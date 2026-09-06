"""Near-duplicate title detection.

Capture merges on an exact title match, which leaves a gap: "Queue timeout"
and "Queue timeouts" are the same subject but two files. Nothing in the server
can tell whether two differently-worded titles mean the same thing, so this
does the one comparison that is safe to automate — near-identical wording —
and leaves genuine judgement to the client.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

#: Above this, two titles are treated as naming the same subject.
DEFAULT_THRESHOLD = 0.85

_WORD = re.compile(r"[a-z0-9]+")


def normalize(title: str) -> frozenset[str]:
    """Reduce a title to comparable word stems.

    Case, punctuation, accents, word order, and simple plurals are all
    discarded, so "Queue Timeouts" and "timeout queue" compare as equal.
    """
    folded = unicodedata.normalize("NFKD", title.casefold())
    stripped = "".join(char for char in folded if not unicodedata.combining(char))
    return frozenset(_singular(word) for word in _WORD.findall(stripped))


def _singular(word: str) -> str:
    """Fold the common English plural endings, conservatively.

    Only endings that are unambiguous are trimmed; "status" and "bus" must not
    become "statu" and "bu".
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("es") and word[-3] in "sxzho":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def score(left: str, right: str) -> float:
    """How alike two titles are, from 0.0 to 1.0.

    Combines word overlap with character-level similarity so that both
    reordering ("timeout queue") and small edits ("visibilty") are caught.
    """
    left_words, right_words = normalize(left), normalize(right)
    if not left_words or not right_words:
        return 0.0
    if left_words == right_words:
        return 1.0

    overlap = len(left_words & right_words) / len(left_words | right_words)
    characters = SequenceMatcher(
        None, " ".join(sorted(left_words)), " ".join(sorted(right_words))
    ).ratio()
    return round(max(overlap, (overlap + characters) / 2), 4)


def find_similar(
    title: str,
    candidates: list[str],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[tuple[str, float]]:
    """Candidate titles close enough to be the same subject, best first."""
    matches = [
        (candidate, similarity)
        for candidate in candidates
        if (similarity := score(title, candidate)) >= threshold
    ]
    return sorted(matches, key=lambda pair: (-pair[1], pair[0].lower()))
