# ADR-0001: Markdown is the source of truth

## Status

Accepted, 2026-09-05. Supersedes an earlier decision that made SQLite
authoritative and Obsidian a projection of it.

## Context

Recall stores engineering knowledge that a user reads, edits, and links inside
Obsidian. Two arrangements were possible:

1. a database owns the state and Markdown is rendered from it;
2. Markdown owns the state and any index is derived from it.

The earlier design chose (1), for good reasons: real identifiers, foreign keys,
atomic multi-record updates, and a full-text index give stronger integrity and
better retrieval than files can.

It carried one consequence that turned out to be disqualifying. If the database
is authoritative and notes are re-rendered from it, then **a note edited by hand
in Obsidian is overwritten on the next update.** For a personal knowledge base
that the user opens daily, silently discarding their own edits is not an
acceptable failure mode.

## Decision

Markdown files in the user's vault are the source of truth. There is no
database.

Search reads the vault directly and ranks in memory. Nothing is cached, so
nothing can fall out of step with the files.

## Consequences

Positive:

- hand-edits always survive; the user and the tool are peers, not writer and reader
- the vault is fully portable — Recall can be deleted and every note still opens
- no schema, no migrations, no index rebuild, no divergence to reconcile
- the whole product is inspectable with `ls` and a text editor

Negative:

- ranking is weaker than a real full-text index would provide
- YAML frontmatter is effectively the schema, so a malformed hand-edit is a data
  problem; parsing is deliberately lenient to contain this
- search cost grows with vault size, since every query scans

## Revisit when

Search latency becomes noticeable in normal use — roughly a few thousand notes.
The fix then is a derived, rebuildable index that the vault remains
authoritative over. It is not a reason to reverse this decision.
