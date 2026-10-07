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


def test_the_window_title_carries_the_real_version(app, ffmod):
    """It said v3.0 through 3.1 and 3.2: a version typed into a string."""
    assert app.root.title().endswith("v" + ffmod.__version__)


def test_fixed_sizes_follow_the_display_dpi(app):
    """At 200% the window opened at 1400x900 physical pixels with fonts twice
    their 96-DPI size: tabs truncated and toolbars running off the edge."""
    expected = max(1.0, app.root.winfo_fpixels("1i") / 96.0)
    assert app._scale == pytest.approx(expected)
    assert app._px(100) == round(100 * expected)


def test_the_window_never_opens_larger_than_the_screen(app):
    app.root.update_idletasks()
    geo = app.root.geometry()                       # "WxH+X+Y"
    w, h = (int(v) for v in geo.split("+")[0].split("x"))
    assert w <= app.root.winfo_screenwidth()
    assert h <= app.root.winfo_screenheight()


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


def test_a_newer_ai_generation_owns_the_pane(app, monkeypatch):
    """Two generations in flight used to append into the same pane and the
    same saved text, so "Save AI Recipe" could write two recipes spliced
    together. The older stream is now ignored and told to stop."""
    calls = []
    monkeypatch.setattr(app.ai_chef, "generate",
                        lambda prompt, callback=None, error_callback=None,
                        should_stop=None: calls.append((callback, error_callback,
                                                        should_stop)))
    recipe = app.engine.generate_recipe(seed_ingredient="salmon")
    app._ai_generate_from_recipe(recipe)
    app._ai_generate_from_recipe(recipe)
    (old_cb, old_err, old_stop), (new_cb, _, new_stop) = calls

    old_cb("STALE ")
    new_cb("FRESH")
    old_err("stale failure")
    old_cb(None)
    app.root.update()

    assert app.ai_response_text == "FRESH"
    assert "STALE" not in app.ai_output.get("1.0", "end")
    assert "stale failure" not in app.ai_output.get("1.0", "end")
    assert "Done" not in app.ai_spinner.cget("text"), "the old stream finished, not this one"
    assert old_stop() and not new_stop()


# ─── Saved recipes ─────────────────────────────────────────────────────

def test_a_failed_save_is_not_reported_as_saved(app, monkeypatch):
    """The status said "Saved!" before the write was attempted, and the
    write's result was never looked at."""
    app.current_recipe = app.engine.generate_recipe(seed_ingredient="salmon")
    monkeypatch.setattr(app, "_save_all", lambda recipes: False)
    app._save_current_recipe()
    assert "failed" in app.save_status.cget("text").lower()


def test_a_successful_save_still_says_so(app):
    app.current_recipe = app.engine.generate_recipe(seed_ingredient="salmon")
    app._save_current_recipe()
    assert app.save_status.cget("text") == "Saved!"


# ─── Pantry ────────────────────────────────────────────────────────────

def test_the_mouse_wheel_is_not_captured_app_wide(app):
    """The pantry list bound the wheel with bind_all for the life of the app,
    so scrolling the recipe results beside it scrolled the list too. It is
    bound only while the pointer is over the list now."""
    for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        assert app.root.bind_all(ev) == "", f"{ev} is bound app-wide at startup"


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


def test_a_built_dish_gets_the_same_diet_check_as_a_generated_one(app, ffmod):
    slot = next(iter(app.build_slot_vars))
    var, candidates = app.build_slot_vars[slot]
    var.set(candidates[0][0])
    app._build_dish_generate()
    recipe = app.current_recipe
    assert recipe["diet"] == ffmod.dietary_profile(recipe["ingredients"].values())
    assert "SUITS" in app.recipe_output.get("1.0", "end")
