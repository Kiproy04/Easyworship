"""
app/schemas/auth.py
Request/response schemas for authentication endpoints.
"""
from pydantic import BaseModel, EmailStr, Field
from app.schemas.organisation import OrgRead


# ── Register ────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=20)


class RegisterResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    message: str = "Registration successful. Please verify your email."

    model_config = {"from_attributes": True}


# ── Login ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ── Refresh ─────────────────────────────────────────────────────────────────
class RefreshRequest(BaseModel):
    refresh_token: str


# ── Password ────────────────────────────────────────────────────────────────
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class OrgContext(BaseModel):
    """Org summary embedded in /me response."""
    id: str
    name: str
    slug: str
    role: str
    plan: str

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    """Returned by GET /auth/me — user + all their orgs."""
    id: str
    email: str
    first_name: str
    last_name: str
    phone: str | None = None
    avatar_url: str | None = None
    is_verified: bool
    orgs: list[OrgContext] = []

    model_config = {"from_attributes": True}
