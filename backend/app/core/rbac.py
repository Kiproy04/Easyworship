"""
app/core/rbac.py
Role-Based Access Control — roles, permissions, and a require_role() factory.

Role hierarchy (highest → lowest):
  super_admin → admin → treasurer → pastor → department_head → member → viewer
"""
from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"      # full god-mode within their org
    ADMIN = "admin"                  # org admin (invites, settings)
    TREASURER = "treasurer"          # full finance access
    PASTOR = "pastor"                # people, attendance, communication
    DEPARTMENT_HEAD = "department_head"  # scoped to their department
    MEMBER = "member"                # read-only member portal (Phase 2)
    VIEWER = "viewer"                # read-only dashboard


# Ordered list — index 0 = highest privilege
ROLE_HIERARCHY: list[Role] = [
    Role.SUPER_ADMIN,
    Role.ADMIN,
    Role.TREASURER,
    Role.PASTOR,
    Role.DEPARTMENT_HEAD,
    Role.MEMBER,
    Role.VIEWER,
]


def role_rank(role: Role) -> int:
    """Lower index = higher privilege."""
    try:
        return ROLE_HIERARCHY.index(role)
    except ValueError:
        return len(ROLE_HIERARCHY)  # unknown role = lowest privilege


def has_permission(user_role: Role, required_role: Role) -> bool:
    """Return True if user_role is at least as privileged as required_role."""
    return role_rank(user_role) <= role_rank(required_role)


# ── Permission groups ────────────────────────────────────────────────────────
# These are convenient sets used in require_role() dependency.

FINANCE_ROLES = {Role.SUPER_ADMIN, Role.ADMIN, Role.TREASURER}
PASTORAL_ROLES = {Role.SUPER_ADMIN, Role.ADMIN, Role.PASTOR}
ADMIN_ROLES = {Role.SUPER_ADMIN, Role.ADMIN}
ALL_STAFF_ROLES = {
    Role.SUPER_ADMIN, Role.ADMIN, Role.TREASURER,
    Role.PASTOR, Role.DEPARTMENT_HEAD,
}
