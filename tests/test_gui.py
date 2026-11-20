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
def app(tmp_path, monkeypatch, build_gui):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    gui = build_gui()
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


def test_the_window_uses_only_glyphs_tk_draws_without_a_font_search(ffmod):
    """Tk on Windows searches for a fallback font the first time it draws a
    glyph the widget's font lacks. Measured per glyph in a fresh interpreter:
    270-430 ms for each emoji, 100-180 ms for the alembic, hourglass and
    check/cross dingbats, under 10 ms for everything allowed below. With
    fourteen such glyphs in labels and buttons the window took a median
    1.9 s to open; without them, 0.84 s."""
    import ast
    from pathlib import Path
    cheap = set("—•←→↔─█░★✓⟳") | set("éñ÷×°")
    src = Path(ffmod.__file__).read_text(encoding="utf-8")
    gui = next(n for n in ast.parse(src).body
               if isinstance(n, ast.ClassDef) and n.name == "FlavorForgeGUI")
    found = {ch for node in ast.walk(gui)
             if isinstance(node, ast.Constant) and isinstance(node.value, str)
             for ch in node.value if ord(ch) > 127}
    assert found <= cheap, f"slow glyphs in the window: {sorted(found - cheap)}"


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


def test_work_from_a_worker_thread_runs_on_the_tk_thread(app, monkeypatch):
    """The AI Chef's threads called root.after themselves, which Tkinter does
    not promise to support. They now queue work the window drains -- and a
    failing call is reported without stopping the ones behind it."""
    import threading
    ran_on, reported = [], []
    monkeypatch.setattr(app.root, "report_callback_exception",
                        lambda *exc: reported.append(exc[0]))

    def worker():
        app._call_on_ui(lambda: 1 / 0)
        app._call_on_ui(lambda: ran_on.append(threading.current_thread()))

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert ran_on == [], "nothing may run on the worker thread"
    app._run_pending_ui_calls()
    assert ran_on == [threading.main_thread()]
    assert reported == [ZeroDivisionError]


def test_the_test_button_neither_blocks_nor_saves(app, monkeypatch, tmp_path):
    """It saved the settings -- including a key only typed, not saved -- and
    then ran the network check on the window's thread."""
    import threading
    release = threading.Event()
    seen = []

    def slow_test():
        seen.append((app.ai_chef.provider, app.ai_chef.anthropic_key))
        release.wait(5)
        return True, "Key accepted."

    monkeypatch.setattr(app.ai_chef, "test_connection", slow_test)
    app.ai_provider_var.set("anthropic")
    app._on_provider_change()
    app.ai_key_var.set("sk-ant-typed-not-saved")
    app._test_ai_connection()                    # returns while the check waits
    assert app.ai_status.cget("text") == "Testing..."
    assert not (tmp_path / ".flavorforge_config.json").exists(), "Test wrote the key"
    release.set()
    for t in threading.enumerate():
        if t is not threading.main_thread() and t.daemon:
            t.join(2)
    app._run_pending_ui_calls()
    assert app.ai_status.cget("text") == "Key accepted."
    assert seen == [("anthropic", "sk-ant-typed-not-saved")], "it tested what was typed"


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
    app._run_pending_ui_calls()

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


def test_a_saved_almost_there_recipe_opens_again(app, monkeypatch):
    """Almost There recipes had no "novelty", and the recipe view read it
    directly: send one to the AI Chef, save it, and loading it later raised
    KeyError in the button handler with the recipe half drawn."""
    monkeypatch.setattr(app.ai_chef, "generate", lambda *a, **k: None)
    app.pantry = {"salt", "garlic", "onion", "tomato", "chicken", "rice", "lemon"}
    app._pantry_almost_there()
    app._pantry_send_to_ai()
    app._save_current_recipe()
    app._refresh_saved_list()
    app.saved_recipe_menu.current(0)
    app._load_saved_recipe()
    assert app.current_recipe["name"] in app.recipe_output.get("1.0", "end")
    assert "Novelty" in app.recipe_output.get("1.0", "end"), "the view finished drawing"


def test_a_hand_edited_saved_recipe_without_novelty_still_opens(app):
    app._display_recipe({"name": "Plain Toast", "ingredients": {"bread": "bread"},
                         "connections": []})
    assert "Plain Toast" in app.recipe_output.get("1.0", "end")


# ─── Debouncing ────────────────────────────────────────────────────────

def _settle(app, ms=300):
    import time
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.root.update()
        time.sleep(0.01)


def test_a_burst_of_resizes_and_slider_moves_redraws_the_graph_once(app, monkeypatch):
    """Each step used to redraw immediately: up to 15,391 canvas lines
    deleted and recreated per step at the slider's minimum."""
    calls = []
    monkeypatch.setattr(app, "draw_graph", lambda: calls.append(1))
    _settle(app)
    calls.clear()
    for _ in range(25):
        app._schedule_graph_redraw()
    assert calls == [], "nothing should draw mid-burst"
    _settle(app)
    assert calls == [1]


def test_typing_in_the_pantry_search_rebuilds_the_list_once(app, monkeypatch):
    """Each keystroke rebuilt all 326 checkboxes; typing a word built one
    list per letter."""
    calls = []
    monkeypatch.setattr(app, "_populate_pantry_checkboxes",
                        lambda *a, **k: calls.append(a))
    for i in range(1, 9):
        app.pantry_search_var.set("parmesan"[:i])
    assert calls == [], "nothing should rebuild mid-word"
    _settle(app)
    assert calls == [("parmesan", "All")]


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
    assert recipe["diet"] == ffmod.recipe_diet(app.build_current_template,
                                               recipe["ingredients"].values())
    assert "SUITS" in app.recipe_output.get("1.0", "end")
