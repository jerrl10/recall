"""The vault: reading, writing, and organising notes on disk.

Markdown files are the source of truth. There is no database and no cache to
keep in step — every operation reads or writes the vault directly, so a note
edited by hand in Obsidian is simply the current state.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from . import markdown, templates
from .config import Settings
from .models import CaptureResult, Note, NoteKind
from .slug import display_title, note_filename, title_from_filename


class VaultError(RuntimeError):
    """Raised when an operation would leave the vault in a bad state."""


class Vault:
    """Read/write access to the Recall folder inside an Obsidian vault."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def path_for(self, note_kind: NoteKind, title: str) -> Path:
        """Absolute path a note of this kind and title belongs at."""
        return self._guard(self.settings.root_path / note_kind.folder / note_filename(title))

    def _guard(self, path: Path) -> Path:
        """Refuse any path that escapes the Recall root.

        Resolution happens first, so neither ``..`` in a title nor a symlink
        inside the vault can redirect a write outside the managed folder.
        """
        root = self.settings.root_path.resolve()
        candidate = Path(os.path.normpath(path))
        try:
            resolved = candidate.resolve()
        except OSError as exc:  # pragma: no cover - platform dependent
            raise VaultError(f"cannot resolve path: {candidate}") from exc

        if resolved != root and root not in resolved.parents:
            raise VaultError("refusing to write outside the Recall folder")
        return resolved

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def iter_notes(self) -> Iterator[tuple[Path, dict[str, Any], str]]:
        """Yield every note under the Recall root as (path, properties, body).

        Daily logs are skipped: they are an index of captures, not knowledge,
        and including them would make every search match today's date.
        Archived notes are skipped because withdrawing a note is the whole
        point of archiving it.
        """
        if not self.settings.root_path.exists():
            return
        skip = (self.settings.daily_path, self.settings.archive_path)
        for path in sorted(self.settings.root_path.rglob("*.md")):
            if any(folder in path.parents for folder in skip):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            properties, body = markdown.split_frontmatter(text)
            yield path, properties, body

    def read(self, title: str, note_kind: NoteKind | None = None) -> tuple[Path, str] | None:
        """Find a note by title, returning its path and full text."""
        if note_kind is not None:
            path = self.path_for(note_kind, title)
            if path.exists():
                return path, path.read_text(encoding="utf-8")
            return None

        target = note_filename(title).lower()
        for path in self.settings.root_path.rglob("*.md"):
            if self.settings.archive_path in path.parents:
                continue
            if path.name.lower() == target:
                return path, path.read_text(encoding="utf-8")
        return None

    def archive(self, title: str, note_kind: NoteKind | None = None) -> Path | None:
        """Move a note into the archive folder, preserving its kind subfolder.

        Recall writes autonomously, so it needs a way to withdraw a note it
        should not have written. Moving rather than deleting keeps the action
        reversible: the file stays visible in Obsidian and can be dragged back.
        Nothing an agent does to this vault should be permanent.
        """
        found = self.read(title, note_kind)
        if found is None:
            return None

        source, _ = found
        if self.settings.archive_path in source.parents:
            return source

        destination = self._guard(self.settings.archive_path / source.parent.name / source.name)
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Never clobber something already archived under the same name.
        if destination.exists():
            stamp = date.today().isoformat()
            destination = self._guard(
                destination.with_name(f"{destination.stem} ({stamp}){destination.suffix}")
            )

        os.replace(source, destination)
        return destination

    def body_of(self, path: Path) -> str:
        """Read one note's Markdown body, without its frontmatter.

        Frontmatter is machine bookkeeping. Feeding it to a model wastes
        context on YAML that says nothing the surrounding fields do not.
        """
        try:
            text = self._guard(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, VaultError):
            return ""
        _, body = markdown.split_frontmatter(text)
        return body

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def write_note(self, note: Note, *, merge: bool = True) -> CaptureResult:
        """Create a note, or fold new material into an existing one.

        Merging rather than overwriting is deliberate: the vault is the source
        of truth, so anything already on disk — including the user's own
        edits — must survive a second capture on the same subject.
        """
        path = self.path_for(note.kind, note.title)
        today = date.today()

        if path.exists() and merge:
            text = self._merge(path, note, today)
            created = False
        else:
            text = self._render(note, created_on=today, updated_on=today)
            created = True

        self._atomic_write(path, text)
        return CaptureResult(
            title=display_title(note.title),
            kind=note.kind,
            path=path,
            created=created,
            wiki_link=f"[[{title_from_filename(path.name)}]]",
        )

    def _render(self, note: Note, *, created_on: date, updated_on: date) -> str:
        title = display_title(note.title)
        properties: dict[str, Any] = {
            "title": title,
            "kind": note.kind.value,
            "created": note.created or created_on,
            "updated": note.updated or updated_on,
            "tags": note.tags,
            "projects": note.projects,
            "source": note.source,
        }

        blocks = [
            f"# {title}",
            markdown.callout(note.summary),
            note.body.strip() or templates.skeleton(note.kind),
        ]
        if note.related:
            blocks.append("## Related\n\n" + markdown.wiki_links(note.related))

        return markdown.compose(properties, "\n\n".join(block for block in blocks if block))

    def _merge(self, path: Path, note: Note, today: date) -> str:
        """Append new material to an existing note under a dated heading."""
        existing = path.read_text(encoding="utf-8")
        properties, body = markdown.split_frontmatter(existing)

        properties["updated"] = today
        properties.setdefault("title", display_title(note.title))
        properties.setdefault("kind", note.kind.value)
        properties["tags"] = _union(properties.get("tags"), note.tags)
        properties["projects"] = _union(properties.get("projects"), note.projects)

        addition = note.body.strip() or note.summary.strip()
        section = f"## Update — {today.isoformat()}\n\n{addition}"
        if note.related:
            section += "\n\n" + markdown.wiki_links(note.related)

        return markdown.compose(properties, f"{body.strip()}\n\n{section}")

    def _atomic_write(self, path: Path, text: str) -> None:
        """Write via a temporary file in the same directory, then rename.

        Obsidian watches the vault; a partial write would be visible to it and
        to any sync client. ``os.replace`` makes the swap atomic.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".recall-", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Daily log
    # ------------------------------------------------------------------

    def log_daily(self, entries: list[CaptureResult], *, note_date: date | None = None) -> Path:
        """Append today's captures to the dated log note.

        The daily note is the chronological view — what was learned when —
        while the topic notes hold the durable knowledge.
        """
        day = note_date or date.today()
        path = self._guard(self.settings.daily_path / f"{day.isoformat()}.md")

        if path.exists():
            properties, body = markdown.split_frontmatter(path.read_text(encoding="utf-8"))
        else:
            properties = {
                "title": day.isoformat(),
                "kind": "daily",
                "created": day,
                "tags": ["daily"],
            }
            body = f"# {day.isoformat()}\n\n## Captured"

        if "## Captured" not in body:
            body = f"{body.rstrip()}\n\n## Captured"

        # A note touched twice in one day is still one entry in the day's log.
        lines = [
            f"- {entry.wiki_link} — {'new' if entry.created else 'updated'} {entry.kind.value}"
            for entry in entries
            if entry.wiki_link not in body
        ]
        if not lines:
            return path

        properties["updated"] = day
        self._atomic_write(
            path, markdown.compose(properties, f"{body.rstrip()}\n" + "\n".join(lines))
        )
        return path

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, int]:
        """Note counts per kind folder, for health reporting."""
        counts: dict[str, int] = {}
        for kind in NoteKind:
            folder = self.settings.root_path / kind.folder
            counts[kind.value] = len(list(folder.glob("*.md"))) if folder.exists() else 0
        daily = self.settings.daily_path
        counts["daily"] = len(list(daily.glob("*.md"))) if daily.exists() else 0
        archive = self.settings.archive_path
        counts["archived"] = len(list(archive.rglob("*.md"))) if archive.exists() else 0
        return counts


def _union(existing: Any, incoming: list[str]) -> list[str]:
    """Merge two tag/project lists without losing or duplicating entries."""
    merged: dict[str, None] = {}
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, str) and item.strip():
                merged.setdefault(item.strip(), None)
    elif isinstance(existing, str) and existing.strip():
        merged.setdefault(existing.strip(), None)
    for item in incoming:
        merged.setdefault(item, None)
    return list(merged)
