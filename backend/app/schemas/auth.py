from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime


# ── Request Schemas ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Used for POST /auth/register"""
    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    """Used for POST /auth/login"""
    email: EmailStr
    password: str


class TokenRefreshRequest(BaseModel):
    """Used for POST /auth/refresh"""
    refresh_token: str


# ── Response Schemas ──────────────────────────────────────────────────────────

class UserOut(BaseModel):
    """Public user fields — never returns hashed_password."""
    id: str
    email: str
    full_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MessageResponse(BaseModel):
    """Generic success/info message."""
    message: str
