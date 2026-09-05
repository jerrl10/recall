"""Filename derivation.

Obsidian resolves ``[[wiki links]]`` by note title, and the filename is what
carries that title. So the filename must stay readable and stable, while
still being legal on every filesystem Recall might run on.
"""

from __future__ import annotations

import re
import unicodedata

#: Characters Obsidian or a common filesystem will reject or mangle.
#: ``#^[]|`` break wiki-link parsing; the rest are illegal on Windows.
_ILLEGAL = re.compile(r'[<>:"/\\|?*#^\[\]]')

#: Windows reserved device names, which cannot be used even with an extension.
_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

MAX_STEM = 120


def note_filename(title: str) -> str:
    """Return a safe ``.md`` filename for a note title.

    The title is preserved as closely as possible — spaces and case included —
    because it is what a reader sees in Obsidian's file list and what wiki
    links resolve against.
    """
    return f"{_safe_stem(title)}.md"


def _safe_stem(title: str) -> str:
    # Normalize so visually identical titles produce one filename.
    stem = unicodedata.normalize("NFC", title)
    stem = _ILLEGAL.sub("", stem)
    stem = stem.replace("\n", " ").replace("\t", " ")
    stem = " ".join(stem.split())
    # Leading dots hide files; trailing dots and spaces are stripped by Windows.
    stem = stem.strip(". ")

    if len(stem) > MAX_STEM:
        stem = stem[:MAX_STEM].rstrip(". ")

    if not stem:
        return "Untitled"
    if stem.lower() in _RESERVED:
        return f"{stem}-note"
    return stem


def title_from_filename(filename: str) -> str:
    """Recover a display title from a note filename."""
    return filename[:-3] if filename.endswith(".md") else filename
