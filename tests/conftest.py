"""Shared fixtures.

flavorforge.py is a single module that builds its GUI only under
``if __name__ == "__main__"``, so importing it is cheap and no window appears.

Since 3.1 the tkinter import is guarded, so the data, the engine and the CLI
import and run on a machine with no GUI toolkit at all — which is what makes
these tests runnable anywhere, and the CLI usable over SSH. The handful of
tests that need Tk say so individually.
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import flavorforge as ff  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    """One FlavorEngine for the session — its __init__ precomputes compound
    frequencies over the whole database and nothing mutates it."""
    return ff.FlavorEngine()


@pytest.fixture(scope="session")
def ffmod():
    return ff


@pytest.fixture
def no_gui():
    """Skip a GUI test where there is no Tk or no display -- or, in CI, fail it.

    CI sets FLAVORFORGE_REQUIRE_GUI=1 on every leg. A GUI test that skips
    there still lets the run pass: until 3.3 added Xvfb, every Linux leg
    skipped all of them and the green result said nothing about it. With the
    variable set, a leg that cannot open a window is red instead.
    """
    def _no_gui(reason):
        if os.environ.get("FLAVORFORGE_REQUIRE_GUI") == "1":
            pytest.fail(f"GUI tests are required in this run, but {reason}")
        pytest.skip(reason)
    return _no_gui


@pytest.fixture
def cli(capsys):
    """Run the CLI and hand back (exit_code, stdout, stderr)."""
    def _run(*argv):
        code = ff.run_cli(list(argv))
        out = capsys.readouterr()
        return code, out.out, out.err
    return _run
