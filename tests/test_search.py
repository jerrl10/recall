"""Ranking must be sensible, filterable, and deterministic."""

from __future__ import annotations

from recall.models import Note, NoteKind
from recall.search import Search, tokenize
from recall.vault import Vault


def seed(vault: Vault, **overrides: object) -> None:
    defaults: dict[str, object] = {
        "title": "A note",
        "kind": NoteKind.CONCEPT,
        "summary": "A summary.",
        "body": "Body text.",
    }
    vault.write_note(Note.model_validate(defaults | overrides))


def test_tokenize_drops_stopwords_and_punctuation() -> None:
    assert tokenize("How does the Queue work?") == ["queue", "work"]


def test_a_title_match_outranks_a_body_mention(vault: Vault, search: Search) -> None:
    seed(vault, title="Visibility timeout", body="Unrelated prose.")
    seed(vault, title="Something else", body="A passing mention of visibility timeout.")

    hits = search.query("visibility timeout")
    assert next(hit.title for hit in hits) == "Visibility timeout"


def test_a_tag_match_is_found(vault: Vault, search: Search) -> None:
    seed(vault, title="Untitled subject", tags=["kubernetes"])
    assert [hit.title for hit in search.query("kubernetes")] == ["Untitled subject"]


def test_notes_without_any_query_term_are_excluded(vault: Vault, search: Search) -> None:
    seed(vault, title="Queues")
    seed(vault, title="Completely unrelated")
    assert [hit.title for hit in search.query("queues")] == ["Queues"]


def test_an_empty_query_returns_recent_notes_rather_than_nothing(
    vault: Vault, search: Search
) -> None:
    seed(vault, title="One")
    seed(vault, title="Two")
    assert len(search.query("the and of")) == 2


def test_results_are_capped(vault: Vault, search: Search) -> None:
    for index in range(12):
        seed(vault, title=f"Queue note {index}")
    assert len(search.query("queue", limit=5)) == 5


def test_ranking_is_deterministic(vault: Vault, search: Search) -> None:
    for index in range(6):
        seed(vault, title=f"Queue {index}", body="identical body text")
    runs = [[hit.title for hit in search.query("queue")] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


class TestFilters:
    def test_by_kind(self, vault: Vault, search: Search) -> None:
        seed(vault, title="Queue concept", kind=NoteKind.CONCEPT)
        seed(vault, title="Queue lesson", kind=NoteKind.LESSON)
        hits = search.query("queue", kinds=[NoteKind.LESSON])
        assert [hit.title for hit in hits] == ["Queue lesson"]

    def test_by_tag(self, vault: Vault, search: Search) -> None:
        seed(vault, title="Queue one", tags=["azure"])
        seed(vault, title="Queue two", tags=["aws"])
        hits = search.query("queue", tags=["azure"])
        assert [hit.title for hit in hits] == ["Queue one"]

    def test_by_project(self, vault: Vault, search: Search) -> None:
        seed(vault, title="Queue one", projects=["recall"])
        seed(vault, title="Queue two", projects=["other"])
        hits = search.query("queue", project="recall")
        assert [hit.title for hit in hits] == ["Queue one"]


def test_hits_carry_an_excerpt_and_a_link(vault: Vault, search: Search) -> None:
    seed(vault, title="Visibility timeout", summary="Hidden, not deleted.")
    hit = search.query("visibility")[0]

    assert hit.wiki_link == "[[Visibility timeout]]"
    assert "Hidden, not deleted." in hit.excerpt
    assert "[!summary]" not in hit.excerpt
    assert hit.score > 0


def test_a_hand_written_note_without_frontmatter_is_still_searchable(
    vault: Vault, search: Search
) -> None:
    folder = vault.settings.root_path / "Concepts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Handwritten.md").write_text("# Handwritten\n\nAbout queues.", encoding="utf-8")

    assert [hit.title for hit in search.query("queues")] == ["Handwritten"]
