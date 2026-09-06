# Recall

[![CI](https://github.com/jerrl10/recall/actions/workflows/ci.yml/badge.svg)](https://github.com/jerrl10/recall/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

**Durable engineering memory for AI coding assistants.**

You solve a hard problem with an AI assistant on Tuesday. On Friday the context
window is gone, the session is closed, and the reasoning went with it.

Recall is an [MCP](https://modelcontextprotocol.io/) server that turns those
conversations into structured notes in your Obsidian vault — and hands them
back to your assistant the next time they matter.

```text
you: "this visibility timeout thing is important — save it"
       │
       ▼
  /learn  ──▶  Recall MCP  ──▶  Obsidian vault
                                 ├── Concepts/Visibility Timeout.md
                                 └── Daily/2026-09-05.md
       │
       ▼
  next session: /recall  ──▶  the knowledge is back in context
```

Built for **Claude Code**, **Codex**, and **OpenCode** from one shared
configuration. *(Verified end-to-end on Claude Code; see
[provider support](#provider-support).)*

---

## Why

Most AI memory tools store conversation history. Recall stores *conclusions*.

- **Your notes, your files.** Plain Markdown in your own Obsidian vault. No
  database, no lock-in, no service. Delete Recall tomorrow and every note still
  opens.
- **Structured, not dumped.** Each note is classified, templated by kind, tagged,
  cross-linked, and logged to a daily timeline.
- **Merges instead of duplicating.** Capturing the same subject twice extends
  the existing note rather than scattering near-duplicates across the vault.
- **Provider-neutral.** One canonical skill and command set, installed into
  whichever assistants you use.
- **No LLM inside the server.** Your assistant already has the conversation and
  does the reasoning. Recall does storage, structure, and retrieval — so it
  needs no API key and makes no network calls.

## What a captured note looks like

````markdown
---
title: Azure Storage Queue visibility timeout
kind: concept
created: 2026-09-05
updated: 2026-09-05
tags:
  - azure
  - queue
  - distributed-systems
projects:
  - recall
source: claude-code
---

# Azure Storage Queue visibility timeout

> [!summary]
> A dequeued message is hidden from other consumers for a set window,
> not deleted.

## How it works

Dequeue hides the message for the visibility timeout. Delete it explicitly
or it reappears.

## Gotchas

Slow consumers cause duplicate processing.

## Related

- [[Idempotency]]
````

Obsidian-native throughout: frontmatter properties, callouts, wiki links, tags.

---

## Install

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and an existing
Obsidian vault.

```bash
git clone https://github.com/jerrl10/recall.git
cd recall
uv sync
```

Then install into your assistant — run this from the project you want memory in:

```bash
# Claude Code
python scripts/install.py claude --vault ~/Documents/Obsidian/MyVault

# Codex
python scripts/install.py codex --vault ~/Documents/Obsidian/MyVault

# OpenCode
python scripts/install.py opencode --vault ~/Documents/Obsidian/MyVault

# or all three
python scripts/install.py all --vault ~/Documents/Obsidian/MyVault
```

Add `--dry-run` to see exactly what would be written first. Existing MCP
configuration is merged, never overwritten — a config that already registers
`recall` is left untouched.

Restart your assistant, then confirm the connection by asking it to run
`vault_health`.

### Provider support

One canonical skill and command set in `ai/` is rendered into each assistant's
native layout, so the workflows cannot drift apart.

| Provider | Status | MCP config | Commands |
| --- | --- | --- | --- |
| Claude Code | Verified end-to-end, in daily use | `.mcp.json` | `.claude/commands/` |
| Codex | Config generated and installer tested; not yet exercised against a live session | `.codex/config.toml` | `~/.codex/prompts/` *(global only)* |
| OpenCode | Config generated and installer tested; not yet exercised against a live session | `opencode.json` | `.opencode/commands/` |

Config formats follow each vendor's current documentation, and the installer is
covered by CI. If you run Recall on Codex or OpenCode, reports are welcome.

## Use

| Command | Does |
| --- | --- |
| `/learn` | Extract everything worth keeping from this conversation |
| `/recall` | Pull relevant prior knowledge back into context |
| `/decision` | Record an architectural decision and its trade-offs |
| `/lesson` | Record a debugging or operational lesson |

Or just say it: *"this is worth remembering — save it to my notes."* The skill
picks it up.

## Vault layout

```text
YourVault/
└── Recall/
    ├── Concepts/     mechanisms, terminology, reusable ideas
    ├── Decisions/    choices made, and what they rule out
    ├── Lessons/      what broke, why, and the fix
    ├── Questions/    open threads worth returning to
    ├── Projects/     durable per-project context
    └── Daily/        dated log linking each day's captures
```

Topic notes hold the knowledge; the daily log gives you the timeline. Recall
only ever writes beneath its own folder.

## Configuration

Set via environment or a `.env` file — see [`.env.example`](.env.example).

| Variable | Default | Purpose |
| --- | --- | --- |
| `RECALL_VAULT_PATH` | *required* | Path to your Obsidian vault |
| `RECALL_ROOT` | `Recall` | Folder inside the vault that Recall owns |
| `RECALL_DAILY_FOLDER` | `Daily` | Subfolder for dated logs |
| `RECALL_MAX_SEARCH_RESULTS` | `10` | Default result cap |
| `RECALL_EXCERPT_CHARS` | `320` | Search excerpt length |
| `RECALL_CONTEXT_CHAR_BUDGET` | `8000` | Hard cap on text `note_context` returns |

Recall creates its own folder inside an existing vault. It never creates a
vault, and never writes outside `RECALL_ROOT`.

## MCP tools

| Tool | Purpose |
| --- | --- |
| `note_capture` | Write a note, or fold new material into an existing one |
| `note_search` | Ranked search across the vault, with excerpts |
| `note_read` | Read one note in full |
| `note_context` | Assemble relevant prior knowledge for the current task |
| `vault_health` | Verify configuration, reachability, and note counts |

## How it works

Markdown files are the source of truth. There is no database and no index to
rebuild — every search walks the vault and ranks in memory, so a note you edit
by hand in Obsidian is simply the current state.

That is a deliberate trade: ranked search is weaker than a real index would
give, in exchange for a vault that is fully portable, hand-editable, and
outlives the tool. See [`docs/decisions/`](docs/decisions/) for the reasoning,
and [`docs/architecture.md`](docs/architecture.md) for the module map.

## Development

```bash
uv sync
uv run ruff format .
uv run ruff check .
uv run mypy src
```

Contributor guidance lives in [CLAUDE.md](CLAUDE.md).

## Status

Working and in daily use on Claude Code. CI covers formatting, types, and
smoke checks over capture, merge, search, context, and the installer; a proper
unit test suite is the next piece of work, followed by verifying the Codex and
OpenCode paths against live sessions.

## License

MIT © Chang Liu
