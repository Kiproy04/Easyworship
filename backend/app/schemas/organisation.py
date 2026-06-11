"""
app/schemas/organisation.py
Schemas for organisation CRUD and membership/invite operations.
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.rbac import Role


# ── Organisation ─────────────────────────────────────────────────────────────
class OrgCreate(BaseModel):
    """Create a new church organisation."""
    name: str = Field(min_length=2, max_length=200)
    church_type: str | None = Field(None, max_length=100)
    description: str | None = None
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    country: str = Field("KE", min_length=2, max_length=2)
    city: str | None = Field(None, max_length=100)
    address: str | None = None
    timezone: str = "Africa/Nairobi"
    currency: str = Field("KES", min_length=3, max_length=3)


class OrgUpdate(BaseModel):
    """Update organisation details."""
    name: str | None = Field(None, min_length=2, max_length=200)
    church_type: str | None = None
    description: str | None = None
    logo_url: str | None = None
    website: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    city: str | None = None
    address: str | None = None
    timezone: str | None = None
    currency: str | None = None


class OrgRead(BaseModel):
    """Public-facing organisation representation."""
    id: str
    name: str
    slug: str
    church_type: str | None = None
    description: str | None = None
    logo_url: str | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    country: str
    city: str | None = None
    address: str | None = None
    timezone: str
    currency: str
    plan: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Org Membership ────────────────────────────────────────────────────────────
class OrgMemberRead(BaseModel):
    id: str
    user_id: str
    org_id: str
    role: Role
    is_active: bool
    department: str | None = None
    created_at: datetime
    # Nested user info
    user_email: str | None = None
    user_first_name: str | None = None
    user_last_name: str | None = None

    model_config = {"from_attributes": True}


class OrgMemberUpdate(BaseModel):
    role: Role | None = None
    department: str | None = None
    is_active: bool | None = None


# ── Invite ────────────────────────────────────────────────────────────────────
class InviteCreate(BaseModel):
    """Invite someone to join an organisation."""
    email: EmailStr
    role: Role = Role.VIEWER


class InviteRead(BaseModel):
    id: str
    org_id: str
    email: str
    role: Role
    accepted: bool
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteAccept(BaseModel):
    """Accept an invitation — if user doesn't exist they also register."""
    token: str
    # Only needed if the user doesn't already have an account
    password: str | None = Field(None, min_length=8, max_length=128)
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
