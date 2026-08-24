"""Shared fixtures.

flavorforge.py is a single module that builds its GUI only under
``if __name__ == "__main__"``, so importing it is cheap and no window appears.

Since 3.1 the tkinter import is guarded, so the data, the engine and the CLI
import and run on a machine with no GUI toolkit at all — which is what makes
these tests runnable anywhere, and the CLI usable over SSH. The handful of
tests that need Tk say so individually.
"""
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
def cli(capsys):
    """Run the CLI and hand back (exit_code, stdout, stderr)."""
    def _run(*argv):
        code = ff.run_cli(list(argv))
        out = capsys.readouterr()
        return code, out.out, out.err
    return _run
