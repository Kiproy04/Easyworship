"""
app/services/auth_service.py
All authentication business logic — now with audit logging.
"""
from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.models.organisation import OrgMember
from app.models.user import User
from app.schemas.auth import (
    MeResponse,
    OrgContext,
    RegisterRequest,
    TokenResponse,
)
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Register ──────────────────────────────────────────────────────────────

    async def register(
        self, data: RegisterRequest, request: Request | None = None
    ) -> User:
        existing = await self.db.scalar(
            select(User).where(User.email == data.email.lower())
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        user = User(
            email=data.email.lower().strip(),
            hashed_password=hash_password(data.password),
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            phone=data.phone,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()

        await AuditService(self.db).log_created(
            resource="user",
            resource_id=str(user.id),
            actor_id=str(user.id),
            data={
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            request=request,
        )
        return user

    # ── Login ─────────────────────────────────────────────────────────────────

    async def login(
        self, email: str, password: str, request: Request | None = None
    ) -> TokenResponse:
        user = await self.db.scalar(
            select(User).where(User.email == email.lower())
        )

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact your administrator.",
            )

        await AuditService(self.db).log_login(str(user.id), request=request)

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ── Refresh ───────────────────────────────────────────────────────────────

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("Wrong token type")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user = await self.db.scalar(
            select(User).where(
                User.id == payload["sub"],
                User.is_active == True,
            )
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ── Me ────────────────────────────────────────────────────────────────────

    async def get_me(self, user: User) -> MeResponse:
        result = await self.db.scalar(
            select(User)
            .where(User.id == user.id)
            .options(
                selectinload(User.org_memberships)
                .selectinload(OrgMember.organisation)
            )
        )

        orgs = [
            OrgContext(
                id=str(m.organisation.id),
                name=m.organisation.name,
                slug=m.organisation.slug,
                role=m.role.value,
                plan=m.organisation.plan,
            )
            for m in result.org_memberships
            if m.is_active and m.organisation.is_active
        ]

        return MeResponse(
            id=str(result.id),
            email=result.email,
            first_name=result.first_name,
            last_name=result.last_name,
            phone=result.phone,
            avatar_url=result.avatar_url,
            is_verified=result.is_verified,
            orgs=orgs,
        )

    # ── Change password ───────────────────────────────────────────────────────

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
        request: Request | None = None,
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        user.hashed_password = hash_password(new_password)
        await self.db.flush()

        await AuditService(self.db).log(
            action="password_changed",
            resource="user",
            resource_id=str(user.id),
            actor_id=str(user.id),
            request=request,
        )