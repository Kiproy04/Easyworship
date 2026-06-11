"""
app/core/security.py
Password hashing and JWT creation / verification.
"""
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ── Password hashing ─────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────────────────────────
def _create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + expires_delta
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: str, org_id: str | None = None) -> str:
    """Short-lived token (default 30 min) — carries user + org context."""
    return _create_token(
        {"sub": user_id, "org": org_id, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    """Long-lived token (default 7 days) — only carries user id."""
    return _create_token(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT.
    Raises JWTError on invalid / expired tokens.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def create_invite_token(email: str, org_id: str, role: str) -> str:
    """Special-purpose token embedded in invite links (24h expiry)."""
    return _create_token(
        {"sub": email, "org": org_id, "role": role, "type": "invite"},
        timedelta(hours=24),
    )
