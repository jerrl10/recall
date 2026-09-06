"""Writing notes: structure, containment, merging, and the daily log."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from recall.models import Note, NoteKind
from recall.vault import Vault, VaultError


def make_note(**overrides: object) -> Note:
    defaults: dict[str, object] = {
        "title": "Visibility timeout",
        "kind": NoteKind.CONCEPT,
        "summary": "Hidden, not deleted.",
        "body": "## How it works\n\nDetail.",
    }
    return Note.model_validate(defaults | overrides)


def test_a_note_lands_in_the_folder_for_its_kind(vault: Vault) -> None:
    for kind, folder in [
        (NoteKind.CONCEPT, "Concepts"),
        (NoteKind.DECISION, "Decisions"),
        (NoteKind.LESSON, "Lessons"),
        (NoteKind.QUESTION, "Questions"),
        (NoteKind.PROJECT, "Projects"),
    ]:
        result = vault.write_note(make_note(kind=kind, title=f"Note {folder}"))
        assert result.path.parent.name == folder


def test_a_written_note_is_obsidian_shaped(vault: Vault) -> None:
    result = vault.write_note(make_note(tags=["Azure", "Queue"], related=["Idempotency"]))
    text = result.path.read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert "title: Visibility timeout" in text
    assert "> [!summary]" in text
    assert "# Visibility timeout" in text
    assert "[[Idempotency]]" in text
    assert "  - azure" in text, "tags should be normalised to lowercase"


def test_an_empty_body_falls_back_to_the_kind_skeleton(vault: Vault) -> None:
    result = vault.write_note(make_note(kind=NoteKind.DECISION, body=""))
    text = result.path.read_text(encoding="utf-8")
    for heading in ("## Context", "## Decision", "## Consequences"):
        assert heading in text


def test_writes_cannot_escape_the_recall_folder(vault: Vault) -> None:
    result = vault.write_note(make_note(title="../../escape"))
    assert vault.settings.root_path in result.path.parents


def test_guard_rejects_a_path_outside_the_root(vault: Vault, tmp_path: Path) -> None:
    with pytest.raises(VaultError):
        vault._guard(tmp_path / "elsewhere.md")


class TestMerge:
    """Capturing the same title again must never destroy what is on disk."""

    def test_second_capture_updates_rather_than_creating(self, vault: Vault) -> None:
        first = vault.write_note(make_note())
        second = vault.write_note(make_note(summary="More.", body="Max is seven days."))

        assert first.created is True
        assert second.created is False
        assert first.path == second.path

    def test_existing_content_survives(self, vault: Vault) -> None:
        result = vault.write_note(make_note())
        hand_edited = result.path.read_text(encoding="utf-8") + "\n\nA line I wrote myself.\n"
        result.path.write_text(hand_edited, encoding="utf-8")

        vault.write_note(make_note(body="New material."))
        text = result.path.read_text(encoding="utf-8")

        assert "A line I wrote myself." in text, "user edits must not be overwritten"
        assert "Detail." in text
        assert "New material." in text
        assert f"## Update — {date.today().isoformat()}" in text

    def test_tags_are_unioned_not_replaced(self, vault: Vault) -> None:
        vault.write_note(make_note(tags=["azure"]))
        result = vault.write_note(make_note(tags=["ops"]))
        text = result.path.read_text(encoding="utf-8")
        assert "  - azure" in text
        assert "  - ops" in text


class TestDailyLog:
    def test_captures_are_linked_from_the_daily_note(self, vault: Vault) -> None:
        result = vault.write_note(make_note())
        path = vault.log_daily([result])
        text = path.read_text(encoding="utf-8")

        assert path.name == f"{date.today().isoformat()}.md"
        assert "[[Visibility timeout]]" in text
        assert "new concept" in text

    def test_a_note_touched_twice_is_logged_once(self, vault: Vault) -> None:
        first = vault.write_note(make_note())
        vault.log_daily([first])
        second = vault.write_note(make_note(body="Again."))
        path = vault.log_daily([second])

        assert path.read_text(encoding="utf-8").count("[[Visibility timeout]]") == 1

    def test_daily_notes_are_excluded_from_iteration(self, vault: Vault) -> None:
        result = vault.write_note(make_note())
        vault.log_daily([result])
        titles = [properties.get("title") for _, properties, _ in vault.iter_notes()]
        assert titles == ["Visibility timeout"]


def test_body_of_omits_frontmatter(vault: Vault) -> None:
    """Regression: note_context used to feed raw YAML to the model."""
    result = vault.write_note(make_note())
    body = vault.body_of(result.path)
    assert "title:" not in body
    assert "# Visibility timeout" in body


def test_body_of_refuses_a_path_outside_the_root(vault: Vault, tmp_path: Path) -> None:
    (tmp_path / "outside.md").write_text("secret", encoding="utf-8")
    assert vault.body_of(tmp_path / "outside.md") == ""


def test_a_failed_write_leaves_no_temporary_files(
    vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: object, **__: object) -> None:
        raise OSError("disk full")

    result = vault.write_note(make_note())
    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError):
        vault.write_note(make_note(body="Second."))

    leftovers = list(result.path.parent.glob(".recall-*"))
    assert leftovers == []
