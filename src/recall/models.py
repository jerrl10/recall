"""The note model. Markdown files are the source of truth; these types are
the in-memory shape of a note on its way to or from disk.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class NoteKind(StrEnum):
    """What sort of knowledge a note holds.

    The kind selects both the vault folder and the body template, so it is
    the one field that changes where a note lives.
    """

    CONCEPT = "concept"
    DECISION = "decision"
    LESSON = "lesson"
    QUESTION = "question"
    PROJECT = "project"

    @property
    def folder(self) -> str:
        """Vault subfolder for this kind."""
        return {
            NoteKind.CONCEPT: "Concepts",
            NoteKind.DECISION: "Decisions",
            NoteKind.LESSON: "Lessons",
            NoteKind.QUESTION: "Questions",
            NoteKind.PROJECT: "Projects",
        }[self]


class Note(BaseModel):
    """A single durable note, as captured from a conversation."""

    title: str = Field(min_length=1, max_length=120)
    kind: NoteKind
    summary: str = Field(
        min_length=1,
        max_length=500,
        description="One or two sentences. Becomes the callout under the title.",
    )
    body: str = Field(
        default="",
        description="Markdown body. Rendered under the kind's section headings.",
    )
    tags: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    related: list[str] = Field(
        default_factory=list,
        description="Titles of other notes; rendered as [[wiki links]].",
    )
    source: str | None = Field(
        default=None,
        description="Which AI client captured this, e.g. 'claude-code'.",
    )
    created: date | None = None
    updated: date | None = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("title cannot be blank")
        return cleaned

    @field_validator("tags", "projects", mode="after")
    @classmethod
    def _normalize_terms(cls, values: list[str]) -> list[str]:
        """Lowercase, dedupe, drop blanks, keep order stable.

        Obsidian tags are case-sensitive in search, so normalizing here stops
        'Azure' and 'azure' becoming two tags in the graph.
        """
        seen: dict[str, None] = {}
        for value in values:
            term = value.strip().lstrip("#").replace(" ", "-").lower()
            if term:
                seen.setdefault(term, None)
        return list(seen)


class SearchHit(BaseModel):
    """A ranked pointer to a note already in the vault."""

    title: str
    kind: NoteKind
    path: Path
    score: float
    excerpt: str
    tags: list[str] = Field(default_factory=list)

    @property
    def wiki_link(self) -> str:
        """Obsidian link form, for pasting into another note."""
        return f"[[{self.title}]]"


class CaptureResult(BaseModel):
    """What happened when a note was written."""

    title: str
    kind: NoteKind
    path: Path
    created: bool = Field(description="True if new, False if an existing note was updated.")
    wiki_link: str
