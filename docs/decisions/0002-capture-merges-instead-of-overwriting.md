# ADR-0002: Capture merges instead of overwriting

## Status

Accepted, 2026-09-05.

## Context

The same subject comes up repeatedly. A user learns something about queue
semantics in one session and something more in another. Three options:

1. **overwrite** — the newest capture replaces the note;
2. **always create** — a second note, disambiguated by suffix or timestamp;
3. **merge** — fold the new material into the existing note.

Overwriting destroys prior knowledge, including anything the user wrote
themselves, which [ADR-0001](0001-markdown-is-the-source-of-truth.md) rules out.
Always creating produces the failure the project exists to prevent: a vault of
near-duplicates that nobody trusts and search cannot rank.

## Decision

`note_capture` keyed on title merges. When the target file already exists:

- new material is appended under a `## Update — YYYY-MM-DD` heading;
- `tags` and `projects` are unioned with what is already there;
- `updated` is refreshed, `created` is preserved;
- **nothing already in the file is removed or rewritten.**

The daily log records a note once per day regardless of how many times it was
touched.

Deduplication depends on the client searching before it writes. The skill and
every command instruct it to call `note_search` first and reuse an existing
title. This is a workflow guarantee, not one the server can enforce — the server
cannot tell whether two differently-titled notes are about the same thing.

## Consequences

Positive:

- capturing twice is safe, so the client is never punished for being eager
- notes accrete detail over time instead of resetting
- user edits and captured material coexist in one file

Negative:

- a long-lived note grows a tail of dated update sections and eventually wants
  manual consolidation
- merging is title-exact; a near-miss title still creates a second note

## Revisit when

Update tails become tedious in practice. The likely answer is a consolidation
command that asks the client to rewrite a note's sections into clean prose —
still client-side reasoning, still no LLM in the server.
