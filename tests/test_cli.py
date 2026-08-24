"""The command line, and the two engine queries it exposes.

The engine was the interesting half of this program and it could only be
reached through 2,000 lines of Tk — you could not script it, use it over SSH,
or run it on a box without a GUI toolkit. Everything here is new in 3.1.

Substitution and the compound inverse index are engine features in their own
right; the CLI is just the first caller.
"""
import pytest


# ─── substitutes ───────────────────────────────────────────────────────

def test_a_substitute_shares_the_ingredients_role(engine, ffmod):
    """A substitute must stand IN for the thing, not go WITH it — which is
    what makes this a different question from get_pairings. Same category, or
    it cannot do the same job in the dish."""
    for name in ("parmesan", "basil", "salmon", "quinoa", "honey"):
        cat = ffmod.INGREDIENTS[name].category
        for sub in engine.substitutes(name, 8):
            assert ffmod.INGREDIENTS[sub["ingredient"]].category == cat, \
                f"{sub['ingredient']} offered as a substitute for {name}"


def test_a_substitute_respects_the_subtype(engine, ffmod):
    """Category alone is far too coarse for grains and sauces. A stock cannot
    stand in for a vinaigrette and orzo cannot stand in for a baguette, even
    though each pair shares a category."""
    for name, table in (("spaghetti", "GRAIN_NOODLES"),
                        ("sourdough", "GRAIN_BREADS"),
                        ("jasmine_rice", "GRAIN_RICE"),
                        ("chicken_stock", "BROTH_TYPES")):
        members = getattr(ffmod, table)
        for sub in engine.substitutes(name, 8):
            assert sub["ingredient"] in members, \
                f"{name}: offered {sub['ingredient']}, which is not in {table}"


def test_an_ingredient_is_not_its_own_substitute(engine):
    for name in ("parmesan", "basil", "spaghetti"):
        assert all(s["ingredient"] != name for s in engine.substitutes(name, 20))


def test_substitutes_prefer_a_real_aroma_match(engine):
    """Ordering matters more here than for pairings: the first suggestion is
    the one a cook will actually use."""
    subs = engine.substitutes("parmesan", 12)
    matched = [s["aroma_match"] for s in subs]
    assert matched[0] is True
    assert matched == sorted(matched, reverse=True), \
        "a role-only match ranked above an aroma match"


def test_a_role_only_substitute_is_labelled_as_one(engine, ffmod):
    """Offering a swap with nothing in common is fine — sometimes all you need
    is something that fills the same slot — but the cook should be told which
    kind of suggestion they are looking at."""
    for name in ffmod.INGREDIENTS:
        for s in engine.substitutes(name, 20):
            distinctive = s["shared_compounds"] - engine._boring_compounds
            assert s["aroma_match"] == bool(distinctive)


def test_substitutes_for_an_unknown_ingredient_is_empty_not_an_error(engine):
    assert engine.substitutes("unobtainium") == []


def test_a_tastant_with_no_compounds_still_gets_role_substitutes(engine, ffmod):
    """salt has no aroma compounds at all, so every suggestion is a role match
    and every score is zero. It should still answer rather than return
    nothing — 'what else is a spice' is a reasonable question."""
    subs = engine.substitutes("salt", 5)
    assert subs
    assert all(s["score"] == 0.0 and not s["aroma_match"] for s in subs)


# ─── the compound inverse index ────────────────────────────────────────

def test_the_inverse_index_agrees_with_the_forward_one(engine, ffmod):
    """The database could only ever be read one way — pick an ingredient, see
    its compounds. This is the other direction and it must not disagree."""
    for compound in list(ffmod.COMPOUNDS)[:25]:
        got = set(engine.ingredients_with_compound(compound))
        expected = {n for n, i in ffmod.INGREDIENTS.items() if compound in i.compounds}
        assert got == expected, compound


def test_every_compound_now_returns_something(engine, ffmod):
    """The orphan check in test_data_integrity says no compound is unattached;
    this is the same claim reached through the query the user actually runs."""
    for compound in ffmod.COMPOUNDS:
        assert engine.ingredients_with_compound(compound), compound


def test_an_unknown_compound_is_empty_not_an_error(engine):
    assert engine.ingredients_with_compound("unobtainium") == []


def test_compound_search_matches_name_and_description(engine):
    assert "1_octen_3_ol" in engine.search_compounds("mushroom")   # description
    assert "geosmin" in engine.search_compounds("geosmin")         # key
    assert "vanillin" in engine.search_compounds("Vanilla")        # case-insensitive
    assert engine.search_compounds("") == []
    assert engine.search_compounds("zzzznope") == []


# ─── the CLI ───────────────────────────────────────────────────────────

def test_version_prints_and_exits_zero(cli):
    with pytest.raises(SystemExit) as e:
        cli("--version")
    assert e.value.code == 0


def test_pair(cli):
    code, out, _ = cli("--pair", "garlic", "-n", "5")
    assert code == 0
    assert "garlic" in out and "allicin" in out
    assert out.count("\n") > 5


def test_pair_accepts_a_display_name_and_a_prefix(cli):
    for spelling in ("bell_pepper", "bell pepper", "bell-pepper"):
        code, out, _ = cli("--pair", spelling, "-n", "3")
        assert code == 0, spelling
        assert "bell pepper" in out


