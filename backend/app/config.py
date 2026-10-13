from typing import Any
from pydantic import field_validator
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ─────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    gemini_api_key: str = ""
    default_llm_provider: str = "gemini"
    default_model: str = "gemini-3.5-flash"
    # Small planning calls (orchestrator) use a lighter Gemini model, which has its
    # own free-tier quota bucket, so they don't spend the main model's daily requests.
    gemini_light_model: str = "gemini-3.5-flash-lite"
    # Fallback when Gemini is unavailable or out of quota.
    groq_model: str = "openai/gpt-oss-120b"
    groq_tpm_limit: int = 8000  # Groq free-tier tokens/minute (prompt + max_tokens per request)
    # After a Gemini *daily* quota error, skip Gemini for this many seconds.
    gemini_quota_cooldown_seconds: int = 3600

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql://analyst:analyst_password@localhost:5432/data_analyst"
    redis_url: str = "redis://localhost:6379/0"

    # ── Storage ──────────────────────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "datasets"
    minio_secure: bool = False

    # ── Security ─────────────────────────────────────────────────────────────
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # ── App Config ────────────────────────────────────────────────────────────
    max_upload_size_mb: int = 500
    max_analysis_timeout_seconds: int = 600
    sandbox_memory_limit_mb: int = 2048
    sandbox_cpu_limit: int = 2

    # ── Rate Limiting ────────────────────────────────────────────────────────
    rate_limit_analysis: str = "10/hour"    # POST /analysis/{id}/start
    rate_limit_upload: str = "20/hour"      # POST /upload
    rate_limit_default: str = "120/minute"  # all other endpoints

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Observability ─────────────────────────────────────────────────────────
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── Frontend ──────────────────────────────────────────────────────────────
    next_public_api_url: str = "http://localhost:8000"
    next_public_ws_url: str = "ws://localhost:8000/ws"

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: Any = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("["):
                import json
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — reads .env once."""
    return Settings()


settings = get_settings()
