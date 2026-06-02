"""
Custom exception hierarchy for ConversalQ.

Architecture Decision:
- All business exceptions inherit from ConversalQError
- HTTP status codes mapped in the error handler middleware, not here
- Keeps domain logic free from HTTP concerns
"""


class ConversalQError(Exception):
    """Base exception for all ConversalQ business errors."""

    def __init__(self, message: str = "An unexpected error occurred", code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class LLMServiceError(ConversalQError):
    """Raised when the LLM provider returns an error or is unreachable."""

    def __init__(self, message: str = "LLM service unavailable"):
        super().__init__(message=message, code="LLM_SERVICE_ERROR")


class ConversationNotFoundError(ConversalQError):
    """Raised when a conversation ID does not exist."""

    def __init__(self, conversation_id: str):
        super().__init__(
            message=f"Conversation {conversation_id} not found",
            code="CONVERSATION_NOT_FOUND",
        )


class RateLimitExceededError(ConversalQError):
    """Raised when a client exceeds the configured rate limit."""

    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(message=message, code="RATE_LIMIT_EXCEEDED")


class ValidationError(ConversalQError):
    """Raised for business-level validation failures."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(message=message, code="VALIDATION_ERROR")


class PromptInjectionError(ConversalQError):
    """Raised when a prompt injection or jailbreak pattern is detected in user input."""

    def __init__(self, reason: str = "injection attempt detected"):
        super().__init__(
            message="Your message contains patterns that are not allowed.",
            code="PROMPT_INJECTION_DETECTED",
        )
        self.reason = reason


class ContentModerationError(ConversalQError):
    """Raised when user input is flagged by the content moderation service."""

    def __init__(self, reason: str = "content policy violation"):
        super().__init__(
            message="Your message was flagged by our content moderation system and cannot be processed.",
            code="CONTENT_MODERATION_FLAGGED",
        )
        self.reason = reason


class VoiceServiceError(ConversalQError):
    """Raised when the voice pipeline encounters an unrecoverable error."""

    def __init__(self, message: str = "Voice service error"):
        super().__init__(message=message, code="VOICE_SERVICE_ERROR")


class CallSessionNotFoundError(ConversalQError):
    """Raised when a Twilio CallSid has no matching session."""

    def __init__(self, call_sid: str):
        super().__init__(
            message=f"Call session {call_sid} not found",
            code="CALL_SESSION_NOT_FOUND",
        )
