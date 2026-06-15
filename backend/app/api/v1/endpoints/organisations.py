"""
app/api/v1/endpoints/organisations.py
Organisation endpoints — CRUD, membership management, invites.

URL structure:
  POST   /orgs                          — create org
  GET    /orgs/mine                     — my orgs
  GET    /orgs/{org_id}                 — get org detail
  PATCH  /orgs/{org_id}                 — update org
  GET    /orgs/{org_id}/members         — list members
  DELETE /orgs/{org_id}/members/{id}    — remove member
  POST   /orgs/{org_id}/invites         — send invite
  GET    /orgs/{org_id}/invites         — list pending invites
  POST   /orgs/invites/accept           — accept an invite
"""
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import (
    AdminOnly,
    AnyOrgMember,
    SuperAdminOnly,
    get_current_user,
    get_org_member,
)
from app.models.organisation import OrgMember
from app.models.user import User
from app.schemas.organisation import (
    InviteAccept,
    InviteCreate,
    InviteRead,
    OrgCreate,
    OrgMemberRead,
    OrgRead,
    OrgUpdate,
)
from app.services.org_service import OrgService

router = APIRouter(prefix="/orgs", tags=["organisations"])


# ── Create ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=OrgRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organisation",
)
async def create_org(
    payload: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgRead:
    """
    Create a new church organisation.
    The authenticated user automatically becomes SUPER_ADMIN.
    Slug is auto-generated from the org name.
    """
    org = await OrgService(db).create(payload, current_user)
    return OrgRead.model_validate(org)


# ── My orgs ───────────────────────────────────────────────────────────────────

@router.get(
    "/mine",
    response_model=list[OrgRead],
    summary="Get all organisations I belong to",
)
async def my_orgs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrgRead]:
    """Returns all active organisations the current user is a member of."""
    orgs = await OrgService(db).get_my_orgs(current_user)
    return [OrgRead.model_validate(o) for o in orgs]


# ── Get one ───────────────────────────────────────────────────────────────────

@router.get(
    "/{org_id}",
    response_model=OrgRead,
    summary="Get organisation details",
)
async def get_org(
    org_id: UUID,
    org_member: OrgMember = AnyOrgMember,
    db: AsyncSession = Depends(get_db),
) -> OrgRead:
    """
    Get full organisation details.
    Requires the user to be an active member of this org.
    """
    org = await OrgService(db).get_by_id(str(org_id))
    return OrgRead.model_validate(org)


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch(
    "/{org_id}",
    response_model=OrgRead,
    summary="Update organisation settings",
)
async def update_org(
    org_id: UUID,
    payload: OrgUpdate,
    org_member: OrgMember = AdminOnly,
    db: AsyncSession = Depends(get_db),
) -> OrgRead:
    """
    Update organisation details — name, description, contact info, etc.
    Requires ADMIN or SUPER_ADMIN role.
    """
    service = OrgService(db)
    org = await service.get_by_id(str(org_id))
    updated = await service.update(org, payload, actor=org_member)
    return OrgRead.model_validate(updated)


# ── Members ───────────────────────────────────────────────────────────────────

@router.get(
    "/{org_id}/members",
    response_model=list[OrgMemberRead],
    summary="List all organisation members",
)
async def list_members(
    org_id: UUID,
    org_member: OrgMember = AnyOrgMember,
    db: AsyncSession = Depends(get_db),
) -> list[OrgMemberRead]:
    """
    List all active members of the organisation with their roles.
    Any org member can view the member list.
    """
    members = await OrgService(db).get_members(str(org_id))
    return [
        OrgMemberRead(
            id=str(m.id),
            user_id=str(m.user_id),
            org_id=str(m.org_id),
            role=m.role,
            is_active=m.is_active,
            department=m.department,
            created_at=m.created_at,
            user_email=m.user.email if m.user else None,
            user_first_name=m.user.first_name if m.user else None,
            user_last_name=m.user.last_name if m.user else None,
        )
        for m in members
    ]


@router.delete(
    "/{org_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from the organisation",
)
async def remove_member(
    org_id: UUID,
    member_id: UUID,
    org_member: OrgMember = AdminOnly,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove (deactivate) a member from the organisation.
    Requires ADMIN or SUPER_ADMIN.
    Cannot remove yourself or a SUPER_ADMIN unless you are one.
    """
    await OrgService(db).remove_member(
        org_id=str(org_id),
        member_id=str(member_id),
        actor=org_member,
    )


# ── Invites ───────────────────────────────────────────────────────────────────

@router.post(
    "/{org_id}/invites",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Invite someone to join the organisation",
)
async def create_invite(
    org_id: UUID,
    payload: InviteCreate,
    org_member: OrgMember = AdminOnly,
    db: AsyncSession = Depends(get_db),
) -> InviteRead:
    """
    Send an invitation to a new member via email.
    The invite link expires after 48 hours.
    Requires ADMIN or SUPER_ADMIN.
    """
    invite = await OrgService(db).create_invite(
        org_id=str(org_id),
        data=payload,
        inviter=org_member,
    )
    return InviteRead.model_validate(invite)


@router.get(
    "/{org_id}/invites",
    response_model=list[InviteRead],
    summary="List pending invites for this organisation",
)
async def list_invites(
    org_id: UUID,
    org_member: OrgMember = AdminOnly,
    db: AsyncSession = Depends(get_db),
) -> list[InviteRead]:
    """List all pending (unaccepted, unexpired) invites. Requires ADMIN+."""
    from sqlalchemy import select
    from datetime import datetime, UTC
    from app.models.organisation import Invite

    result = await db.scalars(
        select(Invite).where(
            Invite.org_id == org_id,
            Invite.accepted == False,
            Invite.expires_at > datetime.now(UTC),
        ).order_by(Invite.created_at.desc())
    )
    return [InviteRead.model_validate(i) for i in result.all()]


@router.post(
    "/invites/accept",
    response_model=OrgMemberRead,
    summary="Accept an organisation invite",
)
async def accept_invite(
    payload: InviteAccept,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgMemberRead:
    """
    Accept an invite using the token from the invite email link.
    The user must be logged in before accepting.
    If they don't have an account yet, they register first via /auth/register.
    """
    membership = await OrgService(db).accept_invite(
        token=payload.token,
        user=current_user,
    )
    return OrgMemberRead(
        id=str(membership.id),
        user_id=str(membership.user_id),
        org_id=str(membership.org_id),
        role=membership.role,
        is_active=membership.is_active,
        department=membership.department,
        created_at=membership.created_at,
    )