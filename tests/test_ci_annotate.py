"""tools/ci_annotate.py, which CI runs after a failed test step so failures
are readable without signing in to GitHub."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("ci_annotate", ROOT / "tools" / "ci_annotate.py")
ca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ca)

REPORT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3" failures="1" errors="1">
  <testcase classname="tests.test_a" name="test_ok" time="0.1"/>
  <testcase classname="tests.test_a" name="test_bad" time="0.1">
    <failure message="assert 1 == 2">line one
line two 100%
E   assert 1 == 2</failure>
  </testcase>
  <testcase classname="tests.test_gui" name="test_window" time="0.1">
    <error message="TclError">E   _tkinter.TclError: no display</error>
  </testcase>
</testsuite></testsuites>
"""


def test_each_failure_and_error_becomes_one_annotation():
    out = list(ca.annotations(REPORT))
    assert len(out) == 2
    assert out[0].startswith("::error title=failure: tests.test_a::test_bad::")
    assert out[1].startswith("::error title=error: tests.test_gui::test_window::")


def test_the_message_is_escaped_for_a_workflow_command():
    first = list(ca.annotations(REPORT))[0]
    assert "\n" not in first and "%0A" in first
    assert "100%25" in first, "a literal % must be escaped first"


def test_a_clean_report_prints_nothing():
    clean = '<testsuites><testsuite><testcase classname="a" name="b"/></testsuite></testsuites>'
    assert list(ca.annotations(clean)) == []
