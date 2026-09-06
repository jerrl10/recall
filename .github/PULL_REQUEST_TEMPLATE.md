## What this changes

<!-- And why. The reasoning is the part a reader cannot get from the diff. -->

## Checklist

- [ ] `uv run ruff format . && uv run ruff check .`
- [ ] `uv run mypy src tests`
- [ ] `uv run pytest`
- [ ] Tests cover the failure paths, not only the happy one
- [ ] A bug fix has a test that fails without it
- [ ] Workflow changes were made in `ai/`, not in a generated provider directory
- [ ] A tool-surface change updates the contract test, the README, and the skill
- [ ] Anything structural has an ADR in `docs/decisions/`
- [ ] `CHANGELOG.md` updated under Unreleased
