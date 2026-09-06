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

Exact-title merge is backed by a near-duplicate guard. A capture whose title is
near-identical to an existing one — differing only by case, plurals, word order,
punctuation, or accents — is refused, and the matches are returned so the client
can reuse that title instead. `allow_similar=true` overrides it when the subject
really is different.

That covers wording variants. Synonyms — "Retry policy" and "Backoff strategy"
naming one subject — are handled separately and more weakly: on a create,
capture queries the vault with the new note's own title, summary, and tags, and
returns any content matches as `related_notes`. Bodies carry the vocabulary
short titles omit, so the overlap is usually visible even when the titles share
no words.

That advises rather than blocks. Content overlap is common between genuinely
distinct notes, so refusing on it would block far more good writes than bad
ones; the client is told what overlaps and decides whether to merge under the
existing title or link the two.

## Consequences

Positive:

- capturing twice is safe, so the client is never punished for being eager
- notes accrete detail over time instead of resetting
- user edits and captured material coexist in one file

Negative:

- a long-lived note grows a tail of dated update sections and eventually wants
  manual consolidation
- the title guard costs a round trip when it fires
- synonym detection only advises, so a determined client can still create
  a second note on one subject

## Revisit when

Update tails become tedious in practice. The likely answer is a consolidation
command that asks the client to rewrite a note's sections into clean prose —
still client-side reasoning, still no LLM in the server.
