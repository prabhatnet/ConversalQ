"""
ConversalQ — FastAPI Application Entry Point.

Architecture Decision:
- Application factory pattern via create_app() for testability
- Lifespan context manager for clean startup/shutdown
- Middleware applied in deterministic order
- API versioned under /api/v1/
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.error_handler import register_exception_handlers
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.core.events import on_shutdown, on_startup
from app.observability.logging import configure_logging

settings = get_settings()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — manages startup and shutdown resources."""
    configure_logging(settings.log_level)

    # --- LangSmith tracing ---
    # LangChain/LangGraph read these env vars before every traced call,
    # so they must be set before the first agent invocation.
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
        logger.info(
            "langsmith_tracing_enabled",
            project=settings.langsmith_project,
            endpoint=settings.langsmith_endpoint,
        )
    else:
        # Explicitly disable in case the var leaked from a parent process
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        logger.info("langsmith_tracing_disabled")

    await on_startup(settings)
    logger.info(
        "application_started",
        app_name=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
    )
    yield
    await on_shutdown()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""
    application = FastAPI(
        title=settings.app_name,
        description="Enterprise AI Call Center Assistant — Multi-agent orchestration platform",
        version=settings.app_version,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # --- Middleware (order matters: outermost first) ---
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Exception Handlers ---
    register_exception_handlers(application)

    # --- Routers ---
    application.include_router(api_v1_router, prefix="/api/v1")

    return application


# Uvicorn entry point
app = create_app()
