"""Reading and writing Obsidian-flavoured Markdown.

Frontmatter is *written* by hand so the output matches what Obsidian's own
Properties editor produces, and *parsed* with PyYAML so a note the user has
edited by hand still loads.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import yaml

FRONTMATTER_FENCE = "---"

#: Frontmatter key order. Obsidian preserves file order in the Properties
#: panel, so a stable order keeps every note looking the same.
_KEY_ORDER = (
    "title",
    "kind",
    "created",
    "updated",
    "tags",
    "projects",
    "source",
)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a note into its frontmatter mapping and its body.

    A note with absent, malformed, or non-mapping frontmatter is treated as a
    note with no properties rather than an error — the vault is the source of
    truth and may legitimately contain hand-written files.
    """
    if not text.startswith(FRONTMATTER_FENCE):
        return {}, text

    parts = text.split(FRONTMATTER_FENCE, 2)
    if len(parts) < 3:
        return {}, text

    _, raw, body = parts
    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}, text

    if not isinstance(loaded, dict):
        return {}, text
    return loaded, body.lstrip("\n")


def render_frontmatter(properties: dict[str, Any]) -> str:
    """Render a properties mapping as an Obsidian frontmatter block."""
    ordered = [k for k in _KEY_ORDER if k in properties]
    ordered += [k for k in properties if k not in _KEY_ORDER]

    lines = [FRONTMATTER_FENCE]
    for key in ordered:
        lines.extend(_render_entry(key, properties[key]))
    lines.append(FRONTMATTER_FENCE)
    return "\n".join(lines)


def _render_entry(key: str, value: Any) -> list[str]:
    if isinstance(value, list):
        if not value:
            return []
        return [f"{key}:", *(f"  - {_scalar(item)}" for item in value)]
    if value is None or value == "":
        return []
    return [f"{key}: {_scalar(value)}"]


def _scalar(value: Any) -> str:
    """Render one scalar, quoting only when YAML would otherwise misread it."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)
    needs_quotes = (
        text == ""
        or text[0] in "!&*[]{}>|%@`\"'#-?:,"
        or ": " in text
        or text.strip() != text
        or text.lower() in {"true", "false", "null", "yes", "no", "on", "off"}
    )
    if needs_quotes:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def compose(properties: dict[str, Any], body: str) -> str:
    """Assemble a complete note file from properties and a Markdown body."""
    return f"{render_frontmatter(properties)}\n\n{body.strip()}\n"


def callout(text: str, kind: str = "summary") -> str:
    """Render an Obsidian callout block.

    Used for the one-line summary so it stands out above the body and is
    collapsible in reading view.
    """
    lines = text.strip().splitlines() or [""]
    rendered = "\n".join(f"> {line}" if line else ">" for line in lines)
    return f"> [!{kind}]\n{rendered}"


def wiki_links(titles: list[str]) -> str:
    """Render a bullet list of Obsidian wiki links."""
    return "\n".join(f"- [[{title}]]" for title in titles)


def excerpt(body: str, limit: int) -> str:
    """Take a readable one-line excerpt from a note body.

    Headings, callout markers, and images are dropped so a search result reads
    as prose rather than as fragments of Markdown scaffolding.
    """
    kept: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "![", "---")):
            continue
        if line.startswith("> [!") or line == ">":
            continue
        kept.append(line.lstrip(">-*+ ").strip())

    text = " ".join(" ".join(kept).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"
