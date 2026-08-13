"""
Structured JSON Logging for Autonomous Data Analyst Agent.

Configures Python's standard `logging` module to emit JSON-formatted records
to stdout, suitable for ingestion by log aggregators (Datadog, Loki, CloudWatch).

Usage:
    from app.core.logging import get_logger
    log = get_logger(__name__)
    log.info("analysis started", session_id=sid, user_id=uid)
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from app.config import settings


# ── JSON Formatter ─────────────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Each record includes:
        timestamp   — ISO-8601 UTC
        level       — DEBUG / INFO / WARNING / ERROR / CRITICAL
        logger      — dotted module name
        message     — the log message
        **extra     — any keyword fields passed via LoggerAdapter or log call
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }

        # Include extra fields injected via LoggerAdapter
        for key, val in record.__dict__.items():
            if key not in _STDLIB_KEYS and not key.startswith("_"):
                try:
                    json.dumps(val)  # only add JSON-serialisable extras
                    payload[key] = val
                except (TypeError, ValueError):
                    payload[key] = str(val)

        # Attach exception info if present
        if record.exc_info:
            payload["exception"] = {
                "type":    record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(payload, default=str, ensure_ascii=False)


# Keys that belong to the standard LogRecord — we exclude them from extras
_STDLIB_KEYS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
})


# ── Context adapter ────────────────────────────────────────────────────────────

class ContextLogger(logging.LoggerAdapter):
    """
    A LoggerAdapter that merges a context dict into every log record.

    Usage:
        log = get_logger(__name__, session_id="abc", user_id="123")
        log.info("step completed", step=3)
        # → {"message": "step completed", "session_id": "abc", "user_id": "123", "step": 3, ...}
    """

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        # Pull any extra fields that were passed as keyword arguments
        # e.g. log.info("msg", session_id="abc") → moves session_id into extra
        extra = dict(self.extra)
        extra.update(kwargs.pop("extra", {}))

        # Move any unknown kwargs (that aren't standard logging kwargs) into extra
        standard_kwargs = {"exc_info", "stack_info", "stacklevel"}
        for key in list(kwargs.keys()):
            if key not in standard_kwargs:
                extra[key] = kwargs.pop(key)

        kwargs["extra"] = extra
        return msg, kwargs


# ── Public factory ─────────────────────────────────────────────────────────────

def get_logger(name: str, **context: Any) -> ContextLogger:
    """
    Return a JSON-structured logger for the given module name.

    Args:
        name:    Typically `__name__` of the calling module.
        context: Optional key-value pairs added to every log record.
    """
    return ContextLogger(logging.getLogger(name), context)


# ── Root setup ─────────────────────────────────────────────────────────────────

def configure_logging(level: str = "INFO") -> None:
    """
    Configure the root logger to emit JSON to stdout.
    Call once at application startup (from main.py lifespan).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers (avoids duplicate logs with uvicorn)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root.info(
        "Logging configured",
        extra={"level": level, "format": "JSON"},
    )
