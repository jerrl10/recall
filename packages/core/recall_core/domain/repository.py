from typing import Protocol
from uuid import UUID

from .models import Memory


class MemoryRepository(Protocol):
    async def save(self, memory: Memory) -> None: ...

    async def get(self, memory_id: UUID) -> Memory | None: ...

    async def search(self, query: str, limit: int = 10) -> list[Memory]: ...

    async def update(self, memory: Memory) -> None: ...
