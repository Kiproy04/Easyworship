"""
app/services/org_service.py
Organisation business logic — create, read, update, membership, invites.
"""
import re
from datetime import datetime, UTC, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.rbac import Role
from app.core.security import create_invite_token
from app.models.organisation import Invite, OrgMember, Organisation
from app.models.user import User
from app.schemas.organisation import InviteCreate, OrgCreate, OrgUpdate
from app.services.audit_service import AuditService  # ← was missing


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


class OrgService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Slug ──────────────────────────────────────────────────────────────────

    async def _unique_slug(self, name: str) -> str:
        base = _slugify(name)
        slug = base
        suffix = 2
        while True:
            exists = await self.db.scalar(
                select(Organisation).where(Organisation.slug == slug)
            )
            if not exists:
                return slug
            slug = f"{base}-{suffix}"
            suffix += 1

    # ── Create ────────────────────────────────────────────────────────────────

    async def create(self, data: OrgCreate, creator: User) -> Organisation:
        slug = await self._unique_slug(data.name)

        org = Organisation(
            name=data.name.strip(),
            slug=slug,
            church_type=data.church_type,
            description=data.description,
            phone=data.phone,
            email=str(data.email).lower() if data.email else None,
            country=data.country.upper(),
            city=data.city,
            address=data.address,
            timezone=data.timezone,
            currency=data.currency.upper(),
            plan="free",
            is_active=True,
        )
        self.db.add(org)
        await self.db.flush()

        membership = OrgMember(
            org_id=org.id,
            user_id=creator.id,
            role=Role.SUPER_ADMIN,
            is_active=True,
        )
        self.db.add(membership)
        await self.db.flush()

        await AuditService(self.db).log_created(
            resource="organisation",
            resource_id=str(org.id),
            org_id=str(org.id),
            actor_id=str(creator.id),
            data={"name": org.name, "slug": org.slug, "plan": org.plan},
        )

        return org

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, org_id: str) -> Organisation:
        org = await self.db.scalar(
            select(Organisation).where(
                Organisation.id == org_id,
                Organisation.is_active == True,
            )
        )
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organisation not found",
            )
        return org

    async def get_my_orgs(self, user: User) -> list[Organisation]:
        result = await self.db.scalars(
            select(Organisation)
            .join(OrgMember, OrgMember.org_id == Organisation.id)
            .where(
                OrgMember.user_id == user.id,
                OrgMember.is_active == True,
                Organisation.is_active == True,
            )
        )
        return list(result.all())

    # ── Update ────────────────────────────────────────────────────────────────

    async def update(
        self,
        org: Organisation,
        data: OrgUpdate,
        actor: OrgMember,       # ← added so we have actor_id for audit
    ) -> Organisation:
        """
        Apply partial updates — only fields explicitly set in the request.
        Captures before/after diff for the audit log.
        """
        # Snapshot before state for audit diff
        before = {
            field: getattr(org, field)
            for field in data.model_dump(exclude_unset=True)
        }

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(org, field, value)
        await self.db.flush()

        # Snapshot after state
        after = {
            field: getattr(org, field)
            for field in data.model_dump(exclude_unset=True)
        }

        await AuditService(self.db).log_updated(
            resource="organisation",
            resource_id=str(org.id),
            org_id=str(org.id),
            actor_id=str(actor.user_id),
            before=before,
            after=after,
        )

        return org

    # ── Members ───────────────────────────────────────────────────────────────

    async def get_members(self, org_id: str) -> list[OrgMember]:
        result = await self.db.scalars(
            select(OrgMember)
            .where(
                OrgMember.org_id == org_id,
                OrgMember.is_active == True,
            )
            .options(selectinload(OrgMember.user))
            .order_by(OrgMember.created_at)
        )
        return list(result.all())

    async def remove_member(
        self, org_id: str, member_id: str, actor: OrgMember
    ) -> None:
        target = await self.db.scalar(
            select(OrgMember).where(
                OrgMember.id == member_id,
                OrgMember.org_id == org_id,
            )
        )
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )

        if str(target.user_id) == str(actor.user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot remove yourself",
            )

        if target.role == Role.SUPER_ADMIN and actor.role != Role.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a super admin can remove another super admin",
            )

        target.is_active = False
        await self.db.flush()

        await AuditService(self.db).log(
            action="deactivated",
            resource="org_member",
            resource_id=str(target.id),
            org_id=str(org_id),
            actor_id=str(actor.user_id),
        )

    # ── Invites ───────────────────────────────────────────────────────────────

    async def create_invite(
        self, org_id: str, data: InviteCreate, inviter: OrgMember
    ) -> Invite:
        existing_member = await self.db.scalar(
            select(OrgMember)
            .join(User, User.id == OrgMember.user_id)
            .where(
                OrgMember.org_id == org_id,
                User.email == data.email.lower(),
                OrgMember.is_active == True,
            )
        )
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This person is already a member of the organisation",
            )

        existing_invite = await self.db.scalar(
            select(Invite).where(
                Invite.org_id == org_id,
                Invite.email == data.email.lower(),
                Invite.accepted == False,
                Invite.expires_at > datetime.now(UTC),
            )
        )
        if existing_invite:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pending invite already exists for this email",
            )

        token = create_invite_token(
            email=data.email.lower(),
            org_id=str(org_id),
            role=data.role.value,
        )

        expire_hours = getattr(settings, "INVITE_TOKEN_EXPIRE_HOURS", 48)
        invite = Invite(
            org_id=org_id,
            invited_by_id=inviter.user_id,
            email=data.email.lower(),
            role=data.role,
            token=token,
            accepted=False,
            expires_at=datetime.now(UTC) + timedelta(hours=expire_hours),
        )
        self.db.add(invite)
        await self.db.flush()

        await AuditService(self.db).log(
            action="invited",
            resource="invite",
            resource_id=str(invite.id),
            org_id=str(org_id),
            actor_id=str(inviter.user_id),
            changes={"email": {"before": None, "after": invite.email},
                     "role": {"before": None, "after": invite.role.value}},
        )

        return invite

    async def accept_invite(self, token: str, user: User) -> OrgMember:
        from app.core.security import decode_token
        from jose import JWTError

        try:
            payload = decode_token(token)
            if payload.get("type") != "invite":
                raise ValueError("Wrong token type")
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invite link",
            )

        invite = await self.db.scalar(
            select(Invite).where(
                Invite.token == token,
                Invite.accepted == False,
                Invite.expires_at > datetime.now(UTC),
            )
        )
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite has already been used or has expired",
            )

        existing = await self.db.scalar(
            select(OrgMember).where(
                OrgMember.org_id == invite.org_id,
                OrgMember.user_id == user.id,
            )
        )
        if existing:
            existing.is_active = True
            existing.role = invite.role
            membership = existing
        else:
            membership = OrgMember(
                org_id=invite.org_id,
                user_id=user.id,
                role=invite.role,
                is_active=True,
            )
            self.db.add(membership)

        invite.accepted = True
        await self.db.flush()

        await AuditService(self.db).log(
            action="accepted_invite",
            resource="org_member",
            resource_id=str(membership.id),
            org_id=str(invite.org_id),
            actor_id=str(user.id),
            changes={"role": {"before": None, "after": invite.role.value}},
        )

        return membership