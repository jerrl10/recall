"""The installer touches other tools' configuration. It must never destroy it."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import install


@pytest.fixture
def scope(tmp_path: Path) -> Path:
    return tmp_path / "project"


def apply(actions: list[install.Action]) -> None:
    for action in actions:
        action.apply()


class TestCodex:
    """Regression: this planner once rewrote config.toml from scratch,
    silently deleting every other MCP server the user had registered."""

    def _existing(self, scope: Path) -> Path:
        path = scope / ".codex" / "config.toml"
        path.parent.mkdir(parents=True)
        path.write_text(
            '# my setup\nmodel = "gpt-5"\n\n'
            '[mcp_servers.context7]\ncommand = "npx"\n\n'
            '[mcp_servers.playwright]\ncommand = "npx"\n',
            encoding="utf-8",
        )
        return path

    def test_existing_servers_survive(self, scope: Path) -> None:
        path = self._existing(scope)
        apply(install.plan_codex(None, scope, use_uv=True))

        config = tomllib.loads(path.read_text(encoding="utf-8"))
        assert set(config["mcp_servers"]) == {"context7", "playwright", "recall"}

    def test_comments_and_unrelated_settings_survive(self, scope: Path) -> None:
        path = self._existing(scope)
        apply(install.plan_codex(None, scope, use_uv=True))

        text = path.read_text(encoding="utf-8")
        assert "# my setup" in text
        assert 'model = "gpt-5"' in text

    def test_reinstalling_is_idempotent(self, scope: Path) -> None:
        path = self._existing(scope)
        apply(install.plan_codex(None, scope, use_uv=True))
        first = path.read_text(encoding="utf-8")

        actions = install.plan_codex(None, scope, use_uv=True)
        config_action = next(a for a in actions if a.path == path)
        assert config_action.writes is False, "a second install should not rewrite the file"
        assert path.read_text(encoding="utf-8") == first

    def test_a_fresh_config_is_created(self, scope: Path) -> None:
        apply(install.plan_codex(None, scope, use_uv=True))
        path = scope / ".codex" / "config.toml"
        assert "recall" in tomllib.loads(path.read_text(encoding="utf-8"))["mcp_servers"]

    def test_the_result_is_always_valid_toml(self, scope: Path) -> None:
        self._existing(scope)
        apply(install.plan_codex("/vaults/mine", scope, use_uv=True))
        config = tomllib.loads((scope / ".codex" / "config.toml").read_text(encoding="utf-8"))
        assert config["mcp_servers"]["recall"]["env"]["RECALL_VAULT_PATH"] == "/vaults/mine"


class TestJsonProviders:
    def test_claude_keeps_other_servers(self, scope: Path) -> None:
        scope.mkdir(parents=True)
        path = scope / ".mcp.json"
        path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")

        apply(install.plan_claude(None, scope, use_uv=True))
        config = json.loads(path.read_text(encoding="utf-8"))
        assert set(config["mcpServers"]) == {"other", "recall"}

    def test_opencode_keeps_other_servers_and_the_schema(self, scope: Path) -> None:
        scope.mkdir(parents=True)
        path = scope / "opencode.json"
        path.write_text(json.dumps({"mcp": {"other": {"type": "local"}}}), encoding="utf-8")

        apply(install.plan_opencode(None, scope, use_uv=True))
        config = json.loads(path.read_text(encoding="utf-8"))
        assert set(config["mcp"]) == {"other", "recall"}
        assert config["$schema"].startswith("https://")

    def test_opencode_uses_a_command_array(self, scope: Path) -> None:
        actions = install.plan_opencode(None, scope, use_uv=True)
        entry = json.loads(actions[0].content or "{}")["mcp"]["recall"]
        assert isinstance(entry["command"], list)
        assert entry["type"] == "local"


class TestServerCommand:
    def test_installing_into_the_repo_stays_portable(self) -> None:
        """An absolute path here would leak a home directory into a commit."""
        command, args = install.server_command(use_uv=True, scope=install.REPO)
        assert args == ["run", "recall"]
        assert command == "uv"

    def test_installing_elsewhere_points_back_at_the_repo(self, scope: Path) -> None:
        _, args = install.server_command(use_uv=True, scope=scope)
        assert args[:2] == ["--directory", str(install.REPO)]

    def test_no_uv_uses_the_installed_entry_point(self, scope: Path) -> None:
        assert install.server_command(use_uv=False, scope=scope) == ("recall", [])


def test_every_command_is_installed_for_every_provider(scope: Path) -> None:
    expected = {path.stem for path in install.COMMANDS_DIR.glob("*.md")}
    assert expected, "no canonical commands found"

    for planner in (install.plan_claude, install.plan_opencode):
        stems = {a.path.stem for a in planner(None, scope, use_uv=True) if a.path.suffix == ".md"}
        assert expected <= stems


def test_agents_md_carries_the_skill_without_its_frontmatter(scope: Path) -> None:
    action = next(a for a in install.plan_opencode(None, scope, True) if a.path.name == "AGENTS.md")
    assert action.content is not None
    assert not action.content.lstrip().startswith("---")
    assert "note_search" in action.content
