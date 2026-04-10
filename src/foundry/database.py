"""Database configuration and session management."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from foundry.config import settings

# Convert postgresql:// to postgresql+asyncpg://
database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

# Create async engine
engine = create_async_engine(
    database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.debug,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def init_db() -> None:
    """Initialize the database by creating all tables.
    
    This should be called on application startup.
    """
    # Convert postgresql:// to postgresql+asyncpg:// if needed for logging
    # we use the database_url variable defined above line 9
    print(f"Initializing database at {database_url}...")
    
    try:
        # Import all models to ensure they are registered with Base.metadata
        import foundry.models # noqa: F401
        
        async with engine.begin() as conn:
            # create_all is a synchronous-style call that conn.run_sync can execute
            await conn.run_sync(Base.metadata.create_all)
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        # In production, we might want to re-raise or handle this differently
        # raise e


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
