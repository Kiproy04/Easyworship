"""
app/models/audit.py
Audit log — every create/update/delete is recorded from day one.
Financial data regulations require immutable audit trails.
Records are NEVER deleted.
"""
import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedModel


class AuditLog(TimestampedModel):
    """
    Immutable audit record for every state-changing action.

    Fields:
      org_id       — which organisation this action belongs to
      actor_id     — who did it (None = system/celery task)
      action       — verb: "created", "updated", "deleted", "login", etc.
      resource     — table/entity name: "member", "donation", "user", etc.
      resource_id  — UUID of the affected record (str for flexibility)
      changes      — JSONB diff: {"field": {"before": old, "after": new}}
      ip_address   — request IP (for security auditing)
      user_agent   — browser/client info
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_org_created", "org_id", "created_at"),
        Index("ix_audit_resource", "resource", "resource_id"),
    )

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AuditLog action={self.action} resource={self.resource} "
            f"resource_id={self.resource_id}>"
        )
