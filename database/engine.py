from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from loguru import logger

from config import config
from database.models import Base

engine = create_async_engine(
    config.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db():
    """Create all tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

        # Migration: channel_type ustunini qo'shish (agar mavjud bo'lmasa)
        from sqlalchemy import text
        async with engine.begin() as conn:
            try:
                await conn.execute(text(
                    "ALTER TABLE channels ADD COLUMN IF NOT EXISTS "
                    "channel_type VARCHAR(20) DEFAULT 'channel'"
                ))
                logger.info("Migration: channel_type column ensured")
            except Exception:
                pass  # Ustun allaqachon mavjud yoki DB IF NOT EXISTS ni qo'llab-quvvatlamaydi

    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


async def drop_db():
    """Drop all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def get_session() -> AsyncSession:
    """Get a new database session."""
    async with async_session() as session:
        return session
