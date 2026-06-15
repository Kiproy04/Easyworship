"""
app/api/v1/router.py
Aggregates all v1 endpoint routers into a single APIRouter.
Mounted in main.py under /api/v1.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth
from app.api.v1.endpoints import organisations

api_router = APIRouter()

# ── Auth (public) ─────────────────────────────────────────────────────────────
api_router.include_router(auth.router)

# ── Organisations ─────────────────────────────────────────────────────────────
api_router.include_router(organisations.router)

# ── Coming in Sprint 1 ────────────────────────────────────────────────────────
# from app.api.v1.endpoints import members
# api_router.include_router(members.router)