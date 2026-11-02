# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **`examples/SKILL.md`** — a valid bundle that CI dogfoods the linter against,
  so the bundled example cannot drift away from what the linter accepts.

### Changed

- CI self-lint step points at `examples/SKILL.md` instead of `README.md`,
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
