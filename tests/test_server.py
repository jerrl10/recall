"""The MCP surface: tool contract, error shape, and end-to-end behaviour."""

from __future__ import annotations

import asyncio
from typing import Any

from recall.server import mcp

EXPECTED_TOOLS = {
    "note_capture",
    "note_search",
    "note_read",
    "note_context",
    "note_archive",
    "vault_health",
}


def test_the_tool_surface_is_exactly_what_is_documented() -> None:
    """A change here is a breaking contract change — update the README too."""
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert names == EXPECTED_TOOLS


def test_capture_documents_the_structure_for_each_kind() -> None:
    tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "note_capture")
    assert tool.description is not None
    for kind in ("concept", "decision", "lesson", "question", "project"):
        assert kind in tool.description


class TestCapture:
    async def test_a_note_is_written_and_linked_from_the_daily_log(self, call: Any) -> None:
        result = await call(
            "note_capture",
            title="Visibility timeout",
            kind="concept",
            summary="Hidden, not deleted.",
            body="## How it works\n\nDetail.",
            tags=["azure"],
        )

        assert result["ok"] is True
        assert result["action"] == "created"
        assert result["wiki_link"] == "[[Visibility timeout]]"
        assert result["relative_path"] == "Recall/Concepts/Visibility timeout.md"
        assert result["daily_note"] is not None

    async def test_the_same_title_updates_instead_of_duplicating(self, call: Any) -> None:
        await call("note_capture", title="Queues", kind="concept", summary="One.")
        again = await call("note_capture", title="Queues", kind="concept", summary="Two.")
        assert again["action"] == "updated"

    async def test_a_near_identical_title_is_refused_with_the_match(self, call: Any) -> None:
        """The dedup guarantee: a subject must not split across two notes."""
        await call("note_capture", title="Queue timeout", kind="concept", summary="One.")
        result = await call("note_capture", title="Queue timeouts", kind="concept", summary="Two.")

        assert result["ok"] is False
        assert result["similar"][0]["title"] == "Queue timeout"
        assert result["similar"][0]["wiki_link"] == "[[Queue timeout]]"
        assert "allow_similar" in result["hint"]

    async def test_the_refused_note_was_not_written(self, call: Any) -> None:
        await call("note_capture", title="Queue timeout", kind="concept", summary="One.")
        await call("note_capture", title="Queue timeouts", kind="concept", summary="Two.")
        assert (await call("vault_health"))["note_counts"]["concept"] == 1

    async def test_allow_similar_overrides_the_guard(self, call: Any) -> None:
        await call("note_capture", title="Queue timeout", kind="concept", summary="One.")
        result = await call(
            "note_capture",
            title="Queue timeouts",
            kind="concept",
            summary="Two.",
            allow_similar=True,
        )
        assert result["ok"] is True
        assert result["action"] == "created"

    async def test_an_exact_title_still_merges_rather_than_being_refused(self, call: Any) -> None:
        """The guard must not block the normal extend-an-existing-note path."""
        await call("note_capture", title="Queue timeout", kind="concept", summary="One.")
        result = await call("note_capture", title="Queue timeout", kind="concept", summary="Two.")
        assert result["ok"] is True
        assert result["action"] == "updated"

    async def test_an_unrelated_title_is_not_blocked(self, call: Any) -> None:
        await call("note_capture", title="Queue timeout", kind="concept", summary="One.")
        result = await call("note_capture", title="Circuit breaker", kind="concept", summary="Two.")
        assert result["ok"] is True

    async def test_the_daily_log_can_be_skipped(self, call: Any) -> None:
        result = await call(
            "note_capture", title="Quiet", kind="concept", summary="s", log_to_daily=False
        )
        assert result["daily_note"] is None


class TestValidation:
    """Regression: these used to escape as opaque tool errors."""

    async def test_a_blank_title_names_the_offending_field(self, call: Any) -> None:
        result = await call("note_capture", title="   ", kind="concept", summary="s")
        assert result["ok"] is False
        assert result["invalid_fields"][0]["field"] == "title"

    async def test_an_over_long_title_is_reported(self, call: Any) -> None:
        result = await call("note_capture", title="x" * 300, kind="concept", summary="s")
        assert result["ok"] is False
        assert "120" in result["error"]

    async def test_an_empty_summary_is_reported(self, call: Any) -> None:
        result = await call("note_capture", title="Fine", kind="concept", summary="")
        assert result["ok"] is False
        assert result["invalid_fields"][0]["field"] == "summary"


