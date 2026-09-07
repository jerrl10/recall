"""Finding Obsidian vaults on the machine.

Obsidian keeps a registry of every vault it has opened. Reading it turns setup
from "look up where your vault lives and export an environment variable" into
"pick one from this list", which is the difference between a tool someone
configures and one they abandon at the configuration step.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

#: Where Obsidian stores its vault registry, per platform.
_REGISTRY = {
    "darwin": Path.home() / "Library/Application Support/obsidian/obsidian.json",
    "win32": Path(os.environ.get("APPDATA", "")) / "obsidian/obsidian.json",
}
_LINUX_REGISTRY = Path.home() / ".config/obsidian/obsidian.json"


def registry_path() -> Path:
    """The obsidian.json location for this platform."""
    return _REGISTRY.get(sys.platform, _LINUX_REGISTRY)


def registered_vaults() -> list[Path]:
    """Vaults Obsidian knows about, most recently opened first.

    Returns an empty list rather than raising when Obsidian is not installed
    or its registry is unreadable — discovery is a convenience, and setup has
    to work without it.
    """
    path = registry_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []

    entries = data.get("vaults")
    if not isinstance(entries, dict):
        return []

    found: list[tuple[int, Path]] = []
    for entry in entries.values():
        if not isinstance(entry, dict):
            continue
        location = entry.get("path")
        if not isinstance(location, str):
            continue
        candidate = Path(location).expanduser()
        if candidate.is_dir():
            timestamp = entry.get("ts")
            found.append((timestamp if isinstance(timestamp, int) else 0, candidate))

    found.sort(key=lambda pair: pair[0], reverse=True)
    return [path for _, path in found]


def looks_like_a_vault(path: Path) -> bool:
    """Whether a directory is an Obsidian vault.

    The marker is a `.obsidian` folder. A directory of Markdown without one
    still works — Obsidian creates the folder when it first opens it — so this
    is used to reassure, never to refuse.
    """
    return (path / ".obsidian").is_dir()


def search_nearby(limit: int = 20) -> list[Path]:
    """Look for vaults in the usual places, when the registry gave nothing."""
    roots = [
        Path.home() / "Documents",
        Path.home() / "Notes",
        Path.home() / "Dropbox",
        Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents",
        Path.home(),
    ]

    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for marker in root.glob("*/.obsidian"):
                vault = marker.parent
                if vault not in found:
                    found.append(vault)
                if len(found) >= limit:
                    return found
        except OSError:
            continue
    return found


def discover() -> list[Path]:
    """Every vault worth offering the user, best guess first."""
    vaults = registered_vaults()
    for candidate in search_nearby():
        if candidate not in vaults:
            vaults.append(candidate)
    return vaults
