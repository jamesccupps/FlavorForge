"""Behaviour of the Tk GUI, driven without a mainloop.

Everything else in the suite tests the engine. These construct the real
window (withdrawn) and call the handlers a click would call, because the bugs
they pin lived in the wiring between widgets and state, where no engine test
can see them. Skipped where there is no Tk or no display.

Home is pointed at a temporary directory so nothing here reads or writes the
real ~/.flavorforge_* files.
"""
import pytest


@pytest.fixture
def app(ffmod, tmp_path, monkeypatch):
    if not ffmod.HAVE_TK:
        pytest.skip("no tkinter")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    try:
        gui = ffmod.FlavorForgeGUI()
    except Exception as exc:                       # no display
        pytest.skip(f"cannot create a Tk root: {exc}")
    gui.root.withdraw()
    yield gui
    gui.root.destroy()


# ─── AI Chef settings ──────────────────────────────────────────────────

def test_the_migration_note_goes_away_once_another_model_is_picked(app, ffmod):
    """It used to stay beside the dropdown whatever was selected, describing
    a choice the user had already overridden."""
    app.ai_chef.retired_model = "claude-opus-5"
    app.ai_chef.anthropic_model = "claude-opus-5-5"
    app.ai_provider_var.set("anthropic")
    app._on_provider_change()
    assert "claude-opus-5 is no longer offered" in app.ai_model_hint.cget("text")

    app.ai_model_var.set("claude-haiku-5-5")
    app._update_model_hint()
    assert "no longer offered" not in app.ai_model_hint.cget("text")


# ─── Build a Dish ──────────────────────────────────────────────────────

def test_build_tab_starts_with_the_template_it_displays(app):
    """The tab opens showing the first template's slots. Its state was reset
    to None after that template was loaded, so the first ingredient picked
    showed the welcome screen instead of a preview, and Build Recipe asked
    for a template while one was on screen."""
    shown = app.build_template_var.get()
    assert app.build_current_template is not None
    assert app.build_current_template["name"] == shown


def test_the_first_pick_on_the_build_tab_shows_a_preview(app):
    slot = next(iter(app.build_slot_vars))
    var, candidates = app.build_slot_vars[slot]
    var.set(candidates[0][0])
    app._on_build_slot_change(slot)
    text = app.build_output.get("1.0", "end")
    assert "YOUR PICKS" in text
    assert "Build a Dish" not in text, "fell back to the welcome screen"


def test_build_recipe_works_without_reselecting_the_template(app):
    slot = next(iter(app.build_slot_vars))
    var, candidates = app.build_slot_vars[slot]
    var.set(candidates[0][0])
    app._build_dish_generate()
    recipe = app.current_recipe
    assert recipe and "error" not in recipe
    assert "{" not in recipe["name"], recipe["name"]
    assert len(recipe["ingredients"]) == len(app.build_current_template["structure"])
