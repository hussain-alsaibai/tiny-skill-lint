"""tiny-skill-scan: detect instruction-carrying content in a SKILL.md body.

The frontmatter linter in ``tiny_skill_lint`` answers "is this document
well-formed?". It says nothing about *what the document tells the agent to
do*, and a well-formed SKILL.md is the cheapest possible delivery vehicle
for a prompt injection: the agent loads it as instructions, by design.

Three vectors matter, and they are the three that shipped in the wild in
November 2026 (usestrix/strix#1760 and the SKILL.md scanners that landed
the same week in marveen, NeuralTrust/TrustGate, OpenJarvis):

1. **Authority override** -- text that tells the agent to disregard its
   system prompt, its safety rules, or the user.
2. **Exfiltration** -- text that tells it to send file contents, env vars,
   keys, or conversation history somewhere.
3. **Invisible payload** -- injected instructions in content a human
   reviewer does not read: HTML comments, zero-width characters, bidi
   controls, or an entire body fenced as a "example output" the agent is
   told to follow.

The design rule here is the same one that applies to a secret scanner: a
finding must be *reviewable*. Every result carries the line number, the
matched span, and one sentence explaining why it is suspicious. Nothing is
auto-fixed and nothing is silently dropped.

Zero dependencies, Python 3.8+. Usage::

    python -m tiny_skill_lint.scan skills/
    python -m tiny_skill_lint.scan SKILL.md --format json --strict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

__version__ = "0.4.0"


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------
# Codes are prefixed S (skill). Severity is deliberately coarse: 'high'
# findings are near-always malicious in a skill body, 'low' are shapes that
# are common in legitimate skills and need a human to decide.
#
# The rule for adding a pattern: it must be a shape a *legitimate* skill
# would not need. "ignore" alone is idiomatic ("ignore the node_modules
# directory"); "ignore all previous instructions" is not.

RULES: Dict[str, Tuple[str, str]] = {
    "S001": (
        "high",
        "Authority override: instructs the agent to discard earlier instructions",
    ),
    "S002": (
        "high",
        "Authority override: claims a higher-priority sender or system role",
    ),
    "S003": (
        "high",
        "Exfiltration: directs data to an external endpoint",
    ),
    "S004": (
        "high",
        "Exfiltration: asks for credentials, keys, or environment values in output",
    ),
    "S005": (
        "high",
        "Invisible payload: instructions hidden in an HTML comment",
    ),
    "S006": (
        "high",
        "Invisible payload: zero-width or bidi control characters",
    ),
    "S007": (
        "medium",
        "Concealment: tells the agent not to mention an action to the user",
    ),
    "S008": (
        "medium",
        "Execution: pipes a remote document straight into a shell",
    ),
    "S009": (
        "medium",
        "Scope creep: grants itself permission the user did not give",
    ),
    "S010": (
        "low",
        "Review note: fenced block labelled as output to reproduce verbatim",
    ),
}

# --- S001: authority override ------------------------------------------------
# "ignore/disregard/forget ... (all|any|the)? (previous|prior|above|earlier)
#  (instructions|prompts|rules|directives)"
_S001 = re.compile(
    r"\b(?:ignore|disregard|forget|override|bypass|overrule)\b"
    r"[^.\n]{0,40}?"
    r"\b(?:all\s+|any\s+|the\s+|your\s+)?"
    r"(?:previous|prior|above|earlier|preceding|former|original|system)\b"
    r"[^.\n]{0,20}?"
    r"\b(?:instructions?|prompts?|rules?|directives?|guidelines?|constraints?)\b",
    re.IGNORECASE,
)

# --- S002: false authority ---------------------------------------------------
_S002 = re.compile(
    r"(?:"
    r"\byou\s+are\s+now\s+(?:a|an|the|in)\b"
    r"|\bnew\s+(?:system\s+)?instructions?\s*:"
    r"|\bsystem\s*:\s*you\s+(?:are|must|will)\b"
    r"|\b(?:the\s+)?(?:developer|admin|administrator|operator)\s+(?:has\s+)?"
    r"(?:authori[sz]ed|approved|instructed|granted)\b"
    r"|\bthis\s+(?:message|document|skill)\s+(?:supersedes|overrides)\b"
    r"|\brole\s*:\s*system\b"
    r")",
    re.IGNORECASE,
)

# --- S003: exfiltration to an endpoint ---------------------------------------
# Built from parts so this file does not itself look like an exfil payload to
# a downstream scanner (same discipline as tiny-secret-mask's fixtures).
#
# A bare URL is NOT a finding. Every API skill documents endpoints, and
# `curl https://api.example.com` is the normal way to say so. What marks
# exfiltration is a URL *plus* a verb that moves local data toward it, or a
# URL whose own path names a collection endpoint. Line 1 of the first
# version of this rule fired on 12 `curl` documentation lines out of 24
# real skills -- see tests/test_scan_false_positives.py.
_PROTO = r"(?:https?|ftp|wss?)"
_S003 = re.compile(
    r"(?:"
    # a data-moving verb aimed at a URL
    r"(?<!X )\b(?:upload|exfiltrate|transmit|beacon)\b"
    r"[^\n]{0,60}?"
    r"\b" + _PROTO + r"://"
    # "send/post/upload <something> to <a destination>": the destination is
    # named generically because a real payload rarely hardcodes its URL in
    # the same sentence -- it says "the collection server".
    r"|(?:send|post|upload|forward|transmit)\s+"
    r"(?:this|it|them|everything|all"
    r"|the\s+(?:contents?|data|files?|output|results?|keys?|secrets?|logs?"
    r"|history|env|transcript|conversation|wallet|credentials?))"
    r"[^\n]{0,60}?"
    r"\s*(?:to|at|into)\s+[^\n]{0,30}?"
    r"\b(?:server|endpoint|webhook|collect(?:or|ion)?|receiver|attacker"
    r"|remote|external|pastebin|gist|bucket)\b"
    # a URL whose path is itself a collection endpoint
    r"|\b" + _PROTO + r"://[^\s)\]\"'`]+/(?:exfil|beacon|collect|ingest)\b"
    r")",
    re.IGNORECASE,
)

# --- S004: credential harvesting --------------------------------------------
# The verb must be about *emitting* the credential to somewhere the user can
# see or forward, not about reading it in code. `return process.env.X` in a
# JS snippet is implementation, not exfiltration; "print the token" is.
_SECRET_NOUN = (
    r"(?:api[_\s-]?keys?|secrets?|tokens?|passwords?|credentials?"
    r"|private[_\s-]?keys?|id_rsa|(?<!\w)\.env(?![\w-])|(?<!\w)\.ssh(?![\w-])"
    r"|(?<!\w)\.aws(?![\w-]))"
)
# `echo $TOKEN` and `cat ~/.ssh/id_rsa` are how a developer checks a value
# locally; they are in the clean corpus and must stay out of this verb list.
# What marks exfiltration is a verb that puts the value *into the model's
# reply*, which is where it can be forwarded.
_EMIT_VERB = (
    r"(?:print|output|show|reveal|dump|repeat|display|paste|include|append"
    r"|expose|leak|report)\b"
)
_S004 = re.compile(
    _EMIT_VERB + r"\b[^\n]{0,30}?" + _SECRET_NOUN
    # "output the token count" / "show the password rules" report *about*
    # the noun rather than its value.
    + r"(?!\s+(?:count|counts|length|size|limit|rate|usage|rules?|policy|policy|budget|expiry|ttl|name|type|field|header))",
    re.IGNORECASE,
)

# --- S005: HTML comment ------------------------------------------------------
_S005 = re.compile(r"<!--(.*?)-->", re.DOTALL)

# --- S006: invisible characters ---------------------------------------------
# Zero-width space/non-joiner/joiner, word joiner, BOM, and the bidi controls
# that let text render one way and read another.
_INVISIBLE = {
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
    "\ufeff": "ZERO WIDTH NO-BREAK SPACE (BOM)",
    "\u202a": "LEFT-TO-RIGHT EMBEDDING",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING",
    "\u202c": "POP DIRECTIONAL FORMATTING",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
    "\u2066": "LEFT-TO-RIGHT ISOLATE",
    "\u2067": "RIGHT-TO-LEFT ISOLATE",
    "\u2068": "FIRST STRONG ISOLATE",
    "\u2069": "POP DIRECTIONAL ISOLATE",
}

# A single zero-width char is common in copied text; a run of three or more
# is a signature. Bidi overrides are flagged at any count.
_RUN_THRESHOLD = 3

# --- S007: concealment -------------------------------------------------------
_S007 = re.compile(
    r"(?:"
    r"\b(?:do\s+not|don't|never|without)\s+(?:tell|inform|alert|warn|notify|mention)"
    r"\s+(?:the\s+)?(?:user|human|operator|requester)\b"
    r"|\bhide\s+(?:this|the\s+fact|that)\b"
    r"|\bkeep\s+(?:this|it)\s+(?:secret|hidden|quiet)\b"
    r"|\bwithout\s+(?:the\s+)?(?:user|human)(?:'s)?\s+(?:knowing|noticing|consent)\b"
    r")",
    re.IGNORECASE,
)

# --- S008: remote content into a shell --------------------------------------
_S008 = re.compile(
    r"(?:"
    r"\b(?:curl|wget)\b[^\n|]{0,120}\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b"
    r"|\b(?:curl|wget)\b[^\n;]{0,120}?\s-o\s*\S+\s*&&\s*(?:sudo\s+)?(?:ba|z)?sh\b"
    r"|\biex\s*\(|Invoke-Expression\b"
    r")",
    re.IGNORECASE,
)

# --- S009: self-granted scope ----------------------------------------------
_S009 = re.compile(
    r"(?:"
    r"\byou\s+(?:now\s+)?have\s+(?:full|unrestricted|unlimited|complete)\s+"
    r"(?:access|permissions?|authority)\b"
    r"|\byou\s+(?:are|have\s+been)\s+(?:authori[sz]ed|permitted|allowed)\s+to\b[^.\n]{0,40}?"
    r"\b(?:without|regardless\s+of|ignoring)\b"
    r"|\bno\s+(?:further\s+)?(?:confirmation|approval|permission)\s+(?:is\s+)?(?:needed|required)"
    r")",
    re.IGNORECASE,
)

# --- S010: verbatim-output fence -------------------------------------------
# A fence whose info string or preceding line says "output", "response",
# "reply" is a shape where the file supplies the model's answer.
_S010_INFO = re.compile(
    r"^\s*(?:```|~~~)\s*(?:output|response|reply|answer|assistant)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# Rules that only make sense as prose instructions. Inside a fence they are
# almost always a documented example.
_PROSE_ONLY = {"S001", "S002", "S007", "S009"}


@dataclass
class Finding:
    """One suspicious span in one file."""

    code: str
    severity: str
    message: str
    line: int
    column: int
    excerpt: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "excerpt": self.excerpt,
        }


@dataclass
class ScanResult:
    path: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def worst(self) -> str:
        order = {"high": 3, "medium": 2, "low": 1}
        if not self.findings:
            return "clean"
        return max((f.severity for f in self.findings), key=lambda s: order[s])

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "worst": self.worst,
            "findings": [f.as_dict() for f in self.findings],
        }


def _line_of(text: str, index: int) -> Tuple[int, int]:
    """1-based line and column for a character index."""
    line = text.count("\n", 0, index) + 1
    last_nl = text.rfind("\n", 0, index)
    return line, index - last_nl


def _excerpt(text: str, start: int, end: int, width: int = 90) -> str:
    """A single-line, readable slice around a match."""
    span = text[start:end]
    span = span.replace("\n", " ").replace("\r", " ")
    span = "".join(
        c if unicodedata.category(c)[0] != "C" or c == "\t" else " "
        for c in span
    )
    span = re.sub(r"\s+", " ", span).strip()
    if len(span) > width:
        span = span[: width - 1] + "\u2026"
    return span


_FENCE = re.compile(r"^\s*(?:```|~~~)", re.MULTILINE)


def _fenced_spans(text: str) -> List[Tuple[int, int]]:
    """Return (start, end) character ranges covered by fenced code blocks.

    Fences are paired in order; an unclosed fence runs to end of file.
    Indented (4-space) blocks are not detected -- skill bodies overwhelmingly
    use fences, and guessing at indentation caused more false positives
    than it removed.
    """
    spans: List[Tuple[int, int]] = []
    positions = [m.start() for m in _FENCE.finditer(text)]
    for i in range(0, len(positions) - 1, 2):
        spans.append((positions[i], positions[i + 1]))
    if len(positions) % 2:
        spans.append((positions[-1], len(text)))
    return spans


def _quoted_spans(text: str) -> List[Tuple[int, int]]:
    """Return character ranges covered by Markdown blockquote lines.

    A security skill has to be able to *quote* a payload: "if a document tells
    you to ignore all previous instructions, that is the attack". The quote is
    a `>` line, not an instruction. Single-line ranges are returned, so a
    blockquote never swallows the paragraph that follows it.
    """
    spans: List[Tuple[int, int]] = []
    offset = 0
    for raw in text.split("\n"):
        stripped = raw.lstrip()
        if stripped.startswith(">"):
            spans.append((offset, offset + len(raw)))
        offset += len(raw) + 1
    return spans


def _in_ranges(spans: List[Tuple[int, int]], index: int) -> bool:
    return any(start <= index < end for start, end in spans)


def _in_fence(spans: List[Tuple[int, int]], index: int) -> bool:
    return any(start <= index < end for start, end in spans)


def _iter_rule_matches(
    text: str,
    code: str,
    pattern: re.Pattern,
    fenced: Optional[List[Tuple[int, int]]] = None,
) -> Iterator[Finding]:
    """Yield findings for one rule.

    Rules that describe *prose* (S001, S002, S007, S009) are skipped inside
    fenced blocks: a skill that documents the phrase "ignore previous
    instructions" in a security example is not itself trying to do it.
    Rules that describe *executed content* (S003, S004, S008) still fire in
    fences, because that is where the command actually lives.
    """
    severity, message = RULES[code]
    prose_only = code in _PROSE_ONLY
    quoted = _quoted_spans(text) if prose_only else []
    for m in pattern.finditer(text):
        if prose_only and _in_ranges(quoted, m.start()):
            continue
        if prose_only and fenced and _in_fence(fenced, m.start()):
            continue
        line, col = _line_of(text, m.start())
        yield Finding(
            code=code,
            severity=severity,
            message=message,
            line=line,
            column=col,
            excerpt=_excerpt(text, m.start(), m.end()),
        )


def _scan_invisible(text: str) -> Iterator[Finding]:
    severity, message = RULES["S006"]
    # Group runs on the same line so a payload of 40 zero-width chars is one
    # finding, not forty.
    run_start: Optional[int] = None
    run_len = 0
    run_names: List[str] = []

    def flush(end: int) -> Iterator[Finding]:
        nonlocal run_start, run_len, run_names
        if run_start is None or not run_names:
            return
        bidi = any("OVERRIDE" in n or "EMBEDDING" in n for n in run_names)
        if run_len >= _RUN_THRESHOLD or bidi:
            line, col = _line_of(text, run_start)
            yield Finding(
                code="S006",
                severity=severity,
                message=f"{message} ({', '.join(sorted(set(run_names)))})",
                line=line,
                column=col,
                excerpt=f"{run_len} invisible character(s)",
            )
        run_start, run_len, run_names = None, 0, []

    for i, ch in enumerate(text):
        if ch in _INVISIBLE:
            if run_start is None:
                run_start = i
            run_len += 1
            run_names.append(_INVISIBLE[ch])
        else:
            yield from flush(i)
    yield from flush(len(text))


def _scan_isolate_pairs(text: str) -> Iterator[Finding]:
    """Flag directional *isolates* only when they come in a matched pair.

    Unlike an override or an embedding, a single isolate is a normal way to
    write mixed-direction prose, and refusing it would make the scanner
    useless on any Arabic, Hebrew, or Persian skill. The abusive shape is a
    matched open/close pair wrapped around a span inside otherwise
    left-to-right text: the span renders in a different order from how it
    reads in the raw file.
    """
    opens = [c for c in ("\u2066", "\u2067", "\u2068") if c in text]
    if not opens or "\u2069" not in text:
        return
    severity, message = RULES["S006"]
    first_open = min(text.index(c) for c in opens)
    if first_open > text.index("\u2069"):
        return
    line, col = _line_of(text, first_open)
    yield Finding(
        code="S006",
        severity=severity,
        message=message + " (matched directional isolates)",
        line=line,
        column=col,
        excerpt="directional isolate pair",
    )


def _scan_html_comments(text: str) -> Iterator[Finding]:
    severity, message = RULES["S005"]
    for m in _S005.finditer(text):
        inner = m.group(1)
        # A comment is only interesting if it carries instruction-shaped text.
        # Licence headers and `<!-- prettier-ignore -->` are everywhere.
        instruction_shaped = bool(
            _S001.search(inner)
            or _S002.search(inner)
            or _S003.search(inner)
            or _S004.search(inner)
            or _S007.search(inner)
            or _S009.search(inner)
            or re.search(
                r"\b(?:you|agent|assistant|claude|model|llm)\b[^.\n]{0,40}"
                r"\b(?:must|should|always|never|now)\b",
                inner,
                re.IGNORECASE,
            )
        )
        if not instruction_shaped:
            continue
        line, col = _line_of(text, m.start())
        yield Finding(
            code="S005",
            severity=severity,
            message=message,
            line=line,
            column=col,
            excerpt=_excerpt(text, m.start(), min(m.end(), m.start() + 200)),
        )


def strip_frontmatter(text: str, *, preserve_lines: bool = True) -> str:
    """Return only the body, so frontmatter prose is not double-reported.

    Handles the leading ``---`` block only. A file without one is returned
    unchanged.

    With ``preserve_lines`` (the default) the removed frontmatter is replaced
    by the same number of newlines, so a finding's line number still refers
    to the file the user will open. Blanking the text but keeping the line
    count is the difference between a useful report and one that points at
    the wrong paragraph.
    """
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    newline = text.find("\n", end + 4)
    if newline == -1:
        return "\n" * text.count("\n") if preserve_lines else ""
    body = text[newline:]
    if not preserve_lines:
        return body
    removed = text[:newline]
    return "\n" * removed.count("\n") + body


def scan_text(text: str, *, include_frontmatter: bool = False) -> List[Finding]:
    """Scan one document body and return its findings, sorted by position."""
    body = text if include_frontmatter else strip_frontmatter(text)
    fenced = _fenced_spans(body)

    findings: List[Finding] = []
    for code in ("S001", "S002", "S003", "S004", "S007", "S008", "S009"):
        findings.extend(
            _iter_rule_matches(body, code, globals()["_" + code], fenced)
        )
    findings.extend(_scan_html_comments(body))
    findings.extend(_scan_invisible(body))
    findings.extend(_scan_isolate_pairs(body))
    for m in _S010_INFO.finditer(body):
        severity, message = RULES["S010"]
        line, col = _line_of(body, m.start())
        findings.append(
            Finding(
                code="S010",
                severity=severity,
                message=message,
                line=line,
                column=col,
                excerpt=_excerpt(body, m.start(), m.end()),
            )
        )

    findings.sort(key=lambda f: (f.line, f.column))
    return findings


def scan_file(path: str | Path, *, include_frontmatter: bool = False) -> ScanResult:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    return ScanResult(
        path=str(p), findings=scan_text(text, include_frontmatter=include_frontmatter)
    )


def iter_skill_files(root: str | Path) -> Iterator[Path]:
    """Yield SKILL.md files under a path (or the path itself if it is one)."""
    root = Path(root)
    if root.is_file():
        yield root
        return
    for candidate in sorted(root.rglob("SKILL.md")):
        yield candidate


def scan_paths(
    paths: Iterable[str | Path], *, include_frontmatter: bool = False
) -> List[ScanResult]:
    results: List[ScanResult] = []
    for raw in paths:
        for f in iter_skill_files(raw):
            results.append(scan_file(f, include_frontmatter=include_frontmatter))
    return results


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _format_human(results: List[ScanResult]) -> str:
    out: List[str] = []
    for r in results:
        if not r.findings:
            continue
        out.append(f"{r.path}  [{r.worst.upper()}]")
        for f in r.findings:
            out.append(
                f"  {f.line}:{f.column}  {f.code} {f.severity:<6} {f.message}"
            )
            if f.excerpt:
                out.append(f"           > {f.excerpt}")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tiny-skill-scan",
        description="Detect instruction-carrying content in SKILL.md bodies.",
    )
    parser.add_argument("paths", nargs="+", help="SKILL.md files or directories")
    parser.add_argument(
        "--format", choices=("human", "json"), default="human", help="output format"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero on any finding (default: only on high severity)",
    )
    parser.add_argument(
        "--include-frontmatter",
        action="store_true",
        help="also scan the YAML frontmatter block",
    )
    args = parser.parse_args(argv)

    results = scan_paths(args.paths, include_frontmatter=args.include_frontmatter)

    if args.format == "json":
        print(json.dumps([r.as_dict() for r in results], indent=2))
    else:
        human = _format_human(results)
        if human:
            print(human)
        else:
            print("clean: no findings")

    total = sum(len(r.findings) for r in results)
    if args.strict:
        return 1 if total else 0
    return 1 if any(f.severity == "high" for r in results for f in r.findings) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
