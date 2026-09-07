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


class TestParseCache:
    """The memo is keyed on (mtime, size), so a stale read is impossible."""

    def test_an_edit_on_disk_is_picked_up(self, vault: Vault) -> None:
        result = vault.write_note(make_note())
        list(vault.iter_notes())  # populate the memo
        text = result.path.read_text(encoding="utf-8").replace("Detail.", "Rewritten by hand.")
        result.path.write_text(text, encoding="utf-8")

        bodies = [body for _, _, body in vault.iter_notes()]
        assert any("Rewritten by hand." in body for body in bodies)

    def test_a_repeat_scan_does_not_reread_the_file(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vault.write_note(make_note())
        list(vault.iter_notes())

        reads = 0
        original = Path.read_text

        def counting(self: Path, *args: object, **kwargs: object) -> str:
            nonlocal reads
            reads += 1
            return original(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "read_text", counting)
        list(vault.iter_notes())
        assert reads == 0, "an unchanged note should be served from the memo"

    def test_writing_invalidates_the_memo(self, vault: Vault) -> None:
        vault.write_note(make_note())
        list(vault.iter_notes())

        vault.write_note(make_note(body="Second capture."))
        bodies = [body for _, _, body in vault.iter_notes()]
        assert any("Second capture." in body for body in bodies)

    def test_archiving_drops_the_note_from_iteration(self, vault: Vault) -> None:
        vault.write_note(make_note())
        list(vault.iter_notes())

        vault.archive("Visibility timeout")
        assert list(vault.iter_notes()) == []


class TestSearchScope:
    """Reading and writing are separate: search can cover the whole vault,
    but writes never leave the Recall folder."""

    def _pre_existing(self, vault: Vault) -> Path:
        """A note the user already had, outside Recall's folder."""
        folder = vault.settings.vault_path / "Engineering"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "Kafka rebalancing.md"
        path.write_text(
            "---\ntitle: Kafka rebalancing\ntags:\n  - kafka\n---\n\n"
            "# Kafka rebalancing\n\nConsumer group rebalance stops the world.\n",
            encoding="utf-8",
        )
        return path

    def test_recall_scope_ignores_the_rest_of_the_vault(self, vault: Vault) -> None:
        self._pre_existing(vault)
        vault.write_note(make_note())
        titles = [p.get("title") for _, p, _ in vault.iter_notes()]
        assert titles == ["Visibility timeout"]

    def test_vault_scope_finds_notes_recall_never_wrote(self, vault: Vault) -> None:
        self._pre_existing(vault)
        vault.write_note(make_note())
        vault.settings.search_scope = "vault"

        titles = {p.get("title") for _, p, _ in vault.iter_notes()}
        assert titles == {"Visibility timeout", "Kafka rebalancing"}

    def test_vault_scope_still_writes_only_inside_recall(self, vault: Vault) -> None:
        vault.settings.search_scope = "vault"
        result = vault.write_note(make_note())
        assert vault.settings.root_path in result.path.parents

    def test_excluded_folders_are_skipped_at_any_depth(self, vault: Vault) -> None:
        vault.settings.search_scope = "vault"
        for folder in ("Templates", ".trash", "Projects/Templates"):
            path = vault.settings.vault_path / folder / "Skip me.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Skip me\n\nqueue queue queue\n", encoding="utf-8")

        titles = [p.get("title") or path.stem for path, p, _ in vault.iter_notes()]
        assert "Skip me" not in titles

    def test_archived_and_daily_notes_stay_excluded_in_vault_scope(self, vault: Vault) -> None:
        vault.settings.search_scope = "vault"
        result = vault.write_note(make_note())
        vault.log_daily([result])
        vault.archive("Visibility timeout")

        assert list(vault.iter_notes()) == []

    def test_the_duplicate_guard_only_considers_notes_recall_owns(self, vault: Vault) -> None:
        """A note Recall did not write cannot be merged into, so blocking a
        capture against it would leave the client with no way forward."""
        self._pre_existing(vault)
        vault.settings.search_scope = "vault"
        assert vault.titles() == []

        vault.write_note(make_note())
        assert vault.titles() == ["Visibility timeout"]