class TestSearch:
    async def test_results_are_ranked_pointers_not_whole_notes(self, call: Any) -> None:
        await call(
            "note_capture",
            title="Visibility timeout",
            kind="concept",
            summary="Hidden.",
            body="## How it works\n\n" + "detail " * 200,
        )
        result = await call("note_search", query="visibility timeout")

        assert result["count"] == 1
        hit = result["results"][0]
        assert set(hit) >= {"title", "kind", "wiki_link", "score", "excerpt"}
        assert len(hit["excerpt"]) < 500, "excerpt should not be the whole note"

    async def test_an_unmatched_query_returns_nothing(self, call: Any) -> None:
        await call("note_capture", title="Queues", kind="concept", summary="s")
        assert (await call("note_search", query="kubernetes"))["count"] == 0


class TestRead:
    async def test_a_note_is_returned_in_full(self, call: Any) -> None:
        await call("note_capture", title="Queues", kind="concept", summary="A summary.")
        result = await call("note_read", title="Queues")
        assert result["ok"] is True
        assert "A summary." in result["content"]

    async def test_a_missing_note_reports_cleanly(self, call: Any) -> None:
        result = await call("note_read", title="Nothing here")
        assert result["ok"] is False
        assert "Nothing here" in result["error"]


class TestContext:
    async def test_frontmatter_never_reaches_the_model(self, call: Any) -> None:
        """Regression: note_context used to return whole files, YAML included."""
        await call("note_capture", title="Queues", kind="concept", summary="s", tags=["azure"])
        result = await call("note_context", query="queues")

        assert "title:" not in result["context"]
        assert "kind: concept" not in result["context"]
        assert "# Queues" in result["context"]

    async def test_the_character_budget_is_enforced(self, call: Any, settings: Any) -> None:
        settings.context_char_budget = 400
        for index in range(5):
            await call(
                "note_capture",
                title=f"Queue note {index}",
                kind="concept",
                summary="s",
                body="detail " * 200,
            )
        result = await call("note_context", query="queue detail")

        assert len(result["context"]) <= 400 + 40, "budget overshoot beyond the truncation marker"
        assert result["truncated"] is True

    async def test_an_empty_vault_returns_an_empty_bundle(self, call: Any) -> None:
        result = await call("note_context", query="anything")
        assert result["count"] == 0
        assert result["context"] == ""


class TestHealth:
    async def test_it_reports_a_usable_vault(self, call: Any) -> None:
        result = await call("vault_health")
        assert result["ok"] is True
        assert result["vault_reachable"] is True
        assert result["writable"] is True

    async def test_counts_track_captures(self, call: Any) -> None:
        await call("note_capture", title="A concept", kind="concept", summary="s")
        await call("note_capture", title="A lesson", kind="lesson", summary="s")
        counts = (await call("vault_health"))["note_counts"]
        assert counts["concept"] == 1
        assert counts["lesson"] == 1
        assert counts["decision"] == 0

    async def test_no_filesystem_paths_are_exposed(self, call: Any) -> None:
        """Absolute paths leak the user's home directory to the client."""
        result = await call("vault_health")
        assert not any(isinstance(v, str) and v.startswith("/") for v in result.values())


class TestArchive:
    async def test_a_note_is_moved_not_deleted(self, call: Any, settings: Any) -> None:
        await call("note_capture", title="Wrong note", kind="concept", summary="Oops.")
        result = await call("note_archive", title="Wrong note")

        assert result["ok"] is True
        assert result["archived_to"] == "Recall/Archive/Concepts/Wrong note.md"
        assert (settings.vault_path / result["archived_to"]).exists()
        assert not (settings.root_path / "Concepts" / "Wrong note.md").exists()

    async def test_an_archived_note_leaves_search(self, call: Any) -> None:
        await call("note_capture", title="Queue thing", kind="concept", summary="About queues.")
        assert (await call("note_search", query="queues"))["count"] == 1

        await call("note_archive", title="Queue thing")
        assert (await call("note_search", query="queues"))["count"] == 0

    async def test_an_archived_note_leaves_context(self, call: Any) -> None:
        await call("note_capture", title="Queue thing", kind="concept", summary="About queues.")
        await call("note_archive", title="Queue thing")
        assert (await call("note_context", query="queues"))["count"] == 0

    async def test_archiving_twice_does_not_clobber(self, call: Any, settings: Any) -> None:
        for _ in range(2):
            await call("note_capture", title="Repeat", kind="concept", summary="s")
            await call("note_archive", title="Repeat")

        archived = list((settings.archive_path).rglob("*.md"))
        assert len(archived) == 2, "the second archive must not overwrite the first"

    async def test_a_missing_note_reports_cleanly(self, call: Any) -> None:
        result = await call("note_archive", title="Never existed")
        assert result["ok"] is False
        assert "Never existed" in result["error"]

    async def test_health_counts_archived_notes(self, call: Any) -> None:
        await call("note_capture", title="Gone", kind="concept", summary="s")
        await call("note_archive", title="Gone")
        counts = (await call("vault_health"))["note_counts"]
        assert counts["archived"] == 1
        assert counts["concept"] == 0
