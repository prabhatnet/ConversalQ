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
