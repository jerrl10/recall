---
description: Record a debugging or operational lesson in the Obsidian vault
---

Capture what we just learned the hard way as a `lesson` note.

Call `note_search` first — if this is a recurrence of a known failure, extend
that note instead of writing a second one.

Then call `note_capture` with kind `lesson` and these sections:

- **What happened** — the symptom, as it actually presented
- **Root cause** — the real cause, not the first plausible one
- **Fix** — what resolved it, with the specific command, flag, or change
- **How to avoid it** — the signal to watch for next time

Include the concrete detail: exact error text, version numbers, the setting
that mattered. A vague lesson is one you will have to learn again.
