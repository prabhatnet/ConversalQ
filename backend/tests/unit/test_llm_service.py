"""
Unit tests for LLM Service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.core.exceptions import LLMServiceError
from app.services.llm_service import LLMService


@pytest.fixture
def llm_service() -> LLMService:
    settings = Settings(openai_api_key="sk-test-key")
    return LLMService(settings=settings)


class TestLLMService:
    """Tests for LLMService.generate_response."""

    @pytest.mark.asyncio
    async def test_generate_response_success(self, llm_service: LLMService):
        """Test successful response generation."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! How can I help?"
        mock_response.model = "gpt-4o"
        mock_response.usage = MagicMock(total_tokens=25)

        with patch.object(
            llm_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await llm_service.generate_response(
                messages=[{"role": "user", "content": "Hi"}]
            )

        assert result["content"] == "Hello! How can I help?"
        assert result["model"] == "gpt-4o"
        assert result["token_count"] == 25
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_generate_response_builds_system_prompt(self, llm_service: LLMService):
        """Test that system prompt is prepended to messages."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.model = "gpt-4o"
        mock_response.usage = MagicMock(total_tokens=10)

        captured_messages = None

        async def capture_create(**kwargs):
            nonlocal captured_messages
            captured_messages = kwargs["messages"]
            return mock_response

        with patch.object(
            llm_service._client.chat.completions,
            "create",
            side_effect=capture_create,
        ):
            await llm_service.generate_response(
                messages=[{"role": "user", "content": "Hi"}]
            )

        assert captured_messages is not None
        assert captured_messages[0]["role"] == "system"
        assert "ConversalQ" in captured_messages[0]["content"]
        assert captured_messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_response_handles_api_error(self, llm_service: LLMService):
        """Test that OpenAI API errors are wrapped in LLMServiceError."""
        from openai import APIError

        with patch.object(
            llm_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=APIError(
                message="Service unavailable",
                request=MagicMock(),
                body=None,
            ),
        ):
            with pytest.raises(LLMServiceError):
                await llm_service.generate_response(
                    messages=[{"role": "user", "content": "Hi"}]
                )
