"""
Shared test fixtures for ConversalQ tests.
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.dependencies import get_chat_service, get_db
from app.main import create_app
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService


def get_test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        app_env="testing",
        app_debug=True,
        openai_api_key="sk-test-key",
        postgres_host="localhost",
        postgres_db="conversalq_test",
    )


@pytest.fixture
def settings() -> Settings:
    return get_test_settings()


@pytest.fixture
def mock_llm_service() -> MagicMock:
    """Mock LLM service that returns predictable responses."""
    service = MagicMock(spec=LLMService)
    service.generate_response = AsyncMock(return_value={
        "content": "I'd be happy to help you with your billing issue. Could you please provide your account number?",
        "model": "gpt-4o",
        "token_count": 42,
        "latency_ms": 150,
    })

    async def mock_stream(*args, **kwargs):
        tokens = ["I'd ", "be ", "happy ", "to ", "help!"]
        for token in tokens:
            yield token

    service.generate_response_stream = mock_stream
    service._model = "gpt-4o"
    return service


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    application = create_app()
    application.dependency_overrides[get_settings] = get_test_settings
    return application


@pytest.fixture
def client(app) -> TestClient:
    """Synchronous test client."""
    return TestClient(app)


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for testing async endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
