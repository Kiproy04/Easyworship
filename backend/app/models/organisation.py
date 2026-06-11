"""
app/models/organisation.py
Organisation (church) + OrgMember join table + Invite model.

Multi-tenancy is enforced by always filtering on org_id.
Every business entity (members, donations, etc.) has a FK to organisations.id.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.rbac import Role
from app.models.base import TimestampedModel

if TYPE_CHECKING:
    from app.models.user import User


class Organisation(TimestampedModel):
    """A church (or any ministry organisation) using EasyWorship."""
    __tablename__ = "organisations"

    # ── Identity ─────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )  # e.g. "nairobi-chapel" — used in URLs

    # ── Profile ───────────────────────────────────────────────
    church_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # e.g. "Pentecostal", "Anglican", "Catholic"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Location ──────────────────────────────────────────────
    country: Mapped[str] = mapped_column(String(2), default="KE", nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Regional settings ─────────────────────────────────────
    timezone: Mapped[str] = mapped_column(
        String(50), default="Africa/Nairobi", nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="KES", nullable=False
    )

    # ── Subscription ──────────────────────────────────────────
    plan: Mapped[str] = mapped_column(
        String(50), default="free", nullable=False
    )  # "free" | "pro" | "enterprise"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ─────────────────────────────────────────
    members: Mapped[list["OrgMember"]] = relationship(
        "OrgMember", back_populates="organisation", cascade="all, delete-orphan"
    )
    invites: Mapped[list["Invite"]] = relationship(
        "Invite", back_populates="organisation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organisation id={self.id} slug={self.slug}>"


class OrgMember(TimestampedModel):
    """
    Join table: which User belongs to which Organisation, and with what Role.
    A user can be in multiple orgs (e.g. they serve two churches).
    """
    __tablename__ = "org_members"
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_org_member"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="role_enum"), nullable=False, default=Role.VIEWER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Optional department scope ──────────────────────────────
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Relationships ─────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="org_memberships")
    organisation: Mapped["Organisation"] = relationship(
        "Organisation", back_populates="members"
    )

    def __repr__(self) -> str:
        return f"<OrgMember user={self.user_id} org={self.org_id} role={self.role}>"


class Invite(TimestampedModel):
    """
    Pending invitation to join an organisation.
    Consumed when the invitee registers/accepts.
    """
    __tablename__ = "invites"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="role_enum"),
        nullable=False,
        default=Role.VIEWER,
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────
    organisation: Mapped["Organisation"] = relationship(
        "Organisation", back_populates="invites"
    )

    def __repr__(self) -> str:
        return f"<Invite email={self.email} org={self.org_id} accepted={self.accepted}>"
