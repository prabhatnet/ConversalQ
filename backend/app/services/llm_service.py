"""
LLM Service — abstraction layer over OpenAI API.

Architecture Decision:
- Encapsulates all LLM interactions behind a single service
- Supports both complete and streaming responses
- Handles retries, error mapping, and token tracking
- Easy to swap providers (OpenAI → Azure OpenAI → Anthropic) by changing this one file
- System prompt defines the AI assistant's persona and capabilities
"""

import time
from typing import AsyncIterator, List, Optional

import structlog
from openai import AsyncOpenAI, APIError, RateLimitError

from app.config import Settings
from app.core.exceptions import LLMServiceError

logger = structlog.get_logger(__name__)

# System prompt establishing the AI call center assistant persona
SYSTEM_PROMPT = """You are ConversalQ, an enterprise AI call center assistant.

Your role:
- Help customers with billing, technical support, account inquiries, and general questions.
- Be professional, empathetic, and concise.
- If you cannot resolve an issue, acknowledge it and indicate it should be escalated.
- Never fabricate information. If unsure, say so clearly.
- Protect customer privacy — never reveal sensitive data.

Response guidelines:
- Keep responses focused and under 300 words unless detail is explicitly requested.
- Use bullet points for multi-step instructions.
- Acknowledge the customer's frustration if they express dissatisfaction.
- End with a clear next step or offer for further assistance.
"""


class LLMService:
    """Service for interacting with Large Language Models."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._temperature = settings.openai_temperature
        self._max_tokens = settings.openai_max_tokens

    async def generate_response(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        system_prompt_addendum: str = "",
    ) -> dict:
        """
        Generate a complete (non-streaming) LLM response.

        Returns:
            dict with keys: content, model, token_count, latency_ms
        """
        full_messages = self._build_messages(messages, system_prompt, system_prompt_addendum)
        start_time = time.perf_counter()

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except RateLimitError as e:
            logger.error("openai_rate_limit", error=str(e))
            raise LLMServiceError("AI service rate limit reached. Please retry in a moment.")
        except APIError as e:
            logger.error("openai_api_error", error=str(e), status_code=e.status_code)
            raise LLMServiceError(f"AI service error: {e.message}")
        except Exception as e:
            logger.exception("openai_unexpected_error", error=str(e))
            raise LLMServiceError("AI service is temporarily unavailable.")

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        choice = response.choices[0]
        usage = response.usage

        logger.info(
            "llm_response_generated",
            model=response.model,
            tokens_total=usage.total_tokens if usage else None,
            latency_ms=elapsed_ms,
        )

        return {
            "content": choice.message.content or "",
            "model": response.model,
            "token_count": usage.total_tokens if usage else None,
            "latency_ms": elapsed_ms,
        }

    async def generate_response_stream(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        system_prompt_addendum: str = "",
    ) -> AsyncIterator[str]:
        """
        Generate a streaming LLM response, yielding tokens as they arrive.

        Yields:
            Individual content tokens as strings.
        """
        full_messages = self._build_messages(messages, system_prompt, system_prompt_addendum)

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except RateLimitError as e:
            logger.error("openai_rate_limit_stream", error=str(e))
            raise LLMServiceError("AI service rate limit reached.")
        except APIError as e:
            logger.error("openai_api_error_stream", error=str(e))
            raise LLMServiceError(f"AI service error: {e.message}")
        except Exception as e:
            logger.exception("openai_unexpected_error_stream", error=str(e))
            raise LLMServiceError("AI service is temporarily unavailable.")

    def _build_messages(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        system_prompt_addendum: str = "",
    ) -> List[dict]:
        """Prepend system prompt (with optional RAG addendum) to message list."""
        system = (system_prompt or SYSTEM_PROMPT) + system_prompt_addendum
        return [{"role": "system", "content": system}] + messages
