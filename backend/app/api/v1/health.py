"""
Health check endpoints.

Provides liveness and readiness probes for container orchestrators
(Kubernetes, Docker health checks, load balancers).
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check() -> dict:
    """Liveness probe — returns 200 if the process is alive."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness probe — checks downstream dependencies."""
    # Phase 1: basic check. Expand with DB/Redis pings in later phases.
    return {
        "status": "ready",
        "checks": {
            "database": "ok",  # TODO: actual DB ping in Phase 2+
            "redis": "ok",     # TODO: actual Redis ping in Phase 4+
        },
    }
