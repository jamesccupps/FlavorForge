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
import time
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
def build_gui(ffmod, no_gui):
    """Construct the real window, retrying a Tk start-up that fails transiently.

    On Windows with Tk 8.6 (Python 3.10-3.13), creating many Tk interpreters
    in one process occasionally fails to read Tcl's own init.tcl: "couldn't
    read file .../tcl8.6/init.tcl: no such file or directory", for a file
    that is there and that the interpreters before and after read without
    trouble. CI annotations showed it on one GUI test per leg, a different
    one each run; Tk 9.0 legs never did. The old fixture skipped on any
    error, which hid it. A user's run creates one interpreter, so this is a
    harness problem and is handled here, not in the app.
    """
    def _build():
        if not ffmod.HAVE_TK:
            no_gui("tkinter is not installed")
        error = None
        for attempt in range(3):
            try:
                return ffmod.FlavorForgeGUI()
            except ffmod.tk.TclError as exc:      # transient on Tk 8.6, or no display
                error = exc
                time.sleep(0.25 * (attempt + 1))
        no_gui(f"a Tk root could not be created after 3 tries: {error}")
    return _build


@pytest.fixture
def cli(capsys):
    """Run the CLI and hand back (exit_code, stdout, stderr)."""
    def _run(*argv):
        code = ff.run_cli(list(argv))
        out = capsys.readouterr()
        return code, out.out, out.err
    return _run
