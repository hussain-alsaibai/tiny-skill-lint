"""tiny-skill-lint: zero-dep SKILL.md frontmatter linter.

Validates the frontmatter of SKILL.md files against a flat-key YAML subset,
an 18-code error catalogue (E001..E018), and a description character-budget
check. Stdlib-only, ~310 LOC, no third-party dependencies.

Usage:
    python -m tiny_skill_lint path/to/SKILL.md
    python -m tiny_skill_lint skills/ --format=json --strict

Exit code is 1 when any record has level "error", so the CLI is usable as a CI
gate directly. See README.md for the error-code catalogue.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

__version__ = "0.2.0"

# --- 18-code error catalogue (E001..E018) ---
# Levels: 'error', 'warn', 'off'. Strict mode promotes 'warn' to 'error'.
ERROR_CODES = {
    "E001": ("error", "Missing required field 'name'"),
    "E002": ("error", "Missing required field 'description'"),
    "E003": ("warn",  "Description exceeds 800 characters"),
    "E004": ("error", "Invalid 'name' format (must be kebab-case)"),
    "E005": ("warn",  "Name is too short (< 3 chars)"),
    "E006": ("error", "Invalid 'version' (must be semver)"),
    "E007": ("warn",  "Version is 0.0.0"),
    "E008": ("error", "Unknown required field (frontmatter not a flat-key subset)"),
    "E009": ("warn",  "Empty 'description'"),
    "E010": ("warn",  "Description contains TODO / FIXME / XXX"),
    "E011": ("warn",  "Missing 'when_to_use' (recommended)"),
    "E012": ("error", "YAML parse error"),
    "E013": ("warn",  "Trailing whitespace in 'description'"),
    "E014": ("warn",  "Name contains uppercase letters"),
    "E015": ("warn",  "Missing trailing newline"),
    "E016": ("warn",  "Version is pre-1.0.0 (warn only for libraries in use)"),
    "E017": ("warn",  "Description first sentence is > 100 chars"),
    "E018": ("error", "Invalid 'version' semver (E006 supersedes; retained for compat)"),
}

# Allowed frontmatter keys (flat-key YAML subset)
ALLOWED_KEYS = {"name", "description", "version", "when_to_use", "license", "author", "tags"}
REQUIRED_KEYS = {"name", "description", "version"}

# Frontmatter delimiter
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n?", re.DOTALL)
KEY_VALUE_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([-.+].+)?$")
KEBAB_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")


@dataclass
class LintRecord:
    path: str
    code: str
    level: str
    message: str
    line: int


def _parse_simple_yaml(text):
    """Parse a flat-key YAML subset (no nested mappings, no lists, no anchors)."""
    result = {}
    current_key = None
    current_value = []
    current_style = None

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if current_key is not None and (raw_line.startswith(" ") or raw_line.startswith("\t")):
            if current_style == "literal":
                current_value.append(raw_line.strip())
            else:
                current_value.append(raw_line.strip())
            continue
        if current_key is not None:
            if current_style == "literal":
                result[current_key] = "\n".join(current_value).strip()
            else:
                result[current_key] = " ".join(current_value).strip()
            current_key = None
            current_value = []
            current_style = None

        m = KEY_VALUE_RE.match(raw_line)
        if not m:
            raise ValueError("line " + str(line_no) + ": cannot parse '" + raw_line + "'")
        key, value = m.group(1), m.group(2).strip()
        if value in (">", "|"):
            current_style = "folded" if value == ">" else "literal"
            current_key = key
            current_value = []
        else:
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            result[key] = value.strip()

    if current_key is not None:
        if current_style == "literal":
            result[current_key] = "\n".join(current_value).strip()
        else:
            result[current_key] = " ".join(current_value).strip()

    return result



def _parse_frontmatter(content):
    """Extract and parse the frontmatter block. Returns (data, body_offset)."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        raise ValueError("no frontmatter block found (expected '---\n...\n---')")
    data = _parse_simple_yaml(m.group(1))
    return data, m.end()


def _check_semver(value):
    return bool(SEMVER_RE.match(value))


def _check_kebab(name):
    if not name or len(name) < 3:
        return False
    if any(c.isupper() for c in name):
        return False
    return bool(KEBAB_RE.match(name))


def _first_sentence(description):
    """Return the first sentence (text up to . ! ?, else the whole string).

    There is deliberately no length cap here. E017 fires when the first
    sentence is *longer* than 100 chars, so truncating to 100 inside this
    helper made the rule unreachable -- any description without sentence
    punctuation produced exactly 100 chars and never triggered E017.
    """
    for i, c in enumerate(description):
        if c in ".!?" and i > 0:
            return description[: i + 1]
    return description


