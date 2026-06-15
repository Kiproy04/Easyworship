"""
app/config.py
Centralised settings loaded from environment variables via pydantic-settings.
All config is accessed through the `settings` singleton.
"""
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_NAME: str = "EasyWorship"
    APP_VERSION: str = "0.1.0"
    SECRET_KEY: str
    FRONTEND_URL: str = "http://localhost:5173"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str          # async (asyncpg)
    DATABASE_SYNC_URL: str     # sync (psycopg2) 

    # ── JWT ──────────────────────────────────────────────────
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # ── Redis ────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Email — Resend ───────────────────────────────────────
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@easyworship.co.ke"
    EMAIL_FROM_NAME: str = "EasyWorship"

    # ── Africa's Talking (SMS) ───────────────────────────────
    AT_API_KEY: str = ""
    AT_USERNAME: str = "sandbox"
    AT_SENDER_ID: str = "EasyWorship"

    # ── M-Pesa / Daraja ──────────────────────────────────────
    MPESA_CONSUMER_KEY: str = ""
    MPESA_CONSUMER_SECRET: str = ""
    MPESA_SHORTCODE: str = ""
    MPESA_PASSKEY: str = ""
    MPESA_CALLBACK_BASE_URL: str = ""
    MPESA_ENV: str = "sandbox"   # "sandbox" | "production"

    @property
    def mpesa_base_url(self) -> str:
        if self.MPESA_ENV == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    # ── Cloudflare R2 ────────────────────────────────────────
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "easyworship-uploads"
    R2_PUBLIC_URL: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


# Convenience singleton — import this everywhere
settings = get_settings()