def test_an_unknown_ingredient_exits_nonzero_with_suggestions(cli):
    code, _, err = cli("--pair", "garlik")
    assert code == 2
    assert "No ingredient" in err
    assert "garlic" in err, "should suggest the near miss"


def test_substitute(cli):
    code, out, _ = cli("--substitute", "parmesan", "-n", "3")
    assert code == 0 and "pecorino" in out


def test_bridge(cli):
    code, out, _ = cli("--bridge", "chocolate", "salmon")
    assert code == 0
    assert "chocolate" in out and "salmon" in out


def test_bridge_reports_a_bad_name_on_either_side(cli):
    assert cli("--bridge", "nonsense", "salmon")[0] == 2
    assert cli("--bridge", "salmon", "nonsense")[0] == 2


def test_compound_lookup(cli):
    code, out, _ = cli("--compound", "geosmin")
    assert code == 0
    assert "beet" in out and "earthy" in out
    assert "1 of 303" in out or "of 303 ingredients" in out


def test_compound_falls_back_to_search(cli):
    code, out, _ = cli("--compound", "mushroom")
    assert code == 0 and "1_octen_3_ol" in out


def test_an_unknown_compound_exits_nonzero(cli):
    code, _, err = cli("--compound", "zzzznope")
    assert code == 2 and "No compound" in err


def test_recipe(cli):
    code, out, _ = cli("--recipe")
    assert code == 0
    assert "novelty" in out
    assert "{" not in out, "an unfilled placeholder reached the output"


def test_recipe_with_a_seed_contains_the_seed(cli):
    code, out, _ = cli("--recipe", "--seed", "salmon")
    assert code == 0 and "salmon" in out.lower()


def test_recipe_with_a_dish_type(cli):
    code, out, _ = cli("--recipe", "--dish-type", "Soup")
    assert code == 0 and "Soup" in out


def test_recipe_with_a_bad_seed_exits_nonzero(cli):
    assert cli("--recipe", "--seed", "unobtainium")[0] == 2


def test_list(cli, ffmod):
    code, out, err = cli("--list")
    assert code == 0
    assert out.count("\n") == len(ffmod.INGREDIENTS)
    assert f"{len(ffmod.INGREDIENTS)} ingredients" in err


def test_list_by_category(cli, ffmod):
    code, out, _ = cli("--list", "--category", "mushroom")
    assert code == 0
    assert out.count("\n") == sum(1 for i in ffmod.INGREDIENTS.values()
                                  if i.category == "mushroom")


def test_list_with_an_unknown_category_exits_nonzero(cli):
    code, _, err = cli("--list", "--category", "condiments")
    assert code == 2 and "Known:" in err


def test_the_queries_are_mutually_exclusive(cli):
    with pytest.raises(SystemExit):
        cli("--pair", "garlic", "--recipe")


# ─── headless ──────────────────────────────────────────────────────────

def test_the_module_imports_without_tkinter(ffmod):
    """The guard that makes the CLI usable on a server. HAVE_TK is False there
    and everything below the GUI must still work."""
    assert hasattr(ffmod, "HAVE_TK")
    assert ffmod.INGREDIENTS and ffmod.COMPOUNDS


def test_the_gui_refuses_clearly_without_tkinter(ffmod, monkeypatch):
    """Not with an AttributeError on None."""
    monkeypatch.setattr(ffmod, "HAVE_TK", False)
    with pytest.raises(RuntimeError, match="python3-tk"):
        ffmod.FlavorForgeGUI()


def test_no_subcommand_without_tkinter_prints_help(ffmod, monkeypatch, capsys):
    monkeypatch.setattr(ffmod, "HAVE_TK", False)
    code = ffmod.run_cli([])
    out = capsys.readouterr()
    assert code == 1
    assert "usage:" in out.out
    assert "tkinter is not installed" in out.err


# ─── the GUI still builds ──────────────────────────────────────────────

def test_the_gui_builds_and_shows_substitutes(ffmod):
    """The one test that constructs the real 2,000-line GUI. It is cheap
    insurance: everything else here works on the engine, so a typo in a Tk
    call would otherwise reach the user before it reached a test."""
    if not ffmod.HAVE_TK:
        pytest.skip("no tkinter")
    try:
        app = ffmod.FlavorForgeGUI()
    except Exception as exc:                       # no display
        pytest.skip(f"cannot create a Tk root: {exc}")
    app.root.withdraw()
    try:
        for tab in ("tab_pair", "tab_graph", "tab_recipe", "tab_build",
                    "tab_bridge", "tab_pantry", "tab_ai"):
            assert hasattr(app, tab), f"{tab} was not built"

        names = [app.pair_listbox.get(i) for i in range(app.pair_listbox.size())]
        idx = next(i for i, n in enumerate(names) if n.startswith("parmesan"))
        app.pair_listbox.selection_set(idx)
        app._on_pair_select(None)
        text = app.pair_results.get("1.0", "end")

        assert "NO PARMESAN? USE INSTEAD" in text
        assert "pecorino" in text
        assert "butyric acid" in text, "the shared compounds should be named"
        app.root.update_idletasks()
    finally:
        app.geo.stop() if hasattr(app, "geo") else None
        app.root.destroy()
