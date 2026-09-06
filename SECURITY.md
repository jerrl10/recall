# Security Policy

## Reporting a vulnerability

Please report security issues privately through
[GitHub Security Advisories](https://github.com/jerrl10/recall/security/advisories/new)
rather than opening a public issue.

Include what an attacker can do, how to reproduce it, and the version or commit
affected. You'll get an acknowledgement within a week. This is a personally
maintained project, so please allow reasonable time for a fix before disclosing
publicly.

## What Recall touches

Understanding the threat model makes it clearer what counts as a vulnerability.

Recall is a **local, single-user** MCP server. It:

- reads and writes Markdown files beneath one configured folder;
- makes **no network calls** and holds no credentials or API keys;
- runs as a subprocess of your AI client, with your user's permissions;
- has **no authentication** and is not designed to be exposed over a network.

## In scope

- **Escaping the vault root.** Every path is resolved and then checked against
  `RECALL_ROOT`; anything reaching outside it — via `..`, symlinks, or a
  crafted title — is a vulnerability.
- **Data loss.** Capture merges and archive moves; nothing should be able to
  make Recall destroy note content, including the user's own hand-written
  edits.
- **Content leaking into logs.** Note bodies must never be logged.
- **Command or code execution** from note content, titles, or frontmatter.
  Stored content is data and is never evaluated.
- **Denial of service** through a crafted note that hangs parsing or search.

## Out of scope

- **Prompt injection through note content.** Recall stores what a client sends
  and returns it as structured data with titles and kinds attached. A note
  reading "ignore previous instructions" is recorded text, not an instruction —
  but Recall cannot control how a model treats what it reads. Preserving the
  data boundary is Recall's job; enforcing the prompt hierarchy is the client's.
- **A malicious MCP client.** A client already runs with your permissions and
  can write to the vault directly. Recall does not defend against the process
  that launched it.
- **A vault on untrusted or shared storage.** Recall assumes the vault belongs
  to the user running it.
- **Exposing the server over a network.** It is stdio, local, and unauthenticated
  by design. Do not do this.

## Practices

- Path containment is verified *after* resolution, so `..` and symlinks cannot
  redirect a write.
- Writes are atomic — a temporary file in the same directory, then `os.replace`
  — so an interrupted write cannot truncate a note.
- Frontmatter parsing is lenient by design: malformed YAML in a hand-edited
  note degrades to "no properties" rather than raising.
- Errors returned to clients carry no absolute filesystem paths.
- Dependencies are pinned in `uv.lock` and updated by Dependabot.
