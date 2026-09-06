# Contributing to Recall

Thanks for taking an interest. This is a small, opinionated project — the
guidance below is mostly about what it deliberately is *not*, so you don't
spend effort on something that gets turned down for architectural reasons.

## Before you start

For anything beyond a bug fix or a typo, **open an issue first**. Recall has a
few load-bearing constraints (below) and it's a poor use of your time to
discover one of them in review.

## Setup

```bash
git clone https://github.com/jerrl10/recall.git
cd recall
uv sync
```

Run everything CI runs:

```bash
uv run ruff format .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Optionally, install the pre-commit hooks so those run before each commit:

```bash
uv run pre-commit install
```

To try changes against a real vault:

```bash
python scripts/demo_vault.py /tmp/recall-demo
RECALL_VAULT_PATH=/tmp/recall-demo uv run recall
```

## The constraints

These are the ones that will get a PR rejected on principle, not on quality.
Each has a documented reason; if you think one is wrong, argue with the reason
rather than working around it.

**Markdown is the source of truth.** No database, no persistent index. Search
scans the vault and ranks in memory. There's an in-process memo keyed on
`(mtime, size)` — extend that before reaching for storage.
See [ADR-0001](docs/decisions/0001-markdown-is-the-source-of-truth.md).

**Nothing is ever destroyed.** Capture merges into existing notes; archive
moves rather than deletes. Some of what is in a vault was written by the user
by hand, and an autonomous agent must not be able to destroy it.
See [ADR-0002](docs/decisions/0002-capture-merges-instead-of-overwriting.md).

**No LLM in the server.** No network calls, no API key, no provider SDK. The
client already has the conversation and does the reasoning; Recall does
storage, structure, and retrieval. This is what makes it usable from any
assistant.

**Never write to stdout.** It carries the MCP protocol — one stray `print`
corrupts the stream and takes the session down. Diagnostics go through
`recall.log`, which writes to stderr.

**Note content is never logged.** A vault holds the user's own engineering
notes; a log file is an easier place to leak them from than the vault.

**MCP handlers stay thin.** `server.py` validates, delegates, and returns. No
Markdown construction, no ranking, no path logic — those live in `vault.py`,
`search.py`, and `slug.py`.

## Changing the tool surface

The six tools are a public contract. `tests/test_server.py` asserts the set
exactly, so adding or renaming one fails CI until you update the test — which
is the point. A contract change needs the test, the README table, and the
canonical skill in `ai/` all updated together.

## Changing the workflows

`ai/` holds the one true copy of the skill and commands. Provider directories
(`.claude/`, `.opencode/`, `.codex/`) are **generated** — edit `ai/`, then run:

```bash
python scripts/install.py claude
```

A PR that edits a generated file directly will be asked to move the change
upstream.

## Tests

Every bug fix ships with a test that fails before it and passes after. New
behaviour ships with tests for the failure paths, not just the happy one.

Tests run against temporary vaults only. Nothing in the suite may touch a real
Obsidian vault or the home directory.

Protocol tests (`tests/test_protocol.py`) launch the server as a subprocess and
drive it with a real MCP client. They're marked `protocol` and run as a
separate CI step; `pytest -m "not protocol"` skips them locally if you want a
faster loop.

## Commits

One logical change per commit. The message should explain **why**, not restate
the diff — a reader six months from now needs the reasoning, and can read the
code for the mechanics.

## Architecture decisions

If a change alters something structural, add an ADR under `docs/decisions/`
following the existing format: context, decision, consequences (positive *and*
negative), and what would make you revisit it.

## Reporting bugs

Include your OS, Python version, MCP client, and the relevant stderr output.
Set `RECALL_LOG_LEVEL=DEBUG` for more. Please don't paste note content — a
title and a description of the shape is enough.
