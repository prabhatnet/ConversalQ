"""
Global exception handlers for the FastAPI application.

Architecture Decision:
- Maps domain exceptions to HTTP responses in ONE place
- Keeps business logic free from HTTP status codes
- Returns consistent error response format across all endpoints
- Logs all unhandled exceptions with full context
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ConversalQError,
    ContentModerationError,
    ConversationNotFoundError,
    LLMServiceError,
    PromptInjectionError,
    RateLimitExceededError,
    ValidationError,
)

logger = structlog.get_logger(__name__)

# Maps exception types to HTTP status codes
_EXCEPTION_STATUS_MAP: dict[type[ConversalQError], int] = {
    ConversationNotFoundError: 404,
    ValidationError: 422,
    RateLimitExceededError: 429,
    LLMServiceError: 502,
    PromptInjectionError: 400,
    ContentModerationError: 422,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application."""

    @app.exception_handler(ConversalQError)
    async def handle_domain_exception(request: Request, exc: ConversalQError) -> JSONResponse:
        status_code = _EXCEPTION_STATUS_MAP.get(type(exc), 500)
        logger.warning(
            "domain_exception",
            error_code=exc.code,
            error_message=exc.message,
            status_code=status_code,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            error_type=type(exc).__name__,
            error_message=str(exc),
            path=str(request.url),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                }
            },
        )