def lint_file(path, config=None):
    """Lint a single SKILL.md file. Returns a list of LintRecord."""
    config = config or {}
    description_budget = config.get("description_budget", 800)
    records = []

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        records.append(LintRecord(str(path), "E012", "error", "Cannot read file: " + str(e), 0))
        return records

    if not content.endswith("\n"):
        records.append(LintRecord(str(path), "E015", "warn", "Missing trailing newline", 0))

    try:
        data, _ = _parse_frontmatter(content)
    except ValueError as e:
        records.append(LintRecord(str(path), "E012", "error", str(e), 0))
        return records

    for key in REQUIRED_KEYS:
        if key not in data:
            code = "E001" if key == "name" else ("E002" if key == "description" else "E006")
            records.append(LintRecord(str(path), code, "error", "Missing required field '" + key + "'", 0))

    for key in data:
        if key not in ALLOWED_KEYS:
            records.append(LintRecord(str(path), "E008", "error", "Unknown field '" + key + "'", 0))

    name = data.get("name", "")
    if name:
        short = len(name) < 3
        upper = any(c.isupper() for c in name)
        kebab_ok = _check_kebab(name)
        if short:
            records.append(LintRecord(str(path), "E005", "warn", "Name is too short (< 3 chars)", 0))
        if upper:
            records.append(LintRecord(str(path), "E014", "warn", "Name contains uppercase letters", 0))
        if not kebab_ok and not short and not upper:
            records.append(LintRecord(str(path), "E004", "error", "Invalid 'name' format (must be kebab-case)", 0))

    description = data.get("description", "")
    if description is not None:
        if not description.strip():
            records.append(LintRecord(str(path), "E009", "warn", "Empty 'description'", 0))
        else:
            if len(description) > description_budget:
                records.append(LintRecord(str(path), "E003", "warn", "Description exceeds " + str(description_budget) + " characters (got " + str(len(description)) + ")", 0))
            if description != description.rstrip():
                records.append(LintRecord(str(path), "E013", "warn", "Trailing whitespace in 'description'", 0))
            if re.search(r"\b(TODO|FIXME|XXX)\b", description, re.IGNORECASE):
                records.append(LintRecord(str(path), "E010", "warn", "Description contains TODO / FIXME / XXX", 0))
            first = _first_sentence(description)
            if len(first) > 100:
                records.append(LintRecord(str(path), "E017", "warn", "Description first sentence is > 100 chars", 0))

    version = data.get("version", "")
    if version:
        if not _check_semver(version):
            records.append(LintRecord(str(path), "E006", "error", "Invalid 'version' (must be semver): got '" + version + "'", 0))
            records.append(LintRecord(str(path), "E018", "error", "Invalid 'version' semver (compat): '" + version + "'", 0))
        if version == "0.0.0":
            records.append(LintRecord(str(path), "E007", "warn", "Version is 0.0.0", 0))
        elif version.startswith("0.") and version != "0.0.0":
            records.append(LintRecord(str(path), "E016", "warn", "Version is pre-1.0.0", 0))

    if "when_to_use" not in data:
        records.append(LintRecord(str(path), "E011", "warn", "Missing 'when_to_use' (recommended)", 0))

    return records


def lint_paths(paths, config=None):
    """Lint a list of paths (files or directories). Returns all LintRecord."""
    config = config or {}
    ignore_patterns = config.get("ignore", [])
    all_records = []

    for p in paths:
        p = Path(p)
        if p.is_dir():
            for child in sorted(p.rglob("SKILL.md")):
                if any(fnmatch.fnmatch(str(child), pat) for pat in ignore_patterns):
                    continue
                all_records.extend(lint_file(child, config))
        elif p.is_file():
            if any(fnmatch.fnmatch(str(p), pat) for pat in ignore_patterns):
                continue
            all_records.extend(lint_file(p, config))
    return all_records


def _load_config(path):
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _apply_strict(records, strict):
    if not strict:
        return records
    out = []
    for r in records:
        if r.level == "warn":
            out.append(LintRecord(r.path, r.code, "error", r.message, r.line))
        else:
            out.append(r)
    return out


def _format_human(records):
    if not records:
        return "no issues"
    by_path = {}
    for r in records:
        by_path.setdefault(r.path, []).append(r)
    lines = []
    for path in sorted(by_path):
        lines.append("\n" + path)
        for r in by_path[path]:
            lines.append("  " + r.code + " [" + r.level + "] " + r.message)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tiny-skill-lint",
        description="Lint SKILL.md frontmatter (zero deps).",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to lint")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    parser.add_argument("--strict", action="store_true", help="Promote warnings to errors")
    parser.add_argument("--config", type=Path, default=None, help="Path to lint.config.json")
    args = parser.parse_args(argv)

    config = _load_config(args.config)
    if args.strict:
        config["strict"] = True

    paths = [Path(p) for p in args.paths]
    records = lint_paths(paths, config)
    records = _apply_strict(records, config.get("strict", False))

    if args.format == "json":
        print(json.dumps([asdict(r) for r in records], indent=2))
    else:
        print(_format_human(records))

    has_error = any(r.level == "error" for r in records)
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
