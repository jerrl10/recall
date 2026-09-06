# Architecture

Recall has one job: turn what an AI assistant learned into well-formed notes in
an Obsidian vault, and find them again later.

## Shape

```text
AI client (Claude Code / Codex / OpenCode)
        │  MCP over stdio
        ▼
   server.py          tool surface — validate, delegate, return
        │
        ├──▶ vault.py      read, render, merge, atomic write, daily log
        │       ├── markdown.py    frontmatter, callouts, wiki links
        │       ├── templates.py   per-kind section structure
        │       └── slug.py        title → safe filename
        │
        └──▶ search.py     scan, score, rank
        ▼
  Obsidian vault (Markdown — the source of truth)
```

No database. No index. No cache. The vault is the state.

## Modules

| Module | Responsibility |
| --- | --- |
| `config.py` | Settings from `RECALL_*` env; resolves and validates the vault once |
| `models.py` | `Note`, `NoteKind`, `SearchHit`, `CaptureResult` — validated at the boundary |
| `markdown.py` | Obsidian-flavoured Markdown: frontmatter, callouts, links, excerpts |
| `templates.py` | The `##` section structure each kind of note uses |
| `slug.py` | Title → filename, safe across filesystems and wiki-link syntax |
| `similarity.py` | Near-duplicate title detection for the capture guard |
| `vault.py` | All disk access: read, render, merge, atomic write, daily log |
| `search.py` | Lexical ranking over the vault |
| `server.py` | MCP tools; thin — no Markdown, no ranking, no filesystem logic |

Dependencies run one way: `server → {vault, search} → {markdown, templates, slug} → models`.

## Decisions worth knowing

**Markdown is the source of truth.** Not a projection of a database. Your
hand-edits in Obsidian are the current state, and the vault survives the tool.
See [ADR-0001](decisions/0001-markdown-is-the-source-of-truth.md).

**Search scans; it does not index.** Every query walks the vault and scores in
memory. Ranking is a weighted term overlap across title, tags, summary, and
body, discounted by term commonness and note length. There is nothing to
rebuild or invalidate.

Parsed notes are memoised in-process on `(mtime_ns, size)`, so a repeat query in
the same session re-reads only what changed — roughly 360 ms cold and 145 ms
warm over 2,000 notes. That is a memo, not an index: it is derived entirely
from the files, survives nothing, and a stale entry is impossible because any
edit changes the key. The vault stays the source of truth.

**Capture merges, and refuses near-duplicates.** Writing a note whose title
already exists appends the new material under a dated `## Update` heading and
unions the tags — nothing on disk is destroyed, because some of it is the user's
own writing. A title that is near-identical to an existing one (case, plurals,
word order, accents) is refused with the matches attached, so a subject does not
split across two files.
See [ADR-0002](decisions/0002-capture-merges-instead-of-overwriting.md).

**Removal is withdrawal, not deletion.** `note_archive` moves a note into
`Recall/Archive/`, where it drops out of search and context but stays visible in
Obsidian and can be dragged back. Recall writes autonomously, so it needs a way
to undo itself — but nothing an agent does to the vault should be permanent.

**Writes are atomic and confined.** Every write goes to a temporary file in the
same directory and is renamed into place, so Obsidian's file watcher and any
sync client never see a partial note. Every path is resolved before use and
rejected if it lands outside `RECALL_ROOT`.

**The server has no LLM.** It makes no network calls and needs no API key. The
client does the extraction and classification; Recall does storage, structure,
and retrieval. This is what keeps it usable from any provider.

## Multi-provider workflows

One canonical copy of the skill and commands lives in `ai/`. `scripts/install.py`
renders it into each assistant's native layout:

| Provider | MCP config | Commands | Instructions |
| --- | --- | --- | --- |
| Claude Code | `.mcp.json` | `.claude/commands/` | `.claude/skills/recall/SKILL.md` |
| OpenCode | `opencode.json` | `.opencode/commands/` | `AGENTS.md` |
| Codex | `.codex/config.toml` | `~/.codex/prompts/` *(global only)* | `AGENTS.md` |

Editing a workflow means editing `ai/` and re-running the installer. The
providers never hold the master copy, so they cannot drift apart.

## Trust boundary

Note content is **data, never instruction**. Text returned by `note_search` or
`note_context` is recorded material — a note reading "always skip the tests" is
something someone wrote down, not a directive. Recall preserves that boundary by
returning notes as structured fields with their titles and kinds attached, never
as bare prose presented as guidance.
