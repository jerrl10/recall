"""Search over the vault.

There is no index. Every query walks the Recall folder and scores notes in
memory, which keeps the vault the single source of truth and leaves nothing to
rebuild or invalidate. A personal knowledge base is small enough that this
stays comfortably fast; if it ever stops being fast, that is the signal to add
a cache, not a reason to have started with one.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from . import markdown
from .config import Settings
from .models import NoteKind, SearchHit
from .slug import title_from_filename
from .vault import Vault

_WORD = re.compile(r"[a-z0-9]+")

#: Field weights. A title match is a much stronger signal of aboutness than a
#: passing mention in the body.
_W_TITLE = 6.0
_W_TAGS = 3.0
_W_SUMMARY = 2.0
_W_BODY = 1.0

#: Words too common to carry signal. Kept small on purpose — an aggressive
#: stoplist would discard real query terms like "how" in "how retries work".
_STOPWORD_SOURCE = """
a an the and or but if then than that this these those of in on at to for
from by with as is are was were be been being it its do does did how what
when where why which who i you we they not no yes can could should would
"""

_STOPWORDS = frozenset(_STOPWORD_SOURCE.split())


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, stopwords removed."""
    return [word for word in _WORD.findall(text.lower()) if word not in _STOPWORDS]


class Search:
    """Ranked lexical search across the vault."""

    def __init__(self, vault: Vault, settings: Settings) -> None:
        self.vault = vault
        self.settings = settings

    def query(
        self,
        text: str,
        *,
        limit: int | None = None,
        kinds: list[NoteKind] | None = None,
        tags: list[str] | None = None,
        project: str | None = None,
    ) -> list[SearchHit]:
        """Return notes relevant to a natural-language query, best first."""
        terms = tokenize(text)
        documents = list(self._collect(kinds, tags, project))

        if not documents:
            return []
        if not terms:
            # No usable query terms: fall back to most recently updated, so the
            # caller still gets a useful window into the vault.
            documents.sort(key=lambda doc: str(doc["updated"]), reverse=True)
            return [self._to_hit(doc, 0.0) for doc in documents[: self._limit(limit)]]

        frequencies = self._document_frequencies(documents, terms)
        total = len(documents)

        scored: list[tuple[float, dict[str, Any]]] = []
        for document in documents:
            score = self._score(document, terms, frequencies, total)
            if score > 0:
                scored.append((score, document))

        scored.sort(key=lambda pair: (-pair[0], pair[1]["title"].lower()))
        return [self._to_hit(doc, score) for score, doc in scored[: self._limit(limit)]]

    # ------------------------------------------------------------------

    def _limit(self, limit: int | None) -> int:
        return limit or self.settings.max_search_results

    def _collect(
        self,
        kinds: list[NoteKind] | None,
        tags: list[str] | None,
        project: str | None,
    ) -> list[dict[str, Any]]:
        wanted_kinds = {kind.value for kind in kinds} if kinds else None
        wanted_tags = {tag.lower().lstrip("#") for tag in tags} if tags else None

        documents: list[dict[str, Any]] = []
        for path, properties, body in self.vault.iter_notes():
            kind_value = str(properties.get("kind", "")) or _kind_from_path(path.parent.name)
            if wanted_kinds and kind_value not in wanted_kinds:
                continue

            note_tags = _as_list(properties.get("tags"))
            if wanted_tags and not wanted_tags & {tag.lower() for tag in note_tags}:
                continue

            note_projects = _as_list(properties.get("projects"))
            if project and project.lower() not in {p.lower() for p in note_projects}:
                continue

            title = str(properties.get("title") or title_from_filename(path.name))
            documents.append(
                {
                    "path": path,
                    "title": title,
                    "kind": kind_value,
                    "tags": note_tags,
                    "summary": _summary_of(body),
                    "body": body,
                    "updated": properties.get("updated", ""),
                    "tokens": {
                        "title": Counter(tokenize(title)),
                        "tags": Counter(tokenize(" ".join(note_tags))),
                        "summary": Counter(tokenize(_summary_of(body))),
                        "body": Counter(tokenize(body)),
                    },
                }
            )
        return documents

    @staticmethod
    def _document_frequencies(documents: list[dict[str, Any]], terms: list[str]) -> dict[str, int]:
        """How many notes contain each term, for inverse-document weighting."""
        frequencies: dict[str, int] = {}
        for term in set(terms):
            frequencies[term] = sum(
                1
                for document in documents
                if any(term in field for field in document["tokens"].values())
            )
        return frequencies

    @staticmethod
    def _score(
        document: dict[str, Any],
        terms: list[str],
        frequencies: dict[str, int],
        total: int,
    ) -> float:
        """Weighted term overlap, damped by term commonness and note length.

        A term appearing in most notes says little about which note is
        relevant, so it is discounted; long notes are normalised so they do
        not outrank short precise ones purely by having more words.
        """
        fields = document["tokens"]
        length = max(sum(fields["body"].values()), 1)
        normalizer = 1.0 / (1.0 + math.log1p(length / 200.0))

        score = 0.0
        for term in set(terms):
            appearances = frequencies.get(term, 0)
            if appearances == 0:
                continue
            idf = math.log(1.0 + total / appearances)

            hits = (
                _W_TITLE * _presence(fields["title"], term)
                + _W_TAGS * _presence(fields["tags"], term)
                + _W_SUMMARY * _presence(fields["summary"], term)
                + _W_BODY * min(fields["body"][term], 3) * normalizer
            )
            score += hits * idf
        return round(score, 4)

    def _to_hit(self, document: dict[str, Any], score: float) -> SearchHit:
        return SearchHit(
            title=document["title"],
            kind=_safe_kind(document["kind"]),
            path=document["path"],
            score=score,
            excerpt=markdown.excerpt(document["body"], self.settings.excerpt_chars),
            tags=document["tags"],
        )


def _presence(counter: Counter[str], term: str) -> float:
    """Saturating count — a second mention in a title adds little."""
    count = counter[term]
    return 0.0 if count == 0 else 1.0 + 0.25 * min(count - 1, 2)


def _summary_of(body: str) -> str:
    """Extract the callout summary, falling back to the opening prose."""
    lines = [line.strip() for line in body.splitlines()]
    quoted = [
        line.lstrip("> ").strip()
        for line in lines
        if line.startswith(">") and not line.startswith("> [!")
    ]
    if quoted:
        return " ".join(quoted)
    for line in lines:
        if line and not line.startswith(("#", ">", "-", "*")):
            return line
    return ""


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _kind_from_path(folder: str) -> str:
    for kind in NoteKind:
        if kind.folder == folder:
            return kind.value
    return ""


def _safe_kind(value: str) -> NoteKind:
    try:
        return NoteKind(value)
    except ValueError:
        return NoteKind.CONCEPT
