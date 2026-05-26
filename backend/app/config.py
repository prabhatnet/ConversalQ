"""
ConversalQ Application Configuration.

Centralized configuration using pydantic-settings for type-safe,
environment-variable-driven configuration with validation.

Architecture Decision:
- Single source of truth for all configuration
- Validation at startup prevents runtime config errors
- Immutable after initialization (frozen model)
- Environment-specific overrides via .env files
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file — works regardless of CWD
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "ConversalQ"
    app_env: str = "development"
    app_debug: bool = False
    app_version: str = "0.1.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # --- OpenAI ---
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2048

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "conversalq"
    postgres_password: str = "conversalq_dev_password"
    postgres_db: str = "conversalq"

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # --- Rate Limiting ---
    rate_limit_per_minute: int = 60

    # --- CORS ---
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # --- ChromaDB (Phase 2) ---
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "conversalq_kb"

    # --- Embeddings (Phase 2) ---
    embedding_model: str = "text-embedding-3-small"

    # --- Memory / Session (Phase 4) ---
    memory_window_size: int = 6
    memory_summarize_threshold: int = 10
    memory_summarize_step: int = 4

    # --- Twilio (Phase 5) ---
    twilio_account_sid: str = Field(default="", description="Twilio Account SID")
    twilio_auth_token: str = Field(default="", description="Twilio Auth Token")
    twilio_phone_number: str = Field(default="", description="Outbound caller ID (E.164 format)")
    twilio_webhook_base_url: str = Field(default="http://localhost:8000", description="Base URL for Twilio webhooks (use ngrok for local dev)")
    twilio_validate_webhooks: bool = Field(default=False, description="Validate X-Twilio-Signature (enable in production)")
    twilio_escalation_number: str = Field(default="", description="Phone number to dial for human agent escalation")

    # --- Deepgram (Phase 5) ---
    deepgram_api_key: str = Field(default="", description="Deepgram API key for real-time STT via WebSocket media streams")

    # --- Text-to-Speech (Phase 5) ---
    tts_enabled: bool = Field(default=False, description="Use OpenAI TTS instead of Twilio built-in <Say> (requires extra API calls)")
    tts_model: str = Field(default="tts-1", description="OpenAI TTS model: tts-1 (fast) or tts-1-hd (quality)")
    tts_voice: str = Field(default="alloy", description="OpenAI TTS voice: alloy, echo, fable, onyx, nova, shimmer")
    voice_language: str = Field(default="en-US", description="Speech recognition language for Twilio Gather")
    voice_greeting: str = Field(default="Welcome to ConversalQ. How can I help you today?")
    voice_timeout: int = Field(default=5, description="Seconds to wait for caller speech to begin")

    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Construct sync PostgreSQL URL for Alembic migrations."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once per process."""
    return Settings()
