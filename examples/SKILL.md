---
name: skill-authoring
description: Scaffold and validate a SKILL.md bundle that loads cleanly in OpenClaw, Cursor, and Codex.
version: 1.0.0
when_to_use: You are writing or reviewing a SKILL.md file and want the frontmatter to pass tiny-skill-lint.
---

# Skill Authoring

This example is linted by `tiny-skill-lint` itself in CI, so the example
cannot drift away from what the linter accepts.

## Steps

1. Write the frontmatter block: `name`, `description`, `version`, `when_to_use`.
2. Keep `name` in kebab-case and `version` in plain semver.
3. Run `python -m tiny_skill_lint path/to/SKILL.md` and fix every error.
