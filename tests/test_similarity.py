"""Near-duplicate detection must catch real variants without false alarms."""

from __future__ import annotations

import pytest

from recall.similarity import find_similar, normalize, score


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Queue timeout", "Queue timeouts"),
        ("Queue Timeout", "queue timeout"),
        ("Visibility timeout", "Timeout visibility"),
        ("Retry policies", "Retry policy"),
        ("Café latency", "Cafe latency"),
    ],
)
def test_wording_variants_of_one_subject_match(left: str, right: str) -> None:
    assert score(left, right) >= 0.85


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Queue timeout", "Queue ordering"),
        ("Azure Storage Queue", "AWS SQS"),
        ("Retry policy", "Circuit breaker"),
        ("Visibility timeout", "Connection timeout"),
    ],
)
def test_genuinely_different_subjects_do_not_match(left: str, right: str) -> None:
    assert score(left, right) < 0.85


def test_a_title_always_matches_itself() -> None:
    assert score("Anything at all", "Anything at all") == 1.0


def test_words_that_merely_end_in_s_are_not_stripped() -> None:
    """'status' must not fold to 'statu', or unrelated titles start matching."""
    assert normalize("status") == {"status"}
    assert normalize("bus") == {"bus"}
    assert normalize("analysis") == {"analysis"}


def test_matches_come_back_best_first() -> None:
    matches = find_similar(
        "Queue timeout",
        ["Queue timeouts", "Queue ordering", "Timeout queue", "Retry policy"],
    )
    assert [title for title, _ in matches] == ["Queue timeouts", "Timeout queue"]
    assert matches[0][1] >= matches[1][1]


def test_an_empty_candidate_list_matches_nothing() -> None:
    assert find_similar("Queue timeout", []) == []


def test_a_title_with_no_word_characters_matches_nothing() -> None:
    assert score("...", "Queue timeout") == 0.0
