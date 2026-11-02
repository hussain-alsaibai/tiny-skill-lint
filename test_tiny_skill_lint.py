"""Tests for tiny-skill-lint. Run with: python -m pytest test_tiny_skill_lint.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tiny_skill_lint as tsl


def make_skill(content):
    """Write content to a temp SKILL.md and return the path."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='SKILL.md', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return Path(f.name)


GOOD = """---
name: tiny-cache
description: A zero-dep LRU+TTL cache for Python.
version: 0.7.0
when_to_use: Cache hot lookups in agent pipelines.
---

# tiny-cache
"""


class TestRequiredFields(unittest.TestCase):
    def test_missing_name(self):
        p = make_skill("---\ndescription: foo\nversion: 1.0.0\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E001", codes)

    def test_missing_description(self):
        p = make_skill("---\nname: foo-bar\nversion: 1.0.0\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E002", codes)

    def test_missing_version(self):
        p = make_skill("---\nname: foo-bar\ndescription: A test.\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        # Missing version -> E006 (semver required)
        self.assertIn("E006", codes)

    def test_good_minimal(self):
        p = make_skill(GOOD)
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        # No errors expected; only the optional E011 (when_to_use) should be absent because it's there
        self.assertNotIn("E001", codes)
        self.assertNotIn("E002", codes)
        self.assertNotIn("E006", codes)
        self.assertNotIn("E011", codes)


class TestNameFormat(unittest.TestCase):
    def test_uppercase_name(self):
        p = make_skill("---\nname: FooBar\ndescription: A test.\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E014", codes)

    def test_short_name(self):
        p = make_skill("---\nname: ab\ndescription: A test.\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E005", codes)

    def test_invalid_kebab(self):
        p = make_skill("---\nname: foo_bar\ndescription: A test.\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E004", codes)


class TestDescription(unittest.TestCase):
    def test_budget_overrun(self):
        desc = "x" * 900
        p = make_skill(f"---\nname: foo-bar\ndescription: {desc}\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E003", codes)

    def test_empty_description(self):
        p = make_skill("---\nname: foo-bar\ndescription: \nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E009", codes)

    def test_todo_in_description(self):
        p = make_skill("---\nname: foo-bar\ndescription: A test. TODO write more.\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E010", codes)

    def test_long_first_sentence(self):
        sentence = "x" * 120
        p = make_skill(f"---\nname: foo-bar\ndescription: {sentence}\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E017", codes)


class TestVersion(unittest.TestCase):
    def test_invalid_semver(self):
        p = make_skill("---\nname: foo-bar\ndescription: A test.\nversion: 1.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E006", codes)
        self.assertIn("E018", codes)

    def test_zero_zero_zero(self):
        p = make_skill("---\nname: foo-bar\ndescription: A test.\nversion: 0.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E007", codes)

    def test_pre_1_0(self):
        p = make_skill("---\nname: foo-bar\ndescription: A test.\nversion: 0.5.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E016", codes)

    def test_valid_semver(self):
        p = make_skill("---\nname: foo-bar\ndescription: A test.\nversion: 1.2.3\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertNotIn("E006", codes)


class TestUnknownKeys(unittest.TestCase):
    def test_unknown_field(self):
        p = make_skill("---\nname: foo-bar\ndescription: A test.\nversion: 1.0.0\nwhen_to_use: x\nfoo: bar\n---\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E008", codes)


class TestYAMLParsing(unittest.TestCase):
    def test_multiline_value(self):
        p = make_skill("---\nname: foo-bar\ndescription: >\n  A long description\n  that spans multiple lines.\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        # Should not produce E012 (parse error)
        codes = [r.code for r in recs]
        self.assertNotIn("E012", codes)

    def test_quoted_value(self):
        p = make_skill('---\nname: foo-bar\ndescription: "A test."\nversion: 1.0.0\nwhen_to_use: x\n---\n')
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertNotIn("E012", codes)

    def test_no_frontmatter(self):
        p = make_skill("# just a markdown file\n")
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E012", codes)


class TestStrictMode(unittest.TestCase):
    def test_strict_promotes_warnings(self):
        p = make_skill("---\nname: foo-bar\ndescription: A test.\nversion: 1.0.0\n---\n")
        recs = tsl.lint_file(p)
        # E011 (when_to_use) is a warning
        warn_codes = [r for r in recs if r.code == "E011"]
        self.assertEqual(len(warn_codes), 1)
        self.assertEqual(warn_codes[0].level, "warn")
        # Apply strict
        strict = tsl._apply_strict(recs, True)
        promoted = [r for r in strict if r.code == "E011"]
        self.assertEqual(promoted[0].level, "error")


class TestOutputFormats(unittest.TestCase):
    def test_format_human_no_issues(self):
        out = tsl._format_human([])
        self.assertIn("no issues", out)

    def test_format_human_groups_by_path(self):
        recs = [
            tsl.LintRecord("a/SKILL.md", "E001", "error", "missing name", 0),
            tsl.LintRecord("a/SKILL.md", "E002", "error", "missing desc", 0),
            tsl.LintRecord("b/SKILL.md", "E001", "error", "missing name", 0),
        ]
        out = tsl._format_human(recs)
        self.assertIn("a/SKILL.md", out)
        self.assertIn("b/SKILL.md", out)

    def test_lintrecord_serialisable(self):
        r = tsl.LintRecord("p", "E001", "error", "msg", 0)
        d = tsl.asdict(r)
        self.assertEqual(d["code"], "E001")


class TestConfig(unittest.TestCase):
    def test_description_budget_override(self):
        p = make_skill("---\nname: foo-bar\ndescription: x\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        # With default 800, single char should NOT trigger E003
        recs = tsl.lint_file(p, config={})
        codes = [r.code for r in recs]
        self.assertNotIn("E003", codes)

    def test_ignore_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "SKILL.md").write_text("---\nname: foo\ndescription: x\nversion: 1.0.0\n---\n")
            recs = tsl.lint_paths([tmp_path], config={"ignore": ["**/SKILL.md"]})
            self.assertEqual(len(recs), 0)


class TestLintingFlow(unittest.TestCase):
    def test_directory_recursion(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sub1 = tmp_path / "a"
            sub1.mkdir()
            sub2 = tmp_path / "b"
            sub2.mkdir()
            (sub1 / "SKILL.md").write_text(GOOD)
            (sub2 / "SKILL.md").write_text("---\nname: Foo\ndescription: x\nversion: 1.0.0\nwhen_to_use: x\n---\n")
            recs = tsl.lint_paths([tmp_path])
            # Sub a: GOOD -> no errors. Sub b: E014 (uppercase).
            paths = set(r.path for r in recs)
            self.assertTrue(any("a" in p for p in paths))
            self.assertTrue(any("b" in p for p in paths))


class TestFirstSentenceRegression(unittest.TestCase):
    """E017 must be reachable.

    The helper used to cap the first sentence at 100 chars, which meant
    the "> 100 chars" condition could never be true. A description with
    no sentence punctuation silently produced exactly 100 chars and the
    rule never fired. These tests pin the reachable behaviour.
    """

    def test_long_first_sentence_without_punctuation_fires(self):
        # No "." "!" or "?" anywhere: the whole string is the first sentence.
        sentence = "x" * 120
        p = make_skill(f"---\nname: foo-bar\ndescription: {sentence}\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        self.assertIn("E017", [r.code for r in recs])

    def test_exactly_100_chars_does_not_fire(self):
        sentence = "x" * 100
        p = make_skill(f"---\nname: foo-bar\ndescription: {sentence}\nversion: 1.0.0\nwhen_to_use: x\n---\n")
        recs = tsl.lint_file(p)
        self.assertNotIn("E017", [r.code for r in recs])

    def test_short_description_does_not_fire(self):
        p = make_skill(GOOD)
        recs = tsl.lint_file(p)
        self.assertNotIn("E017", [r.code for r in recs])

    def test_long_first_sentence_is_measured_to_the_period(self):
        # 130 chars before the period, then more text after it.
        first = "y" * 130
        p = make_skill(
            f"---\nname: foo-bar\ndescription: {first}. trailing words\n"
            "version: 1.0.0\nwhen_to_use: x\n---\n"
        )
        recs = tsl.lint_file(p)
        self.assertIn("E017", [r.code for r in recs])


class TestErrorCatalogue(unittest.TestCase):
    def test_18_codes_present(self):
        self.assertEqual(len(tsl.ERROR_CODES), 18)

    def test_codes_are_e001_to_e018(self):
        for i in range(1, 19):
            self.assertIn(f"E{i:03d}", tsl.ERROR_CODES)


class TestTrailingNewline(unittest.TestCase):
    def test_no_trailing_newline(self):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='SKILL.md', delete=False, encoding='utf-8')
        f.write(GOOD.rstrip('\n'))  # no trailing newline
        f.close()
        p = Path(f.name)
        recs = tsl.lint_file(p)
        codes = [r.code for r in recs]
        self.assertIn("E015", codes)


if __name__ == "__main__":
    unittest.main()
