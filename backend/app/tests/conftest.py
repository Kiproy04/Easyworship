import os
import asyncio
import pytest
from typing import AsyncGenerator
from alembic import command  
from alembic.config import Config
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
# 2. Force the application to load the 'test' profile configuration
os.environ["APP_ENV"] = "test"

from app.config import settings
from app.db.session import get_db  # Change this to match your actual database session dependency import
from app.main import app

# Create the dedicated async test database engine
test_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)

@pytest.fixture(scope="session", autouse=True)
def migrate_database():
    """Automatically applies Alembic migrations to the test database on startup."""
    alembic_cfg = Config("alembic.ini")
    # Dynamically inject the test connection URL with the doubled percents for configparser
    escaped_url = settings.DATABASE_SYNC_URL.replace("%", "%%")
    alembic_cfg.set_main_option("sqlalchemy.url", escaped_url)
    
    # Upgrade the database schema straight to head
    command.upgrade(alembic_cfg, "head")
    yield
    # Optional: Clean up the tables when the entire test suite finishes
    # command.downgrade(alembic_cfg, "base")


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a pristine, isolated transaction for every single test block."""
    # Use connect() instead of begin() so it doesn't auto-commit
    async with test_engine.connect() as connection:
        # 1. Explicitly start a transaction
        transaction = await connection.begin()
        # 2. Bind your session to this specific transaction
        async with TestingSessionLocal(bind=connection) as session:
            yield session            
        # 3. CRITICAL: Always roll back the transaction when the test finishes
        await transaction.rollback()

@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provides an async HTTP client with FastAPI's database dependency overridden."""
    async def _override_get_db():
        try:
            yield db_session
        finally:
            await db_session.close()

    # Hot-swap your normal database session dependency with our sandboxed test session
    app.dependency_overrides[get_db] = _override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
        
    # Clean up the override after the test finishes
    app.dependency_overrides.clear()