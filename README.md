# tiny-skill-lint

Zero-dependency SKILL.md tooling: a frontmatter linter **and** a prompt-injection scanner for the body. Stdlib-only.

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-97%2F97-brightgreen.svg)
[![CI](https://github.com/hussain-alsaibai/tiny-skill-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/hussain-alsaibai/tiny-skill-lint/actions/workflows/ci.yml)

`tiny-skill-lint` validates the frontmatter of `SKILL.md` files against a flat-key
YAML subset, a 19-code error catalogue, and a `description` character-budget check.
It is a single stdlib-only file, so it drops into any repo with no dependency tree.

## Why tiny-skill-lint?

The SKILL.md convention is adopted by OpenClaw, Cursor, Goose, CodeBuddy, and most
internal agent frameworks. There was no schema enforcement, no quality score, and no
CI gate. `tiny-skill-lint` is a single-file Python tool that:

- Validates required fields (`name`, `description`, `version`)
- Enforces an 800-character description budget (warn on overrun)
- Emits against the 19-code error catalogue (`E001`–`E019`)
- Supports CI-friendly JSON output via `--format=json`
- Exits non-zero on errors, so it is usable as a CI gate as-is
- Configurable via `lint.config.json`

## Why also scan the body?

`tiny-skill-lint` answers *is this document well-formed?* It does not answer
*what does this document tell the agent to do?* — and a well-formed SKILL.md is
the cheapest delivery vehicle for a prompt injection, because the agent loads
it **as instructions**, by design. A skill can pass the frontmatter gate and
still tell the agent to exfiltrate `~/.ssh`.

`tiny-skill-scan` reads the body. Ten rules, three groups:

| code | severity | what it catches |
|---|---|---|
| S001 | high | "ignore all previous instructions", rule override |
| S002 | high | fake system role, "this skill supersedes policy" |
| S003 | high | exfiltration: upload/send data to a collector |
| S004 | high | credential harvesting: print the API key into the reply |
| S005 | high | instructions hidden in an HTML comment |
| S006 | high | zero-width runs, bidi overrides, matched isolates |
| S007 | medium | "don't tell the user", concealment |
| S008 | medium | `curl … \| bash` from a remote document |
| S009 | medium | self-granted scope, "no approval required" |
| S010 | low | a fence that supplies the model's answer verbatim |

```bash
tiny-skill-scan skills/                    # human output, exit 1 only on high
tiny-skill-scan SKILL.md --format json     # machine-readable
tiny-skill-scan skills/ --strict           # exit 1 on any finding
```

### The false-positive rule

A security linter that fires on correct documentation is worse than no
linter: it gets ignored within a day, and so does the real finding behind it.
The first draft of S003 flagged every `curl` example line in a real skills
tree. Three conventions keep it usable, each covered by a test:

- **Prose rules skip fenced blocks and blockquotes.** A security skill that
  *quotes* an attack — in a code fence, or in a `>` paragraph describing the
  shape — is not performing it. Rules that describe executed content (S003,
  S004, S008) still fire inside fences, because that is where the command
  lives; a quote on the next line still fires.
- **A verb list describes where the value ends up.** `echo $TOKEN` and
  `cat ~/.ssh/id_rsa` are how a developer checks a value locally, and both
  appear in correct documentation. S004 fires on verbs that put the value
  into the model's reply, which is where it can be forwarded.
- **A single zero-width char or isolate is prose.** Only a run of three or
  more, a bidi override or embedding at any count, or a matched isolate pair,
  is flagged — otherwise every Arabic, Hebrew, or Persian skill is a false
  positive.

Findings are reviewable by construction: line, column, the matched span, and
one sentence of why. Nothing is auto-fixed and nothing is silently dropped.

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
| E019 | error | `name` does not match the parent directory name (agentskills.io spec) |

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
python -m pytest -v
```

35 tests, stdlib only. CI runs them across Python 3.8–3.12 and then dogfoods the
linter against `examples/skill-authoring/SKILL.md`, so the bundled example cannot drift away from
what the linter accepts.

## License

MIT
