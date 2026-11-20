"""tools/release_notes.py, which the release workflow runs on every tag.

Tested here because the workflow itself only runs when a release is cut, and
a broken notes step would be found then, in public.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("release_notes", ROOT / "tools" / "release_notes.py")
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

SAMPLE = """# Changelog

## [2.0.0] — 2026-01-02

A paragraph that wraps
onto a second line.

### Fixed

- **An item** that also
  wraps.
- A second item.

## [1.0.0] — 2026-01-01

Older.
"""


def test_the_section_stops_at_the_next_version():
    body = rn.section(SAMPLE, "v2.0.0")
    assert body.startswith("A paragraph") and "Older." not in body


def test_the_last_section_runs_to_the_end():
    assert rn.section(SAMPLE, "1.0.0") == "Older."


def test_wrapped_lines_are_joined_and_structure_kept():
    out = rn.unwrap(rn.section(SAMPLE, "2.0.0"))
    assert "A paragraph that wraps onto a second line." in out
    assert "- **An item** that also wraps." in out
    assert "\n- A second item." in out
    assert "\n### Fixed\n" in out


def test_an_unknown_version_fails_rather_than_publishing_nothing():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "release_notes.py"), "v0.0.1"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "no section" in r.stderr


def test_the_current_version_has_notes(ffmod):
    """The release job fails if this does, so fail here first."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "release_notes.py"),
                        "v" + ffmod.__version__], capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0 and len(r.stdout) > 100, r.stderr
