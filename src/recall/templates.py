"""Per-kind note structure.

Each kind of knowledge answers a different question, so each gets its own
section headings. The AI client is told this structure through the skill and
the tool description, and fills it in; Recall renders whatever arrives and
falls back to the skeleton when a body is empty.
"""

from __future__ import annotations

from .models import NoteKind

#: Canonical headings per kind, in order.
SECTIONS: dict[NoteKind, tuple[str, ...]] = {
    NoteKind.CONCEPT: ("How it works", "Why it matters", "Gotchas"),
    NoteKind.DECISION: ("Context", "Decision", "Consequences", "Alternatives considered"),
    NoteKind.LESSON: ("What happened", "Root cause", "Fix", "How to avoid it"),
    NoteKind.QUESTION: ("The question", "What we know", "Next step"),
    NoteKind.PROJECT: ("Overview", "Current state", "Open threads"),
}

#: One-line guidance shown to the model for each kind.
GUIDANCE: dict[NoteKind, str] = {
    NoteKind.CONCEPT: "A reusable idea, mechanism, or piece of terminology.",
    NoteKind.DECISION: "A choice that was actually made, and what it rules out.",
    NoteKind.LESSON: "Something that broke, why, and what fixed it.",
    NoteKind.QUESTION: "An open technical question worth returning to.",
    NoteKind.PROJECT: "Durable context about a specific project.",
}


def skeleton(kind: NoteKind) -> str:
    """Empty section scaffold for a kind, used when no body is supplied."""
    return "\n\n".join(f"## {heading}" for heading in SECTIONS[kind])


def structure_hint() -> str:
    """A compact description of every kind, for tool and skill documentation."""
    lines = []
    for kind in NoteKind:
        headings = " · ".join(SECTIONS[kind])
        lines.append(f"- **{kind.value}** — {GUIDANCE[kind]} Sections: {headings}")
    return "\n".join(lines)
