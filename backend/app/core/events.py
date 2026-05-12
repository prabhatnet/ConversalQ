"""
Application lifecycle events — startup and shutdown hooks.

Architecture Decision:
- Resource initialization (DB pool, Redis) happens at startup
- Graceful cleanup on shutdown prevents resource leaks
- Centralized here for visibility and ordering control
- Falls back to in-memory storage if PostgreSQL is unavailable
"""

import structlog

from app.config import Settings
from app.db.session import init_db

logger = structlog.get_logger(__name__)

# Module-level flag: True if DB is available, False if using in-memory fallback
db_available: bool = False


async def on_startup(settings: Settings) -> None:
    """Initialize resources on application startup."""
    global db_available
    logger.info("initializing_database")
    try:
        await init_db(settings)
        db_available = True
        logger.info("database_initialized")
    except Exception as e:
        db_available = False
        logger.warning(
            "database_unavailable_using_in_memory",
            error=str(e),
            hint="Start PostgreSQL or use Docker Compose for persistent storage.",
        )


async def on_shutdown() -> None:
    """Clean up resources on application shutdown."""
    from app.db.session import close_db

    logger.info("closing_database_connections")
    await close_db()
    logger.info("shutdown_complete")
