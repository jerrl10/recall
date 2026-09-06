"""Filenames must stay legal, stable, and matched to the recorded title."""

from __future__ import annotations

from pathlib import Path

import pytest

from recall.slug import MAX_STEM, display_title, note_filename, title_from_filename


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Visibility timeout", "Visibility timeout.md"),
        ("Azure/Storage: queues", "AzureStorage queues.md"),
        ("What is a [[link]]?", "What is a link.md"),
        ("  padded  spaces  ", "padded spaces.md"),
        ("Ünïcodé stays", "Ünïcodé stays.md"),
    ],
)
def test_illegal_characters_are_removed_but_titles_stay_readable(title: str, expected: str) -> None:
    assert note_filename(title) == expected


@pytest.mark.parametrize("title", ["../../escape", "..", "./.", "a/../../../b"])
def test_traversal_sequences_cannot_survive_into_a_filename(title: str) -> None:
    name = note_filename(title)
    assert "/" not in name and "\\" not in name
    assert not name.startswith(".")
    assert Path(name).name == name, "must be a bare filename, not a path"


@pytest.mark.parametrize("reserved", ["CON", "con", "PRN", "nul", "COM1", "lpt9"])
def test_windows_device_names_are_escaped(reserved: str) -> None:
    assert note_filename(reserved) == f"{reserved}-note.md"


def test_blank_and_punctuation_only_titles_get_a_placeholder() -> None:
    assert note_filename("...") == "Untitled.md"
    assert note_filename("///") == "Untitled.md"


def test_long_titles_are_truncated_without_a_trailing_dot() -> None:
    name = note_filename("x" * 400)
    assert len(name) == MAX_STEM + len(".md")
    assert not name.removesuffix(".md").endswith(".")


def test_display_title_matches_the_filename_stem() -> None:
    """Regression: frontmatter used to record the raw, unsanitised title."""
    for title in ["../../escape", "CON", "Normal Title", "a: b"]:
        assert f"{display_title(title)}.md" == note_filename(title)


def test_title_round_trips_through_the_filename() -> None:
    assert title_from_filename(note_filename("Visibility timeout")) == "Visibility timeout"
