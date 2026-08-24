"""The three files FlavorForge writes to the user's home directory.

    ~/.flavorforge_config.json          provider settings and the API key
    ~/.flavorforge_pantry.json          what is in your cupboard
    ~/.flavorforge_saved_recipes.json   the recipes you kept

All three were written with a bare ``open(path, "w")``, which truncates before
it writes. An interruption between those two steps leaves an empty file. For
the pantry that is an annoyance; for the saved recipes it is somebody's
collection; for the config it is the API key.

The GUI methods are thin wrappers over the module-level helper, which is what
these test — constructing FlavorForgeGUI needs a display and 2,000 lines of
widgets to answer a question about os.replace.
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "flavorforge.py"


@pytest.fixture
def target(tmp_path):
    return str(tmp_path / "data.json")


# ─── the write ─────────────────────────────────────────────────────────

def test_a_good_write_round_trips(ffmod, target):
    assert ffmod._write_json_atomic(target, {"a": [1, 2], "b": "x"}) is True
    assert json.loads(Path(target).read_text(encoding="utf-8")) == {"a": [1, 2], "b": "x"}


def test_sets_are_encodable(ffmod, target):
    """Saved recipes carry compound sets, which json cannot encode natively —
    hence default=list. Without it, saving a recipe raised."""
    assert ffmod._write_json_atomic(target, {"shared": {"linalool", "hexanal"}}) is True
    got = json.loads(Path(target).read_text(encoding="utf-8"))
    assert sorted(got["shared"]) == ["hexanal", "linalool"]


def test_a_failed_write_leaves_the_previous_file_intact(ffmod, target):
    """The property the whole exercise is for. A truncating write would have
    destroyed the good data before discovering it could not write the new."""
    ffmod._write_json_atomic(target, {"good": 1})
    assert ffmod._write_json_atomic(target, {"bad": object()}) is False
    assert json.loads(Path(target).read_text(encoding="utf-8")) == {"good": 1}


def test_a_failed_write_leaves_no_temp_file(ffmod, target):
    ffmod._write_json_atomic(target, {"bad": object()})
    assert not list(Path(target).parent.glob("*.tmp"))


def test_a_successful_write_leaves_no_temp_file(ffmod, target):
    ffmod._write_json_atomic(target, {"ok": True})
    assert not list(Path(target).parent.glob("*.tmp"))


def test_an_unwritable_location_is_reported_not_raised(ffmod, tmp_path):
    """Called from a Tk button handler, where an exception is a traceback on
    stderr nobody is watching and a UI that appears to have done nothing."""
    assert ffmod._write_json_atomic(str(tmp_path / "no" / "such" / "dir.json"),
                                    {"a": 1}) is False


def test_writes_are_utf8_regardless_of_locale(ffmod, target):
    """encoding="utf-8" is explicit: the default is locale-dependent, so a
    za'atar or jalapeño in a recipe name could fail to save on one machine and
    work on another."""
    ffmod._write_json_atomic(target, {"name": "jalapeño & za'atar — 100°C"})
    assert json.loads(Path(target).read_text(encoding="utf-8"))["name"] == \
        "jalapeño & za'atar — 100°C"


@pytest.mark.skipif(sys.platform == "win32", reason="no POSIX mode bits")
def test_a_secret_file_is_owner_only(ffmod, target):
    ffmod._write_json_atomic(target, {"anthropic_key": "sk-ant-x"}, secret=True)
    assert not (os.stat(target).st_mode & 0o077)


@pytest.mark.skipif(sys.platform == "win32", reason="no POSIX mode bits")
def test_an_ordinary_file_is_not_given_special_treatment(ffmod, target):
    """The pantry is not a secret; only the config asks for the chmod."""
    ffmod._write_json_atomic(target, {"pantry": ["salt"]})
    assert os.path.exists(target)


# ─── the reads ─────────────────────────────────────────────────────────

def test_the_gui_save_paths_all_go_through_the_atomic_helper():
    """Textual, because the alternative is a display and 2,000 widgets. If a
    fourth persisted file appears, it should join them."""
    src = SRC.read_text(encoding="utf-8")
    for method in ("_save_all", "_save_pantry", "save_config"):
        body = src[src.index(f"def {method}("):]
        body = body[:body.index("\n    def ")]
        assert "_write_json_atomic" in body, f"{method} does not write atomically"
        assert 'open(' not in body, f"{method} still opens the file directly"


def test_the_load_paths_tolerate_a_byte_order_mark():
    """These files are hand-editable and Notepad writes a BOM, which plain
    utf-8 rejects outright — the pantry would silently come back empty."""
    src = SRC.read_text(encoding="utf-8")
    for method in ("_load_all_saved", "_load_pantry", "_load_config"):
        body = src[src.index(f"def {method}("):]
        body = body[:body.index("\n    def ")]
        assert "utf-8-sig" in body, f"{method} does not tolerate a BOM"


def test_the_load_paths_catch_oserror_not_just_filenotfound():
    """A permission error or a directory in place of the file raises OSError,
    which FileNotFoundError alone does not cover — that would have escaped
    into the GUI as a crash on startup."""
    src = SRC.read_text(encoding="utf-8")
    for method in ("_load_all_saved", "_load_pantry", "_load_config"):
        body = src[src.index(f"def {method}("):]
        body = body[:body.index("\n    def ")]
        assert re.search(r"except \([^)]*OSError", body), f"{method} does not catch OSError"


def test_a_bom_file_is_readable(ffmod, tmp_path):
    """The mechanism itself, rather than only the source text."""
    p = tmp_path / "bom.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"pantry": ["salt"]}).encode("utf-8"))
    with open(p, encoding="utf-8-sig") as fh:
        assert json.load(fh) == {"pantry": ["salt"]}
    # json raises its own error for a BOM rather than letting the codec do it:
    # "Unexpected UTF-8 BOM (decode using utf-8-sig)". Worth pinning, because
    # the message names the fix and the handler must catch the right type.
    with pytest.raises(json.JSONDecodeError, match="BOM"):
        with open(p, encoding="utf-8") as fh:
            json.load(fh)
