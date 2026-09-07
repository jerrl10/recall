"""Command line: setup, doctor, and the server itself.

Configuration is the step where tools get abandoned, so `recall setup` does the
looking-up itself and `recall doctor` answers "why isn't this working" without
anyone reading source.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__, discovery
from .config import load_settings
from .vault import Vault

ENV_FILE_NAME = ".env"


def _say(message: str = "") -> None:
    """Write to stderr.

    stdout belongs to the MCP protocol. The CLI shares a process entry point
    with the server, so it keeps the same discipline rather than relying on
    remembering which mode it is in.
    """
    print(message, file=sys.stderr)


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


def _choose_vault(candidates: list[Path]) -> Path | None:
    if not candidates:
        _say("No Obsidian vaults found automatically.")
        _say()
        answer = input("Path to your vault: ").strip()
        return Path(answer).expanduser().resolve() if answer else None

    _say("Vaults found:")
    for index, path in enumerate(candidates, start=1):
        marker = "" if discovery.looks_like_a_vault(path) else "  (no .obsidian folder yet)"
        _say(f"  {index}. {path}{marker}")
    _say(f"  {len(candidates) + 1}. somewhere else")
    _say()

    answer = input(f"Which vault? [1-{len(candidates) + 1}] ").strip()
    if not answer:
        return candidates[0]
    if not answer.isdigit():
        return None

    choice = int(answer)
    if 1 <= choice <= len(candidates):
        return candidates[choice - 1]
    if choice == len(candidates) + 1:
        typed = input("Path to your vault: ").strip()
        return Path(typed).expanduser().resolve() if typed else None
    return None


def _choose_scope() -> str:
    """Ask before letting an assistant read the user's existing notes."""
    _say()
    _say("Recall only ever writes into its own folder. What should it be able to read?")
    _say()
    _say("  1. Your whole vault — everything you have already written becomes")
    _say("     recallable immediately. An assistant can surface any note in it.")
    _say("  2. Only notes Recall creates — nothing existing is ever read.")
    _say()
    answer = input("Which? [1/2] ").strip()
    return "recall" if answer == "2" else "vault"


def command_setup(args: argparse.Namespace) -> int:
    """Find a vault, confirm the scope, and write a .env file."""
    _say("Recall setup")
    _say()

    vault = (
        Path(args.vault).expanduser().resolve()
        if args.vault
        else _choose_vault(discovery.discover())
    )
    if vault is None:
        _say("No vault chosen. Nothing written.")
        return 1
    if not vault.is_dir():
        _say(f"Not a directory: {vault}")
        return 1

    scope = args.scope or _choose_scope()

    target = Path(args.output).expanduser().resolve() if args.output else Path.cwd() / ENV_FILE_NAME
    if target.exists() and not args.force:
        _say()
        _say(f"{target} already exists. Re-run with --force to overwrite, or set:")
        _say(f"  RECALL_VAULT_PATH={vault}")
        _say(f"  RECALL_SEARCH_SCOPE={scope}")
        return 1

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"RECALL_VAULT_PATH={vault}\nRECALL_SEARCH_SCOPE={scope}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        _say(f"Could not write {target}: {exc.strerror or exc}")
        _say()
        _say("Set these in your environment instead:")
        _say(f"  RECALL_VAULT_PATH={vault}")
        _say(f"  RECALL_SEARCH_SCOPE={scope}")
        return 1

    _say()
    _say(f"Wrote {target}")
    _say(f"  vault: {vault}")
    _say(f"  scope: {scope}")
    _say()
    _say("Next: register Recall with your assistant, then ask it to run vault_health.")
    _say(f"  python scripts/install.py claude --vault {vault}")
    return 0


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def command_doctor(_: argparse.Namespace) -> int:
    """Check every prerequisite and say plainly which one is unmet."""
    _say(f"Recall {__version__}")
    _say()

    configured = os.environ.get("RECALL_VAULT_PATH")
    env_file = Path.cwd() / ENV_FILE_NAME
    if configured:
        _say("  config     RECALL_VAULT_PATH is set")
    elif env_file.exists():
        _say(f"  config     reading {env_file}")
    else:
        _say("  config     FAIL  no RECALL_VAULT_PATH and no .env file")
        _say()
        _say("Run `recall setup`, or set RECALL_VAULT_PATH to your vault.")
        return 1

    try:
        settings = load_settings()
    except Exception as exc:
        _say(f"  vault      FAIL  {exc}")
        _say()
        _say("Run `recall setup` to pick a vault.")
        return 1

    _say(f"  vault      {settings.vault_path}")
    if not discovery.looks_like_a_vault(settings.vault_path):
        _say("             note: no .obsidian folder — Obsidian has not opened this yet")

    _say(f"  writes to  {settings.root}/")
    _say(f"  searches   {settings.search_scope}")

    probe = settings.root_path / ".recall-doctor-probe"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        _say("  writable   yes")
    except OSError as exc:
        _say(f"  writable   FAIL  {exc.strerror or exc}")
        return 1

    counts = Vault(settings).stats()
    total = sum(counts.values())
    _say(
        f"  notes      {total}  ({', '.join(f'{k}: {v}' for k, v in counts.items() if v)})"
        if total
        else "  notes      0  (nothing captured yet)"
    )

    _say()
    _say("Everything checks out.")
    return 0


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


def command_serve(_: argparse.Namespace) -> int:
    from .server import main as serve

    serve()
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recall",
        description="Durable engineering memory for AI coding assistants.",
    )
    parser.add_argument("--version", action="version", version=f"recall {__version__}")
    subcommands = parser.add_subparsers(dest="command")

    serve = subcommands.add_parser("serve", help="Run the MCP server over stdio (default).")
    serve.set_defaults(handler=command_serve)

    setup = subcommands.add_parser("setup", help="Find your vault and write a config file.")
    setup.add_argument("--vault", help="Skip discovery and use this path.")
    setup.add_argument("--scope", choices=["recall", "vault"], help="Skip the scope question.")
    setup.add_argument("--output", help="Where to write the .env file.")
    setup.add_argument("--force", action="store_true", help="Overwrite an existing file.")
    setup.set_defaults(handler=command_setup)

    doctor = subcommands.add_parser("doctor", help="Diagnose a broken configuration.")
    doctor.set_defaults(handler=command_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch a subcommand, defaulting to running the server.

    An assistant launches this with no arguments, so a bare `recall` must
    start the server rather than print help.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        return command_serve(args)
    result: int = handler(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
