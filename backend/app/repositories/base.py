"""
Base repository providing common CRUD operations.

Architecture Decision:
- Generic base class avoids code duplication across repositories
- Type-safe with Generic[T] pattern
- All database operations are async
- Repository pattern decouples business logic from data access
"""

from typing import Generic, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, model: Type[T], session: AsyncSession):
        self._model = model
        self._session = session

    async def get_by_id(self, entity_id: UUID) -> Optional[T]:
        """Retrieve an entity by its primary key."""
        return await self._session.get(self._model, entity_id)

    async def create(self, entity: T) -> T:
        """Persist a new entity."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        """Delete an entity."""
        await self._session.delete(entity)
        await self._session.flush()
