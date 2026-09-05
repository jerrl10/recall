---
description: Record an architectural or technical decision in the Obsidian vault
---

Capture the decision we just reached as a `decision` note.

Call `note_search` first to check whether this supersedes or refines an
existing decision. If it does, extend that note under its existing title so
the reasoning stays in one place.

Then call `note_capture` with kind `decision` and these sections:

- **Context** — what forced a choice
- **Decision** — what was chosen, stated plainly
- **Consequences** — what this now commits us to, including the downsides
- **Alternatives considered** — what was rejected and why

Record the decision actually made, not the one that sounds best. If it was a
trade-off under uncertainty, say so.
