---
name: engineering-notes
description: Capture durable engineering knowledge from the current AI conversation and maintain the user's Obsidian engineering knowledge base.
---

# Engineering Notes

## Purpose

Do not create transcripts.

Extract engineering knowledge that will still be useful months later.

Capture:
- reusable concepts
- architecture reasoning
- tradeoffs
- important terminology
- patterns
- debugging / operational lessons
- actual decisions
- open questions

Ignore:
- greetings
- filler
- temporary debugging noise
- repetitive explanations
- obvious generated code

## Taxonomy

- `Daily/YYYY-MM-DD.md`
- `Concepts/<Concept>.md`
- `Projects/<Project>.md`
- `Decisions/<Decision>.md`
- `Lessons/<Lesson>.md`

## Rules

1. Review the current conversation.
2. Search existing knowledge first.
3. Prefer merge over duplicate.
4. Preserve useful existing content.
5. Keep notes concise and technical.
6. Use Obsidian `[[Wiki Links]]` where useful.
7. Add a concise entry to today's Daily note.
8. Do not claim AI suggestions are verified facts.
9. Report only changed/created files unless asked for the content.

## Future Recall MCP behavior

When Recall MCP tools are available, prefer them over direct Markdown editing.

The intended semantic operations are:
- recall/search existing memory
- capture new memory
- update existing memory
- retrieve compact context

Do not bypass Recall with raw file edits once the MCP workflow is enabled.
