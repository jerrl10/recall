#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"

install_opencode() {
  mkdir -p "$HOME/.config/opencode/skills"
  mkdir -p "$HOME/.config/opencode/commands"

  ln -snf "$ROOT/ai/skills/engineering-notes"     "$HOME/.config/opencode/skills/engineering-notes"

  for file in "$ROOT"/ai/commands/*.md; do
    ln -snf "$file" "$HOME/.config/opencode/commands/$(basename "$file")"
  done

  echo "OpenCode config installed."
  echo "Restart OpenCode to reload skills and commands."
}

install_claude() {
  echo "Claude Code uses the repository CLAUDE.md and AGENTS.md."
  echo "Shared prompt source is under: $ROOT/ai"
  echo "No global Claude files are overwritten by this installer."
}

case "$TARGET" in
  opencode)
    install_opencode
    ;;
  claude)
    install_claude
    ;;
  all)
    install_opencode
    install_claude
    ;;
  *)
    echo "Usage: $0 [opencode|claude|all]"
    exit 1
    ;;
esac
