from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from app.config import settings


# Convert postgres:// to postgresql+asyncpg://
database_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace("postgres://", "postgresql+asyncpg://")

# Create async engine
engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def init_db():
    """Initialize database connection."""
    async with engine.begin() as conn:
        # Create all tables (use Alembic migrations in production)
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized")


async def close_db():
    """Close database connection."""
    await engine.dispose()
    print("Database connection closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
