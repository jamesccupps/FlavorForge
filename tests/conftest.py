"""Shared fixtures.

flavorforge.py is a single module that imports tkinter at the top and builds
its GUI only under ``if __name__ == "__main__"``, so importing it is safe and
cheap — no window appears. tkinter itself must be importable, which it is on
any stock CPython (CI installs python3-tk on the Linux legs).
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

pytest.importorskip("tkinter", reason="flavorforge imports tkinter at module level")

import flavorforge as ff  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    """One FlavorEngine for the session — its __init__ precomputes compound
    frequencies over the whole database and nothing mutates it."""
    return ff.FlavorEngine()


@pytest.fixture(scope="session")
def ffmod():
    return ff
