"""
app/schemas/user.py
Schemas for user profile operations.
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    """Public-facing user representation."""
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None = None
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Fields the user can update on their own profile."""
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=20)
    avatar_url: str | None = Field(None, max_length=512)
