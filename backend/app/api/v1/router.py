"""
API v1 Router Aggregator.

Architecture Decision:
- All v1 routers registered here for single-point inclusion in main.py
- Tagged for OpenAPI grouping
- Prefix applied at the router level, not per-endpoint
"""

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.agents import router as agents_router
from app.api.v1.voice import router as voice_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(chat_router, prefix="/chat", tags=["Chat"])
api_v1_router.include_router(knowledge_router, tags=["Knowledge Base"])
api_v1_router.include_router(agents_router)
api_v1_router.include_router(voice_router, prefix="/voice", tags=["Voice"])
