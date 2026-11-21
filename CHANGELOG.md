# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- None yet.

## [0.4.0] - 2026-11-21

### Added

- **`tiny-skill-scan`** — a prompt-injection scanner for the SKILL.md *body*.
  The frontmatter linter answers "is this document well-formed?"; it says
  nothing about what the document tells the agent to do, and a well-formed
  SKILL.md is the cheapest delivery vehicle for an injection because the
  agent loads it as instructions by design. Ten rules: S001 authority
  override, S002 false authority, S003 exfiltration, S004 credential
  harvesting, S005 instructions in an HTML comment, S006 invisible / bidi /
  matched-isolate runs, S007 concealment, S008 remote-into-shell, S009
  self-granted scope, S010 answer-shaped fence.
- `--format json`, `--strict`, and recursive directory scanning.
- `examples/clean-corpus/` — three real SKILL.md files that must stay clean.

### Fixed

- **Line numbers pointed at the wrong line.** `strip_frontmatter` returned the
  body with the frontmatter *removed*, so a finding on the fifth line of the
  file was reported as line 3. It now blanks the frontmatter while preserving
  its line count (`preserve_lines=True`), which is the difference between a
  report a reviewer can act on and one that sends them to the wrong
  paragraph.
- **The CI test step named its test files explicitly.** A new test file would
  have passed locally and never executed in CI. The step now collects by
  pattern.

### Notes on false positives

A security linter that fires on correct documentation gets ignored within a
day, and the real finding goes with it. The first draft of S003 flagged every
`curl` example line in this workspace's own skills. The shipped rules follow
three conventions, each covered by a test:

- **Prose rules skip fenced blocks and blockquotes.** A security skill that
  *quotes* "ignore previous instructions" inside an example, or in a `>`
  paragraph describing the attack, is not doing it. Rules that describe
  executed content (S003, S004, S008) still fire inside fences, because that
  is where the command lives.
- **A verb list describes where the value ends up, not what it is.** `echo
  $TOKEN` and `cat ~/.ssh/id_rsa` are how a developer checks a value locally
  and both appear in correct documentation, so they are not credential
  harvesting. S004 fires on verbs that put the value into the model's reply.
- **A single zero-width character or directional isolate is prose.** Only a
  run of three or more, a bidi override or embedding at any count, or a
  matched isolate pair, is flagged — otherwise every Arabic, Hebrew, or
  Persian skill becomes a false positive.


### Fixed

- **The dogfood step could not pass its own new rule.** `examples/SKILL.md`
  lived in a directory named `examples` while its `name` was
  `skill-authoring`, so E019 — the rule this branch adds — failed on the
  repository's own bundled example, on every Python version. The example now
  lives at `examples/skill-authoring/SKILL.md`, which is the shape the spec
  requires and the shape a real bundle has.
- CI runs the suite with `-v` so a failing job names the test.

## [0.3.0] - 2026-11-07

### Added

- **E019: `name` must match the parent directory name.** The
  [agentskills.io specification](https://agentskills.io/specification) states
  that `name` "must match the parent directory name". Without this rule a
  skill loads in a lenient client and is rejected by a spec-compliant one,
  with an error that names the skill rather than the mismatch. The check
  compares the basename of the SKILL.md's own parent and returns `None` for a
  file written straight into a temp directory, so unit fixtures are not
  forced to invent a skill directory. Catalogue is now 19 codes.

### Fixed

- None. Proven by `TestDirectoryNameMatch`: stubbing the check turns
  `test_mismatched_directory_fires_e019` red (1 failed, 35 passed).

## [0.2.0] - 2026-11-02

### Fixed

- **E017 was unreachable.** `_first_sentence()` capped the returned sentence at
  100 characters, so the rule that fires when the first sentence is *longer*
  than 100 characters could never be true. A `description` with no sentence
  punctuation produced exactly 100 characters and E017 never fired. The
  length cap is removed; the first sentence is now measured to its `.`, `!`
  or `?`, or is the whole description when it has none.

### Added

- **4 regression tests** pinning E017 behaviour: fires without punctuation,
  fires when measured to a period, does not fire at exactly 100 characters,
  does not fire on a short description.
- **Version-consistency test** asserting `pyproject.toml` matches
  `tiny_skill_lint.__version__`, and `__version__` on the module.
- **`examples/skill-authoring/SKILL.md`** — a valid bundle that CI dogfoods the linter against,
  so the bundled example cannot drift away from what the linter accepts.

### Changed

- Removed the deprecated `tiny_skill_lint_part2.py` stub, which was a
  comment-only file kept for history and had no runtime effect.
- CI self-lint step points at `examples/skill-authoring/SKILL.md` instead of `README.md`,
  which was never a SKILL.md and so reported E012 (no frontmatter block).
- README drops an ecosystem section that named three packages with version
  numbers that do not exist (`skillspec/lint` v0.3.0, `skillcheck/core` v0.4.0,
  `openskills/lint` v0.2.0) and a link to a `dev-masterkit` spec file that was
  never published. The claims were unverifiable and two of the names are now
  taken by unrelated third-party projects.

## [0.1.0] - 2026-10-09

### Added

- **Initial release.**
- **18-code error catalogue** (E001–E018) covering: missing/invalid required
  fields (`name`, `description`, `version`), description budget overrun (>800
  chars), name format (kebab-case), semver validation, unknown frontmatter
  keys, empty/TODO descriptions, missing `when_to_use`, YAML parse errors,
  trailing whitespace, uppercase name, missing trailing newline, pre-1.0
  version warning, and oversize first-sentence warning.
- **CLI** with `--format=human|json`, `--strict` (promotes warnings to
  errors), and `--config=<path>` for `lint.config.json`.
- **Stdlib-only**, ~210 LOC of executable code, zero runtime dependencies,
  Python 3.8+.
- **CI** across Python 3.8-3.12.

### Tests

- 32 tests covering: required-field detection, name format validation,
  description budget, semver validation, unknown key rejection, multi-line
  value parsing, ignore patterns, strict-mode promotion, JSON output shape,
  directory recursion, and human output grouping.
