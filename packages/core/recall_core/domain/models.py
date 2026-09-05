from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MemoryKind(StrEnum):
    CONCEPT = "concept"
    DECISION = "decision"
    LESSON = "lesson"
    QUESTION = "question"
    PROJECT_CONTEXT = "project_context"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISPUTED = "disputed"


class Memory(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: MemoryKind
    title: str
    summary: str
    content: str
    tags: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    status: MemoryStatus = MemoryStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
