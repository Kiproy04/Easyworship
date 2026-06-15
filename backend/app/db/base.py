"""
app/db/base.py
SQLAlchemy declarative base + all model imports.

WHY this file exists:
  Alembic's autogenerate scans Base.metadata to detect your tables.
  It can only see models that have been imported before that scan runs.
  Importing them all here and then importing this file in alembic/env.py
  guarantees every table gets picked up automatically.

  Rule: every time you create a new model file, add its import here.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """All SQLAlchemy models inherit from this."""
    pass


       