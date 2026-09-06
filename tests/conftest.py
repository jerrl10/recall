"""Shared fixtures.

Every test runs against a throwaway vault directory. Nothing here touches a
real Obsidian vault or the user's home directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from recall.config import Settings
from recall.search import Search
from recall.vault import Vault


@pytest.fixture
def vault_path(tmp_path: Path) -> Path:
    """An empty directory standing in for an Obsidian vault."""
    path = tmp_path / "vault"
    path.mkdir()
    return path


@pytest.fixture
def settings(vault_path: Path) -> Settings:
    config = Settings(vault_path=vault_path)
    config.validate_vault()
    return config


@pytest.fixture
def vault(settings: Settings) -> Vault:
    return Vault(settings)


@pytest.fixture
def search(vault: Vault, settings: Settings) -> Search:
    return Search(vault, settings)


@pytest.fixture
def call(settings: Settings, vault: Vault, search: Search) -> Iterator[Any]:
    """Invoke an MCP tool against the temporary vault.

    The server caches its settings in module globals so configuration is
    resolved once per process; the fixture swaps them out and restores them so
    tests cannot leak state into one another.
    """
    from recall import server

    saved = (server._settings, server._vault, server._search)
    server._settings, server._vault, server._search = settings, vault, search

    async def invoke(name: str, **arguments: Any) -> Any:
        result = await server.mcp.call_tool(name, arguments)
        return getattr(result, "structured_content", None)

    yield invoke

    server._settings, server._vault, server._search = saved
