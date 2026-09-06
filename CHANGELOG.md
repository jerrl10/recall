# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `note_archive` — withdraw a note captured in error. The file moves to
  `Recall/Archive/` and leaves search and context, but is never deleted.
- Near-duplicate title guard on `note_capture`: a title differing only by case,
  plurals, word order, punctuation, or accents is refused with the matches
  attached. `allow_similar=true` overrides it.
- `related_notes` on capture — existing notes whose *content* overlaps, which
  catches two different titles for one subject.
- Structured logging to stderr, configurable with `RECALL_LOG_LEVEL`. Note
  content is never logged.
- `RECALL_CONTEXT_CHAR_BUDGET` caps what `note_context` returns.
- Demo vault seeder (`scripts/demo_vault.py`).
- Test suite: 142 tests, including MCP protocol conformance against a real
  stdio subprocess.
- CI across Linux, macOS, and Windows on Python 3.12 and 3.13, with a coverage
  floor.

### Fixed

- The Codex installer destroyed existing MCP server configuration. It now
  appends, validates the result, and leaves an existing `recall` entry alone.
- The Codex installer generated invalid TOML on Windows, so installing there
  silently registered nothing.
- `note_context` returned raw YAML frontmatter and had no size limit.
- Invalid input to `note_capture` raised an opaque tool error instead of a
  structured response naming the field.
- The `note_capture` description shipped a literal `{structure}` placeholder,
  so the per-kind section guidance never reached any model.
- Frontmatter `title` could disagree with the filename and wiki link.
- Relative paths in tool output used the host's path separator.

## [0.1.0]

Initial working version: Markdown-first capture into an Obsidian vault, with
`note_capture`, `note_search`, `note_read`, `note_context`, and `vault_health`,
plus a shared skill and command set for Claude Code, Codex, and OpenCode.

[Unreleased]: https://github.com/jerrl10/recall/compare/main...HEAD
[0.1.0]: https://github.com/jerrl10/recall/releases/tag/v0.1.0
