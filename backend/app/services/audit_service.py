"""
app/services/audit_service.py
Centralised audit logging — called after every state-changing action.

Usage:
    await AuditService(db).log(
        action="created",
        resource="organisation",
        resource_id=str(org.id),
        org_id=str(org.id),
        actor_id=str(current_user.id),
        changes={"name": {"before": None, "after": org.name}},
        request=request,   # optional — extracts IP + user agent
    )

Design decisions:
  - Audit writes never raise exceptions — a failed audit log should
    never break the actual operation. Errors are logged to stderr only.
  - Records are NEVER deleted — no delete method exists intentionally.
  - actor_id is None for system/celery background tasks.
  - changes follows the diff format:
      {"field": {"before": old_value, "after": new_value}}
"""
import logging
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        *,
        action: str,
        resource: str,
        resource_id: str | None = None,
        org_id: str | UUID | None = None,
        actor_id: str | UUID | None = None,
        changes: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> None:
        """
        Write an audit entry. Never raises — failures are logged only.

        Args:
            action      — verb describing what happened:
                          "created" | "updated" | "deleted" |
                          "login" | "logout" | "invited" | "accepted_invite" |
                          "password_changed" | "role_changed" | "deactivated"
            resource    — entity type: "user" | "organisation" |
                          "org_member" | "invite" | "member" | "donation" ...
            resource_id — UUID or ID of the affected record
            org_id      — which organisation this belongs to
            actor_id    — user who performed the action (None = system)
            changes     — JSONB diff of what changed:
                          {"name": {"before": "Old", "after": "New"}}
            request     — FastAPI Request object for IP + user agent extraction
        """
        try:
            entry = AuditLog(
                org_id=UUID(str(org_id)) if org_id else None,
                actor_id=UUID(str(actor_id)) if actor_id else None,
                action=action,
                resource=resource,
                resource_id=str(resource_id) if resource_id else None,
                changes=changes,
                ip_address=_extract_ip(request) if request else None,
                user_agent=_extract_user_agent(request) if request else None,
            )
            self.db.add(entry)
            await self.db.flush()

        except Exception as exc:
            # Never let audit logging break the main operation
            logger.error(
                "Audit log failed — action=%s resource=%s resource_id=%s error=%s",
                action, resource, resource_id, exc,
            )

    # ── Convenience methods ───────────────────────────────────────────────────

    async def log_login(
        self, user_id: str, request: Request | None = None
    ) -> None:
        await self.log(
            action="login",
            resource="user",
            resource_id=user_id,
            actor_id=user_id,
            request=request,
        )

    async def log_created(
        self,
        resource: str,
        resource_id: str,
        org_id: str | None = None,
        actor_id: str | None = None,
        data: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> None:
        """Log a record creation — changes shows the initial values."""
        changes = (
            {k: {"before": None, "after": v} for k, v in data.items()}
            if data else None
        )
        await self.log(
            action="created",
            resource=resource,
            resource_id=resource_id,
            org_id=org_id,
            actor_id=actor_id,
            changes=changes,
            request=request,
        )

    async def log_updated(
        self,
        resource: str,
        resource_id: str,
        before: dict[str, Any],
        after: dict[str, Any],
        org_id: str | None = None,
        actor_id: str | None = None,
        request: Request | None = None,
    ) -> None:
        """
        Log an update — only records fields that actually changed.
        Automatically diffs before vs after so callers don't have to.
        """
        changes = {
            k: {"before": before.get(k), "after": after.get(k)}
            for k in after
            if after.get(k) != before.get(k)
        }
        if not changes:
            return  # nothing actually changed — skip the write

        await self.log(
            action="updated",
            resource=resource,
            resource_id=resource_id,
            org_id=org_id,
            actor_id=actor_id,
            changes=changes,
            request=request,
        )

    async def log_deleted(
        self,
        resource: str,
        resource_id: str,
        org_id: str | None = None,
        actor_id: str | None = None,
        request: Request | None = None,
    ) -> None:
        await self.log(
            action="deleted",
            resource=resource,
            resource_id=resource_id,
            org_id=org_id,
            actor_id=actor_id,
            request=request,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_ip(request: Request) -> str | None:
    """
    Extract real client IP — checks X-Forwarded-For first
    (set by Railway / nginx / Cloudflare proxies).
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can be a comma-separated list — first is the client
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def _extract_user_agent(request: Request) -> str | None:
    return request.headers.get("User-Agent")