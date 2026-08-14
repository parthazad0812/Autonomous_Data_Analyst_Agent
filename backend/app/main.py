"""
FastAPI application entry point.

Phase 7 additions:
  - Structured JSON logging configured at startup
  - Request/response logging middleware (method, path, status, duration)
  - Global exception handlers (500 catch-all, 422 validation errors)
  - Rate limiting via SlowAPI (Redis-backed)
  - Deep health check endpoint (/health/ready)
"""

import time
import traceback

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.routes import auth, upload, analysis
from app.api import websocket

log = get_logger(__name__)


# ── Rate limiter (Redis-backed with in-memory fallback) ───────────────────────
def _build_limiter() -> Limiter:
    """Build rate limiter; falls back to in-memory if Redis is unreachable."""
    try:
        import redis as _redis
        r = _redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        r.close()
        return Limiter(
            key_func=get_remote_address,
            storage_uri=settings.redis_url,
            default_limits=[settings.rate_limit_default],
        )
    except Exception:
        log.warning("Redis unavailable — rate limiter using in-memory storage")
        return Limiter(
            key_func=get_remote_address,
            default_limits=[settings.rate_limit_default],
        )

limiter = _build_limiter()


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    configure_logging(settings.log_level)
    log.info(
        "Autonomous Data Analyst Agent API starting up",
        version="1.0.0",
        log_level=settings.log_level,
    )
    yield
    log.info("API shutting down")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Autonomous Data Analyst Agent API",
    description="AI-powered autonomous data analysis platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Attach rate limiter to app state
app.state.limiter = limiter


# ── Middleware ────────────────────────────────────────────────────────────────

# SlowAPI rate limiting middleware
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every HTTP request with method, path, status code, and duration."""
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        log.info(
            "HTTP request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )
        return response
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        log.error(
            "Unhandled exception in request",
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
            error=str(exc),
        )
        raise


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    log.warning(
        "Rate limit exceeded",
        path=request.url.path,
        client=request.client.host if request.client else None,
        limit=str(exc.detail),
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Rate limit exceeded. Please slow down.",
            "retry_after": "Try again in a moment.",
        },
        headers={"Retry-After": "60"},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return clean 422 with field-level errors — never expose raw Pydantic internals."""
    errors = []
    for err in exc.errors():
        errors.append({
            "field": " → ".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        })
    log.warning(
        "Request validation failed",
        path=request.url.path,
        method=request.method,
        errors=errors,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all 500 handler — logs full traceback, returns safe response."""
    log.error(
        "Unhandled server error",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error=str(exc),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(websocket.router)  # WS at /ws/analysis/{session_id}


# ── Health checks ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    """
    Liveness probe — load balancers hit this.
    Returns 200 immediately if the process is alive.
    """
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready", tags=["Health"])
def health_ready():
    """
    Readiness / deep health check.
    Verifies that PostgreSQL, Redis, and MinIO are all reachable.
    Returns 200 only when ALL services are healthy.
    Returns 503 with a service map showing which one(s) failed.
    """
    import redis as redis_lib
    from app.db.database import engine
    from app.services.minio_service import get_minio_client

    services: dict[str, dict] = {}
    all_healthy = True

    # ── PostgreSQL ─────────────────────────────────────────────────────────
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        services["postgres"] = {"status": "healthy"}
    except Exception as exc:
        services["postgres"] = {"status": "unhealthy", "error": str(exc)}
        all_healthy = False
        log.error("Health check: PostgreSQL unhealthy", error=str(exc))

    # ── Redis ──────────────────────────────────────────────────────────────
    try:
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        services["redis"] = {"status": "healthy"}
    except Exception as exc:
        services["redis"] = {"status": "unhealthy", "error": str(exc)}
        all_healthy = False
        log.error("Health check: Redis unhealthy", error=str(exc))

    # ── MinIO ──────────────────────────────────────────────────────────────
    try:
        client = get_minio_client()
        client.bucket_exists(settings.minio_bucket)
        services["minio"] = {"status": "healthy"}
    except Exception as exc:
        services["minio"] = {"status": "unhealthy", "error": str(exc)}
        all_healthy = False
        log.error("Health check: MinIO unhealthy", error=str(exc))

    response_body = {
        "status": "healthy" if all_healthy else "degraded",
        "version": "1.0.0",
        "services": services,
    }

    if not all_healthy:
        log.warning("Readiness check failed — some services unhealthy", services=services)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response_body,
        )

    return response_body


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Autonomous Data Analyst Agent API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/health/ready",
    }
