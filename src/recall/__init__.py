"""Recall — durable engineering memory for AI coding assistants.

Captures knowledge from AI conversations into a well-structured Obsidian
vault. Markdown files are the source of truth; there is no database.
"""

from .models import CaptureResult, Note, NoteKind, SearchHit

__version__ = "0.1.0"

__all__ = ["CaptureResult", "Note", "NoteKind", "SearchHit", "__version__"]
