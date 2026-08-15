from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# ── Engine ───────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,       # Ping before checkout to detect stale connections
    pool_size=5,              # Reduced from 10 — Neon free tier has limited connections
    max_overflow=10,          # Reduced from 20
    pool_recycle=270,         # Recycle connections every 4.5 min — before Neon kills idle ones (~5 min)
    pool_timeout=30,          # Wait max 30s for a connection from pool
    echo=False,
    connect_args={
        "keepalives": 1,          # Enable TCP keepalive
        "keepalives_idle": 30,    # Start keepalive probes after 30s of inactivity
        "keepalives_interval": 10, # Probe every 10s
        "keepalives_count": 5,    # Drop after 5 failed probes
        "connect_timeout": 10,    # Fail fast if DB is unreachable
    },
)

# ── Session Factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this base."""
    pass


# ── Dependency ────────────────────────────────────────────────────────────────
def get_db():
    """FastAPI dependency that yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
