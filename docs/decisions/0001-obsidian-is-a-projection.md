# ADR-0001: Obsidian is a projection, not the primary domain store

## Status

Accepted.

## Context

Recall requires structured IDs, reliable updates, search indexes, future provenance, and deterministic persistence. Markdown is excellent for humans but weaker as the sole machine-state representation.

## Decision

Use a structured local database as Recall's machine-facing state and project memories to Obsidian Markdown for human consumption.

The initial database is SQLite.

## Alternatives

### Obsidian-only storage

Simpler initially, but couples domain behavior to files and makes reliable identity, relations, indexing, and transactional updates harder.

### PostgreSQL immediately

Powerful but unnecessary operational overhead for the initial local, single-user product.

## Consequences

Positive:
- clean separation between domain and presentation
- easier future indexing and migration
- human-readable Obsidian notes remain available
- future storage adapters stay possible

Negative:
- projection consistency must be handled
- SQLite and Markdown can temporarily diverge if projection fails
