# tiny-skill-lint

A zero-dependency SKILL.md frontmatter linter. ~310 LOC, 33 tests, stdlib-only.

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-33%2F33-brightgreen.svg)](test_tiny_skill_lint.py)
[![CI](https://github.com/hussain-alsaibai/tiny-skill-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/hussain-alsaibai/tiny-skill-lint/actions/workflows/ci.yml)

`tiny-skill-lint` validates the frontmatter of `SKILL.md` files against a flat-key
YAML subset, an 18-code error catalogue, and a `description` character-budget check.
It is a single stdlib-only file, so it drops into any repo with no dependency tree.

## Why tiny-skill-lint?

The SKILL.md convention is adopted by OpenClaw, Cursor, Goose, CodeBuddy, and most
internal agent frameworks. There was no schema enforcement, no quality score, and no
CI gate. `tiny-skill-lint` is a single-file Python tool that:

- Validates required fields (`name`, `description`, `version`)
- Enforces an 800-character description budget (warn on overrun)
- Emits against the 18-code error catalogue (`E001`–`E018`)
- Supports CI-friendly JSON output via `--format=json`
- Exits non-zero on errors, so it is usable as a CI gate as-is
- Configurable via `lint.config.json`

## Install

```bash
# From GitHub (recommended -- not yet on PyPI)
pip install git+https://github.com/hussain-alsaibai/tiny-skill-lint.git
```

Or copy `tiny_skill_lint.py` to your repo and run it directly.

## Usage

```bash
# Lint a single file
python -m tiny_skill_lint path/to/SKILL.md

# Lint a directory recursively
python -m tiny_skill_lint skills/

# CI-friendly output
python -m tiny_skill_lint skills/ --format=json

# Strict mode (warnings become errors)
python -m tiny_skill_lint skills/ --strict
```

Exit code is `1` when any record has level `error`, `0` otherwise. That makes the
JSON form usable directly as a CI gate:

```yaml
- name: Lint skills
  run: python -m tiny_skill_lint skills/ --format=json
```

## Error Codes

| Code | Level | Description |
|------|-------|-------------|
| E001 | error | Missing required field `name` |
| E002 | error | Missing required field `description` |
| E003 | warn  | `description` exceeds 800 characters |
| E004 | error | Invalid `name` format (must be kebab-case) |
| E005 | warn  | `name` is too short (< 3 chars) |
| E006 | error | Invalid `version` (must be semver) |
| E007 | warn  | `version` is `0.0.0` |
| E008 | error | Unknown required field (frontmatter not a flat-key subset) |
| E009 | warn  | Empty `description` |
| E010 | warn  | `description` contains TODO / FIXME / XXX |
| E011 | warn  | Missing `when_to_use` (recommended) |
| E012 | error | YAML parse error |
| E013 | warn  | Trailing whitespace in `description` |
| E014 | warn  | `name` contains uppercase letters |
| E015 | warn  | Missing trailing newline |
| E016 | warn  | `version` is pre-1.0.0 |
| E017 | warn  | `description` first sentence is > 100 chars (no clear lead) |
| E018 | error | Invalid `version` semver (E006 supersedes; E018 retained for compat) |

## Configuration

`lint.config.json`:

```json
{
  "description_budget": 800,
  "strict": false,
  "codes": {
    "E003": {"level": "warn"},
    "E011": {"level": "off"}
  },
  "ignore": ["**/test*/SKILL.md"]
}
```

## Tests

```bash
python -m pytest test_tiny_skill_lint.py -v
```

33 tests, stdlib only. CI runs them across Python 3.8–3.12 and then dogfoods the
linter against `examples/SKILL.md`, so the bundled example cannot drift away from
what the linter accepts.

## License

MIT
