#!/usr/bin/env python3
"""Install Recall's MCP server and workflows into an AI coding assistant.

One canonical copy of the skill and commands lives in ``ai/``. This script
renders that into whatever layout each assistant expects, so the workflows stay
identical across providers instead of drifting into four hand-maintained forks.

Usage:
    python scripts/install.py claude
    python scripts/install.py codex --vault ~/Documents/Obsidian/MyVault
    python scripts/install.py opencode --global
    python scripts/install.py all --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AI_DIR = REPO / "ai"
COMMANDS_DIR = AI_DIR / "commands"
SKILL_FILE = AI_DIR / "skills" / "recall" / "SKILL.md"

PROVIDERS = ("claude", "codex", "opencode")


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


@dataclass
class Action:
    """One filesystem change, described before it happens."""

    path: Path
    content: str
    note: str = ""

    def apply(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.content, encoding="utf-8")


def server_command(use_uv: bool) -> tuple[str, list[str]]:
    """How the assistant should launch the server.

    ``uv run`` keeps the server pinned to this repo's locked environment; a
    bare ``recall`` assumes the package is installed on PATH.
    """
    if use_uv:
        return "uv", ["--directory", str(REPO), "run", "recall"]
    return "recall", []


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


def plan_claude(vault: str | None, scope: Path, use_uv: bool) -> list[Action]:
    """Claude Code: .mcp.json, .claude/skills/, .claude/commands/."""
    command, args = server_command(use_uv)
    entry: dict[str, object] = {"command": command, "args": args}
    if vault:
        entry["env"] = {"RECALL_VAULT_PATH": vault}

    config_path = scope / ".mcp.json"
    config = _read_json(config_path)
    config.setdefault("mcpServers", {})["recall"] = entry

    actions = [
        Action(config_path, json.dumps(config, indent=2) + "\n", "MCP server registration"),
        Action(
            scope / ".claude" / "skills" / "recall" / "SKILL.md",
            SKILL_FILE.read_text(encoding="utf-8"),
            "capture skill",
        ),
    ]
    for source in sorted(COMMANDS_DIR.glob("*.md")):
        actions.append(
            Action(
                scope / ".claude" / "commands" / source.name,
                source.read_text(encoding="utf-8"),
                f"/{source.stem} command",
            )
        )
    return actions


def plan_opencode(vault: str | None, scope: Path, use_uv: bool) -> list[Action]:
    """OpenCode: opencode.json, .opencode/commands/, AGENTS.md."""
    command, args = server_command(use_uv)
    entry: dict[str, object] = {"type": "local", "command": [command, *args], "enabled": True}
    if vault:
        entry["environment"] = {"RECALL_VAULT_PATH": vault}

    config_path = scope / "opencode.json"
    config = _read_json(config_path)
    config.setdefault("$schema", "https://opencode.ai/config.json")
    config.setdefault("mcp", {})["recall"] = entry

    actions = [
        Action(config_path, json.dumps(config, indent=2) + "\n", "MCP server registration"),
        Action(scope / "AGENTS.md", _agents_md(), "skill as agent instructions"),
    ]
    for source in sorted(COMMANDS_DIR.glob("*.md")):
        actions.append(
            Action(
                scope / ".opencode" / "commands" / source.name,
                source.read_text(encoding="utf-8"),
                f"/{source.stem} command",
            )
        )
    return actions


def plan_codex(vault: str | None, scope: Path, use_uv: bool) -> list[Action]:
    """Codex: .codex/config.toml, AGENTS.md, and global prompts.

    Codex loads custom prompts only from ``$CODEX_HOME/prompts`` (defaults to
    ``~/.codex/prompts``), so the commands install globally even when the MCP
    registration is project-scoped.
    """
    command, args = server_command(use_uv)
    lines = [
        "[mcp_servers.recall]",
        f'command = "{command}"',
        "args = [" + ", ".join(f'"{arg}"' for arg in args) + "]",
    ]
    if vault:
        lines += ["", "[mcp_servers.recall.env]", f'RECALL_VAULT_PATH = "{vault}"']

    actions = [
        Action(
            scope / ".codex" / "config.toml",
            "\n".join(lines) + "\n",
            "MCP server registration (merge by hand if the file exists)",
        ),
        Action(scope / "AGENTS.md", _agents_md(), "skill as agent instructions"),
    ]
    prompts = Path.home() / ".codex" / "prompts"
    for source in sorted(COMMANDS_DIR.glob("*.md")):
        actions.append(
            Action(
                prompts / source.name,
                source.read_text(encoding="utf-8"),
                f"/{source.stem} prompt (global — Codex has no project prompts)",
            )
        )
    return actions


PLANNERS = {"claude": plan_claude, "codex": plan_codex, "opencode": plan_opencode}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, object]:
    """Load an existing config so installing never discards other servers."""
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"  ! {path} is not valid JSON; leaving it alone", file=sys.stderr)
        raise SystemExit(1) from None
    return loaded if isinstance(loaded, dict) else {}


def _agents_md() -> str:
    """Render the skill as an AGENTS.md section, the format Codex and
    OpenCode both read for repository instructions.
    """
    body = SKILL_FILE.read_text(encoding="utf-8")
    if body.startswith("---"):
        body = body.split("---", 2)[-1].lstrip("\n")
    return (
        "# Agent instructions\n\n"
        "This project uses the Recall MCP server to store engineering "
        "knowledge in an Obsidian vault.\n\n"
        f"{body}"
    )


def _check_environment(use_uv: bool) -> None:
    command, _ = server_command(use_uv)
    if shutil.which(command) is None:
        print(
            f"  ! '{command}' is not on PATH — the assistant will not be able "
            "to start the server until it is",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install Recall into an AI coding assistant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("provider", choices=[*PROVIDERS, "all"])
    parser.add_argument(
        "--vault",
        help="Obsidian vault path to bake into the config. Omit to rely on RECALL_VAULT_PATH.",
    )
    parser.add_argument(
        "--scope",
        type=Path,
        default=Path.cwd(),
        help="Directory to install into (default: current directory).",
    )
    parser.add_argument(
        "--no-uv",
        action="store_true",
        help="Launch an installed 'recall' binary instead of 'uv run'.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing.")
    args = parser.parse_args()

    if not SKILL_FILE.exists():
        print(f"error: canonical skill missing at {SKILL_FILE}", file=sys.stderr)
        return 1

    vault = args.vault
    if vault:
        resolved = Path(vault).expanduser()
        if not resolved.is_dir():
            print(f"error: vault path is not a directory: {resolved}", file=sys.stderr)
            return 1
        vault = str(resolved.resolve())

    targets = PROVIDERS if args.provider == "all" else (args.provider,)
    scope = args.scope.expanduser().resolve()
    use_uv = not args.no_uv

    _check_environment(use_uv)

    for provider in targets:
        actions = PLANNERS[provider](vault, scope, use_uv)
        print(f"\n{provider}:")
        for action in actions:
            marker = "would write" if args.dry_run else "wrote"
            try:
                shown: Path | str = action.path.relative_to(scope)
            except ValueError:
                shown = action.path
            print(f"  {marker} {shown}" + (f"  — {action.note}" if action.note else ""))
            if not args.dry_run:
                action.apply()

    if not vault:
        print(
            "\nNo --vault given. Set RECALL_VAULT_PATH in your environment "
            "before starting the assistant."
        )
    print("\nRestart your assistant to pick up the new configuration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
