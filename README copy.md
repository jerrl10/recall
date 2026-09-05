# Recall

**Long-term engineering memory for AI coding assistants.**

Recall turns useful engineering conversations into durable, structured knowledge that can be reused by OpenCode, Claude Code, Codex, and other MCP-compatible clients.

## Current goal

The first milestone is intentionally small:

```text
AI client
   │
   │ MCP
   ▼
Recall
   │
   ├── SQLite
   └── Obsidian projection
```

Recall v1 does **not** require its own LLM calls. The AI client already has the conversation and performs the reasoning. Recall provides reliable storage, retrieval, and projection.

## Repository structure

```text
apps/
  mcp_server/      MCP transport and tool surface
  cli/             Local administration / debugging CLI

packages/
  core/            Domain + application use cases
  storage/         SQLite/Postgres adapters
  obsidian/        Obsidian Markdown projection
  retrieval/       Lexical / future semantic retrieval
  providers/       Optional future AI provider adapters

ai/
  skills/          Shared AI workflows
  commands/        Reusable commands such as /learn
  prompts/         Canonical prompt material

docs/
  architecture/
  decisions/
  roadmap/
  development/

AGENTS.md
CLAUDE.md
DEVELOPMENT_GUIDE.md
```

## Design principles

1. Engineering knowledge is the domain; Obsidian is an adapter.
2. MCP is the interoperability boundary, not the business layer.
3. Prefer semantic tools over raw file CRUD.
4. Search before create; merge before duplicate.
5. Provenance and reversibility matter.
6. Keep LLM usage optional.
7. Start simple: SQLite + FTS + Obsidian projection.
8. Avoid premature vector databases, graph databases, queues, or distributed infrastructure.

## Planned v1 MCP tools

- `memory_capture`
- `memory_recall`
- `memory_get`
- `memory_context`

Later:

- `memory_review`
- `memory_apply`
- `memory_consolidate`

## Local setup

```bash
uv sync
uv run pytest
uv run ruff check .
```

OpenCode integration:

```bash
./scripts/install-ai-config.sh opencode
```

See `DEVELOPMENT_GUIDE.md` for the architecture and contribution rules.
