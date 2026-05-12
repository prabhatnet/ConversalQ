"""
Common Pydantic schemas shared across the application.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Standard error response body."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Wrapper for error responses."""

    error: ErrorDetail


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
