# Getting Started

## Requirements

- Python 3.12+
- uv
- Git

## Setup

```bash
uv sync
cp .env.example .env
uv run pytest
uv run ruff check .
```

## Run the MCP server

During the initial scaffold stage:

```bash
uv run python apps/mcp_server/recall_mcp/server.py
```

The server currently exposes only a health tool.

## AI workflow setup

```bash
./scripts/install-ai-config.sh opencode
```

Restart OpenCode after installing the global config.
