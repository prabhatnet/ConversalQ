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

# Module-level flags
db_available: bool = False
chroma_available: bool = False


async def on_startup(settings: Settings) -> None:
    """Initialize resources on application startup."""
    global db_available, chroma_available

    # --- PostgreSQL ---
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

    # --- ChromaDB ---
    logger.info("initializing_chromadb")
    try:
        from app.rag.vector_store import get_vector_store
        store = get_vector_store()
        await store.connect()
        chroma_available = True
        logger.info("chromadb_initialized")
    except Exception as e:
        chroma_available = False
        logger.warning(
            "chromadb_unavailable_rag_disabled",
            error=str(e),
            hint="Start ChromaDB via Docker: docker compose up chromadb (from the infra/ directory)",
        )


async def on_shutdown() -> None:
    """Clean up resources on application shutdown."""
    from app.db.session import close_db

    logger.info("closing_database_connections")
    await close_db()

    # Disconnect ChromaDB (no-op for HTTP client, but symmetric)
    if chroma_available:
        try:
            from app.rag.vector_store import get_vector_store
            await get_vector_store().disconnect()
        except Exception:
            pass

    logger.info("shutdown_complete")
