"""Pytest configuration and fixtures."""

import pytest
import os
import asyncio
import platform


def pytest_configure(config):
    """Configuration hook for pytest."""
    pass

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from httpx import AsyncClient, ASGITransport
from alembic import command
from alembic.config import Config
from foundry.database import Base
from foundry.config import settings
from foundry.main import app
from foundry.database import get_db

# Test database URL
TEST_DATABASE_URL = settings.database_url.replace("foundry_db", "foundry_db_test")
TEST_DATABASE_URL = TEST_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Global engine for session
_test_engine = None
_migrations_run = False


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup test database with migrations once per session."""
    global _migrations_run
    
    print(f"\n=== Setting up test database, migrations_run={_migrations_run} ===")
    
    if not _migrations_run:
        # Convert async URL to sync for Alembic
        sync_url = TEST_DATABASE_URL.replace("+asyncpg", "")
        
        print(f"Database URL: {sync_url}")
        
        # Configure Alembic
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        
        # Try to get current revision
        try:
            from alembic.script import ScriptDirectory
            from alembic.runtime.migration import MigrationContext
            from sqlalchemy import create_engine
            
            engine = create_engine(sync_url)
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()
                
                print(f"Current revision: {current_rev}")
                
                if current_rev is None:
                    # No migrations applied yet, run them
                    print("Running migrations...")
                    command.upgrade(alembic_cfg, "head")
                    _migrations_run = True
                    print("Migrations completed!")
                else:
                    # Migrations already applied, check if we need to upgrade
                    script = ScriptDirectory.from_config(alembic_cfg)
                    head_rev = script.get_current_head()
                    
                    print(f"Head revision: {head_rev}")
                    
                    if current_rev != head_rev:
                        # Upgrade to latest
                        print("Upgrading migrations...")
                        command.upgrade(alembic_cfg, "head")
                        print("Upgrade completed!")
                    _migrations_run = True
            
            engine.dispose()
        except Exception as e:
            # If anything fails, try a fresh upgrade
            print(f"Error checking migrations: {e}")
            try:
                print("Attempting fresh upgrade...")
                command.upgrade(alembic_cfg, "head")
                _migrations_run = True
                print("Fresh upgrade completed!")
            except Exception as e2:
                print(f"Alembic migration failed: {e2}")
                # Don't raise, let tests continue
    else:
        print("Migrations already run, skipping...")
    
    yield


@pytest.fixture
async def test_engine():
    """Create test database engine for each test to avoid loop mismatches."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with transaction rollback for isolation."""
    # Create a connection
    async with test_engine.connect() as connection:
        # Start a transaction
        async with connection.begin() as transaction:
            # Create session bound to the connection
            async_session = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            
            session = async_session()
            
            try:
                yield session
            finally:
                await session.close()
                # Rollback the transaction to clean up test data
                await transaction.rollback()


@pytest.fixture(scope="function")
async def redis_client():
    """Create test Redis client."""
    from foundry.redis_client import redis_client
    
    # Connect to Redis
    await redis_client.connect()
    
    yield redis_client
    
    # Clean up test data
    await redis_client.client.flushdb()
    
    # Disconnect
    await redis_client.disconnect()


@pytest.fixture
async def client(db_session: AsyncSession, redis_client) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with database session and Redis override."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()
