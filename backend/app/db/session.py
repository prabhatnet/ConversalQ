"""
Async database session management.

Architecture Decision:
- AsyncSession for non-blocking database I/O
- Session-per-request pattern via async generator
- Connection pooling with sensible defaults
- Separate init/close for lifecycle management
"""

from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

logger = structlog.get_logger(__name__)

# Module-level engine and session factory — initialized on startup
_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_db(settings: Settings) -> None:
    """Initialize the async database engine and session factory."""
    global _engine, _async_session_factory

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.app_debug,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Verify connectivity — raises if PostgreSQL is unreachable
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    logger.info("database_engine_created", url=settings.database_url.split("@")[-1])


async def close_db() -> None:
    """Dispose of the database engine and connections."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("database_engine_disposed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async database session."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
