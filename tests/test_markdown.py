"""Frontmatter must survive a round trip, and tolerate files people edit."""

from __future__ import annotations

from datetime import date

import yaml

from recall import markdown


def test_properties_round_trip_through_yaml() -> None:
    properties = {
        "title": "Visibility timeout",
        "kind": "concept",
        "created": date(2026, 9, 6),
        "tags": ["azure", "queue"],
    }
    parsed, body = markdown.split_frontmatter(markdown.compose(properties, "# Heading\n\nText."))

    assert parsed["title"] == "Visibility timeout"
    assert parsed["tags"] == ["azure", "queue"]
    assert parsed["created"] == date(2026, 9, 6)
    assert body.startswith("# Heading")


def test_keys_are_written_in_a_stable_order() -> None:
    rendered = markdown.render_frontmatter(
        {"tags": ["b"], "title": "T", "kind": "concept", "zzz_custom": "x"}
    )
    keys = [line.split(":")[0] for line in rendered.splitlines() if ":" in line]
    assert keys[:3] == ["title", "kind", "tags"]
    assert keys[-1] == "zzz_custom", "unknown keys should be kept, not dropped"


def test_empty_values_are_omitted_rather_than_written_as_null() -> None:
    rendered = markdown.render_frontmatter({"title": "T", "tags": [], "source": None})
    assert "tags" not in rendered
    assert "source" not in rendered


def test_values_yaml_would_misread_are_quoted() -> None:
    for value in ["- dash start", "yes", "key: value", "#hash", " padded"]:
        rendered = markdown.render_frontmatter({"title": value})
        assert yaml.safe_load(rendered.strip("-\n"))["title"] == value


def test_malformed_frontmatter_degrades_to_no_properties() -> None:
    """Hand-edited notes must still load — the vault is the source of truth."""
    properties, body = markdown.split_frontmatter("---\n:::not: valid: yaml\n---\n\nBody.")
    assert properties == {}
    assert "Body." in body


def test_a_note_without_frontmatter_is_all_body() -> None:
    properties, body = markdown.split_frontmatter("# Just a heading\n\nText.")
    assert properties == {}
    assert body.startswith("# Just a heading")


def test_frontmatter_that_is_a_list_is_ignored() -> None:
    properties, _ = markdown.split_frontmatter("---\n- a\n- b\n---\n\nBody.")
    assert properties == {}


def test_callout_renders_a_collapsible_summary() -> None:
    assert markdown.callout("One line.") == "> [!summary]\n> One line."


def test_excerpt_strips_markdown_scaffolding() -> None:
    body = "# Title\n\n> [!summary]\n> The point.\n\n## Section\n\n- a bullet"
    excerpt = markdown.excerpt(body, 200)
    assert "[!summary]" not in excerpt
    assert "#" not in excerpt
    assert "The point." in excerpt
    assert "a bullet" in excerpt


def test_excerpt_respects_its_limit() -> None:
    excerpt = markdown.excerpt("word " * 200, 50)
    assert len(excerpt) <= 51
    assert excerpt.endswith("…")
