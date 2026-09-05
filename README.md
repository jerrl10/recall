# Recall

A local-first MCP server that turns AI-assisted engineering conversations into durable, structured engineering knowledge — and makes that knowledge retrievable in future AI sessions.

Recall is not an Obsidian automation tool and not an LLM application. Your AI client (Claude Code, OpenCode, Codex) already understands the conversation and decides what is worth remembering. Recall stores it, indexes it, tracks its lifecycle, and projects it into readable Markdown.

## How it works

```text
AI client session
        ↓  /learn
Recall MCP tools
        ↓
SQLite  (authoritative state + FTS5 search)
        ↓
Obsidian Markdown  (human-readable projection)

        ↑  memory_context
   next session reads it back
```

- **SQLite is the source of truth.** A memory's identity is a UUIDv7, never a filename.
- **Obsidian is a projection.** Files are re-rendered from authoritative state; a failed write never corrupts a committed memory.
- **No LLM inside the server.** No API key, no provider dependency, no network.

## MCP tools

| Tool | Purpose |
| --- | --- |
| `memory_health` | Server, schema, index, and projection status |
| `memory_capture` | Persist one already-extracted memory |
| `memory_update` | Amend a memory or move it through its lifecycle |
| `memory_get` | Fetch one memory by stable ID |
| `memory_recall` | Ranked, filtered search over the corpus |
| `memory_context` | A bounded, provenance-tagged bundle for injection |

Memories are classified as `concept`, `decision`, `lesson`, `question`, or `project_context`, and carry a status of `active`, `superseded`, `disputed`, or `archived`. Knowledge is superseded, not overwritten.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- A SQLite build with FTS5 (checked at startup)
- An existing Obsidian vault, if you want the Markdown projection

## Setup

```bash
uv sync
```

Configure via environment or `.env` (see `.env.example`):

```dotenv
RECALL_DB_PATH=~/.recall/recall.db
RECALL_OBSIDIAN_VAULT_PATH=~/Documents/Obsidian/MyVault
RECALL_OBSIDIAN_ROOT=Recall
```

Recall creates its own database and its own root folder inside an existing vault. It never creates a vault.

### Connecting a client

Recall speaks plain MCP over stdio — any compliant client works. Claude Code is the reference client, registered per-project via a committed `.mcp.json`:

```json
{
  "mcpServers": {
    "recall": {
      "command": "uv",
      "args": ["run", "recall"],
      "env": {}
    }
  }
}
```

Vault paths stay in the environment, not in that file. Call `memory_health` after connecting — it reports schema version, FTS5 availability, and whether the projection root is reachable.

The `/learn` capture workflow lives in `.claude/skills/learn/`, version-controlled next to the server it drives.

### A note on the Obsidian files

Projected Markdown is **written by Recall and re-rendered from SQLite**. Editing a note inside Obsidian works, but your edit is overwritten the next time that memory is updated. SQLite is the source of truth; the vault is a view of it. Reading, linking, and searching in Obsidian are all fine.

No Obsidian API key, plugin, or running app is required — a vault is a folder of Markdown files.

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

This repository is built with Claude Code. [CLAUDE.md](CLAUDE.md) holds the condensed invariants and loads into every session; [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) is the authoritative spec — architecture, memory model, milestones, and the contributor contract. Read the guide before changing anything.

## Status

Pre-Milestone 0. The guide is written; the code is not.
