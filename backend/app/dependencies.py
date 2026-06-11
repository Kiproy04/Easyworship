"""
app/dependencies.py
FastAPI dependency functions for auth, multi-tenancy, and RBAC.

These are the most-used functions in the entire codebase.
Every protected endpoint goes through at least one of these.

Dependency chain:
    get_current_user()
        └── get_org_member(org_id)
                └── require_role(*roles)

Usage examples:
    # Any authenticated user in the org
    async def endpoint(member: OrgMember = Depends(get_org_member)): ...

    # Specific roles only
    async def endpoint(member: OrgMember = Depends(require_role(Role.TREASURER))): ...

    # Shorthand aliases (most common)
    async def endpoint(member: OrgMember = AdminOnly): ...
    async def endpoint(member: OrgMember = FinanceOnly): ...
"""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from app.core.rbac import (
    ADMIN_ROLES,
    ALL_STAFF_ROLES,
    FINANCE_ROLES,
    PASTORAL_ROLES,
    Role,
    role_rank,
)
from app.core.security import decode_token
from app.db.session import get_db
from app.models.organisation import OrgMember
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# ── Step 1: Resolve authenticated user from JWT ───────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decodes the JWT and returns the matching User.
    Raises 401 if the token is invalid, expired, or the user no longer exists.
    """
    payload = decode_token(token)  # raises 401 on failure

    result = await db.execute(
        select(User).where(
            User.id == payload["sub"],
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ── Step 2: Resolve org membership ───────────────────────────────────────────

async def get_org_member(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgMember:
    """
    Verifies the current user is an active member of org_id.
    This is the primary multi-tenancy guard — org_id comes from
    the URL path: /api/v1/orgs/{org_id}/...

    Raises 403 if the user does not belong to that org.
    Returns 403 (not 404) intentionally — we never confirm whether
    an org exists to an unauthorised user.
    """
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.org_id == org_id,
            OrgMember.user_id == current_user.id,
            OrgMember.is_active == True,
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organisation",
        )
    return member


# ── Step 3: RBAC role enforcement ─────────────────────────────────────────────

def require_role(*roles: Role):
    """
    Dependency factory — returns a dependency that enforces role membership.

    Accepts one or more roles. Passes if the member has ANY of them.
    Uses role_rank() so higher-privilege roles always satisfy lower requirements.

    Examples:
        Depends(require_role(Role.TREASURER))
            → treasurer, admin, super_admin all pass

        Depends(require_role(Role.PASTOR, Role.TREASURER))
            → pastoral OR finance roles pass (and anyone above them)
    """
    async def checker(
        org_member: OrgMember = Depends(get_org_member),
    ) -> OrgMember:
        member_rank = role_rank(org_member.role)
        # Pass if member rank is <= (higher privilege) any of the required roles
        allowed = any(member_rank <= role_rank(r) for r in roles)

        if not allowed:
            required_names = " or ".join(r.value for r in roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {required_names} (or higher)",
            )
        return org_member

    return checker


# ── Convenience aliases ───────────────────────────────────────────────────────
# Import these directly in endpoints for clean, readable code.
#
# Usage:
#   async def delete_member(member: OrgMember = SuperAdminOnly): ...
#   async def approve_expense(member: OrgMember = FinanceOnly): ...

SuperAdminOnly = Depends(require_role(Role.SUPER_ADMIN))
AdminOnly      = Depends(require_role(Role.ADMIN))        # admin + super_admin
FinanceOnly    = Depends(require_role(Role.TREASURER))    # treasurer + above
PastoralOnly   = Depends(require_role(Role.PASTOR))       # pastor + above
AnyStaff       = Depends(require_role(Role.DEPARTMENT_HEAD))  # all staff roles
AnyOrgMember   = Depends(get_org_member)                  # any role, just must be in org