"""
app/db/registry.py
Imports all models so Alembic can detect them during autogenerate.
This is the ONLY file that imports both Base and all models together.
Import this in alembic/env.py instead of app/db/base.py
"""
from app.db.base import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.organisation import Organisation, OrgMember, Invite  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401