"""Cross-reference checks over the ingredient / compound / template databases.

This is the test file that matters most in a data-heavy project. Every bug
these catch is invisible by inspection: a compound key that does not exist
scores as "no match" rather than raising, an override table keyed on an
ingredient that was later renamed simply stops applying, and a template slot
with no candidates drops silently out of the generated dish.

None of it is exotic — it is all "does this name on the left exist on the
right" — but nothing was checking it, and the audit that prompted these tests
found five real problems in this file's scope alone.
"""
import collections
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "flavorforge.py"

# The grain/sauce subset tables, which drive the specialised template slots.
SUBSET_TABLES = ("GRAIN_NOODLES", "GRAIN_BREADS", "GRAIN_RICE", "GRAIN_OTHER",
                 "BROTH_TYPES", "COOKING_SAUCES", "DRESSINGS", "EDIBLE_GRAINS")

# Slots handled by explicit branches in get_slot_candidates rather than by
# SLOT_CAT_MAP.
SUBTYPE_SLOTS = {"noodle", "bread", "rice_type", "grain",
                 "broth", "cooking_sauce", "dressing"}


# ─── compounds ─────────────────────────────────────────────────────────

def test_every_referenced_compound_exists(ffmod):
    """A typo'd compound key does not raise — it silently never matches, so
    the ingredient quietly loses part of its flavour profile."""
    unknown = collections.defaultdict(list)
    for name, ing in ffmod.INGREDIENTS.items():
        for c in ing.compounds:
            if c not in ffmod.COMPOUNDS:
                unknown[c].append(name)
    assert not unknown, f"unknown compound keys: {dict(unknown)}"


def test_every_compound_has_a_known_category(ffmod):
    """The category drives the node colour in the graph; an unknown one falls
    through to no colour at all."""
    for key, comp in ffmod.COMPOUNDS.items():
        assert comp.category in ffmod.COMPOUND_CATEGORIES, f"{key}: {comp.category!r}"


def test_compound_keys_and_display_names_are_consistent(ffmod):
    """The key may be a safe identifier (`4vg`) while the name is the real
    chemical name (`4-vinylguaiacol`) — that is fine. What is not fine is a
    name that is empty or a duplicate of another compound's."""
    names = [c.name for c in ffmod.COMPOUNDS.values()]
    assert all(names), "a compound has an empty display name"
    dupes = [n for n, k in collections.Counter(names).items() if k > 1]
    assert not dupes, f"two compounds share a display name: {dupes}"


# ─── ingredients ───────────────────────────────────────────────────────

def test_every_ingredient_has_a_known_category(ffmod):
    for name, ing in ffmod.INGREDIENTS.items():
        assert ing.category in ffmod.CATEGORIES, f"{name}: {ing.category!r}"


def test_every_ingredient_has_cooking_methods(ffmod):
    """The AI prompt prints "Best cooking methods:" per ingredient; an empty
    list renders as a dangling label."""
    for name, ing in ffmod.INGREDIENTS.items():
        assert ing.cooking_methods, f"{name} has no cooking methods"


def test_every_ingredient_has_flavor_notes(ffmod):
    for name, ing in ffmod.INGREDIENTS.items():
        assert ing.flavor_notes.strip(), f"{name} has no flavor notes"


def test_ingredients_without_compounds_are_only_the_pure_tastants(ffmod):
    """Salt, MSG, sugar and cornstarch genuinely have no aroma compounds —
    they are taste and texture, not smell. That is correct, but it means they
    can never pair or bridge, so the set is pinned rather than left to drift."""
    empty = {n for n, i in ffmod.INGREDIENTS.items() if not i.compounds}
    assert empty == {"salt", "msg", "white_sugar", "cornstarch"}, sorted(empty)


def test_a_zero_compound_ingredient_cannot_crash_the_bridge_finder(engine):
    """find_bridge divides by len(bridge.compounds). The `if shared_with_a and
    shared_with_b` guard means an empty set is skipped before the division —
    verified here rather than assumed, because the division is right there."""
    assert engine.find_bridge("salt", "chicken") == []
    for pair in (("chicken", "beef"), ("tomato", "basil")):
        for b in engine.find_bridge(*pair):
            assert b["ingredient"] not in {"salt", "msg", "white_sugar", "cornstarch"}


# ─── duplicate keys, which Python resolves silently ────────────────────

def _dict_block(text, marker):
    i = text.index(marker)
    depth, j = 0, i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return text[i:j]


def test_no_duplicate_keys_in_the_big_literals():
    """`{"a": 1, "a": 2}` is legal Python and keeps the second silently. In a
    1,800-line dict literal maintained by hand that is a real hazard: the first
    definition simply stops existing, with no error anywhere."""
    src = SRC.read_text(encoding="utf-8")
    for marker in ("INGREDIENTS = {", "COMPOUNDS = {", "TASTE_OVERRIDES = {",
                   "TEXTURE_OVERRIDES = {", "CATEGORY_TEXTURES = {",
                   "CATEGORY_TASTES = {"):
        block = _dict_block(src, marker)
        keys = re.findall(r'^\s{4}"([^"]+)":', block, re.M)
        dupes = [k for k, n in collections.Counter(keys).items() if n > 1]
        assert not dupes, f"{marker.split(' =')[0]} defines {dupes} more than once"


# ─── override and subset tables ────────────────────────────────────────

def test_every_category_has_texture_and_taste_defaults(ffmod):
    """A category missing from these tables silently degrades every ingredient
    in it to ["neutral"] / {} — no error, just worse output."""
    for cat in ffmod.CATEGORIES:
        assert cat in ffmod.CATEGORY_TEXTURES, f"CATEGORY_TEXTURES missing {cat!r}"
        assert cat in ffmod.CATEGORY_TASTES, f"CATEGORY_TASTES missing {cat!r}"


def test_subset_tables_reference_real_ingredients(ffmod):
    ghosts = {}
    for set_name in SUBSET_TABLES:
        missing = [m for m in getattr(ffmod, set_name) if m not in ffmod.INGREDIENTS]
        if missing:
            ghosts[set_name] = missing
    assert not ghosts, f"grain/sauce subsets naming non-existent ingredients: {ghosts}"


def test_taste_override_values_are_in_range(ffmod):
    """Taste levels are averaged and compared against thresholds like 0.4; a
    value outside 0..1 would skew analyze_balance for the whole dish."""
    for name, profile in ffmod.TASTE_OVERRIDES.items():
        for dim, val in profile.items():
            assert 0.0 <= val <= 1.0, f"{name}[{dim}] = {val}"


# ─── templates ─────────────────────────────────────────────────────────

PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
ALIASES = {"veg": "vegetable", "cheese": "dairy"}


def test_every_template_has_the_keys_the_engine_reads(ffmod):
    for i, t in enumerate(ffmod.DISH_TEMPLATES):
        for key in ("name", "technique", "structure", "needs", "dish_type"):
            assert key in t, f"template[{i}] {t.get('name', '?')!r} has no {key!r}"


def test_every_dish_type_is_declared(ffmod):
    for t in ffmod.DISH_TEMPLATES:
        assert t["dish_type"] in ffmod.DISH_TYPES, \
            f"{t['name']!r}: dish_type {t['dish_type']!r} not in DISH_TYPES"


def test_every_declared_dish_type_has_templates(ffmod):
    """A dish type in the dropdown with no templates behind it silently falls
    back to the full template list, so the filter appears to do nothing."""
    have = {t["dish_type"] for t in ffmod.DISH_TEMPLATES}
    missing = [d for d in ffmod.DISH_TYPES if d != "Any" and d not in have]
    assert not missing, f"dish types with no templates: {missing}"


def test_every_placeholder_can_be_filled(ffmod):
    """`{protein}` in a name with no `protein` in structure renders the literal
    braces to the user."""
    bad = []
    for t in ffmod.DISH_TEMPLATES:
        structure = set(t["structure"])
        for field in ("name", "technique"):
            for ph in PLACEHOLDER.findall(t[field]):
                if ph in structure or (ph in ALIASES and ALIASES[ph] in structure):
                    continue
                bad.append(f"{t['name']!r} {field} uses {{{ph}}}, structure={sorted(structure)}")
    assert not bad, bad


def test_every_needs_slot_is_also_in_structure(ffmod):
    """generate_recipe places the seed by scanning `needs`, then fills from
    `structure`. A slot in needs but not structure can take the seed and then
    never be rendered."""
    bad = [f"{t['name']!r}: needs {s!r} not in structure"
           for t in ffmod.DISH_TEMPLATES for s in t["needs"] if s not in t["structure"]]
    assert not bad, bad


def test_every_template_slot_has_candidates(ffmod):
    """An empty candidate list makes generate_recipe skip the slot, leaving the
    placeholder unreplaced and the dish short an ingredient."""
    bad = [f"{t['name']!r} slot {s!r}"
           for t in ffmod.DISH_TEMPLATES for s in t["structure"]
           if not ffmod.get_slot_candidates(s)]
    assert not bad, f"template slots with no candidate ingredients: {bad}"


def test_every_template_slot_is_mapped(ffmod):
    """SLOT_CAT_MAP.get(slot, list(CATEGORIES)) means an unmapped slot matches
    EVERY category — a 'herb' slot would happily return beef."""
    used = {s for t in ffmod.DISH_TEMPLATES for s in t["structure"]}
    unmapped = sorted(s for s in used
                      if s not in ffmod.SLOT_CAT_MAP and s not in SUBTYPE_SLOTS)
    assert not unmapped, f"slots absent from SLOT_CAT_MAP: {unmapped}"


def test_the_readme_counts_match_the_data(ffmod):
    readme = (SRC.parent / "README.md").read_text(encoding="utf-8")
    assert f"{len(ffmod.INGREDIENTS)} ingredients" in readme
    assert f"{len(ffmod.COMPOUNDS)} aroma compounds" in readme
    assert f"{len(ffmod.DISH_TEMPLATES)} recipe templates" in readme


# ─── the module's own claims about itself ──────────────────────────────

def test_the_module_docstring_counts_are_accurate(ffmod):
    """The docstring is the first thing anyone reads and it was three versions
    stale: 190 ingredients when there were 297, 77 templates when there were
    102, 17 dish types when there were 16 (it was counting the "Any" filter
    entry as a dish type). The README had been kept current; the code had not,
    and nothing could tell you that."""
    doc = ffmod.__doc__
    actual = {
        "ingredients": len(ffmod.INGREDIENTS),
        "compounds": len(ffmod.COMPOUNDS),
        "templates": len(ffmod.DISH_TEMPLATES),
    }
    for word, n in actual.items():
        m = re.search(rf"(\d+)\s+{word}", doc)
        assert m, f"docstring no longer states a {word} count"
        assert int(m.group(1)) == n, f"docstring says {m.group(1)} {word}, actual {n}"


def test_the_docstring_dish_type_count_excludes_the_any_filter(ffmod):
    """"Any" is a UI filter meaning "do not filter", not a kind of dish."""
    m = re.search(r"(\d+)\s+dish types", ffmod.__doc__)
    assert m, "docstring no longer states a dish-type count"
    assert int(m.group(1)) == len(ffmod.DISH_TYPES) - 1


def test_the_readme_counts_match_the_data(ffmod):
    readme = (SRC.parent / "README.md").read_text(encoding="utf-8")
    assert f"{len(ffmod.INGREDIENTS)} ingredients" in readme
    assert f"{len(ffmod.COMPOUNDS)} aroma compounds" in readme
    assert f"{len(ffmod.DISH_TEMPLATES)} recipe templates" in readme


# ─── reachability ──────────────────────────────────────────────────────

def _reachable(ffmod):
    used = {s for t in ffmod.DISH_TEMPLATES for s in t["structure"]}
    out = set()
    for slot in used:
        out.update(ffmod.get_slot_candidates(slot))
    return out


def test_every_declared_slot_is_actually_used(ffmod):
    """The direction that bit: `oil` was declared in SLOT_CAT_MAP and used by
    none of the 102 templates, so no generated recipe could ever contain a
    cooking fat — while _add_staples listed olive oil as a pantry staple and
    analyze_balance cheerfully advised "Needs richness — add butter, oil"."""
    used = {s for t in ffmod.DISH_TEMPLATES for s in t["structure"]}
    unused = sorted(set(ffmod.SLOT_CAT_MAP) - used - SUBTYPE_SLOTS)
    assert not unused, (
        f"slots declared in SLOT_CAT_MAP but used by no template: {unused} — "
        f"every ingredient reachable only through them is unreachable")


def test_every_ingredient_category_is_reachable(ffmod):
    """A whole category no slot can select is a category of ingredients the
    generator can never use. oil/fat was 0 of 3."""
    by_cat = collections.Counter(ffmod.INGREDIENTS[n].category for n in _reachable(ffmod))
    dead = sorted(c for c in ffmod.CATEGORIES if by_cat[c] == 0)
    assert not dead, f"categories no template slot can reach: {dead}"


def test_only_the_deliberate_exclusions_are_unreachable(ffmod):
    """flour and cornstarch are held out of the generic grain slot on purpose —
    get_slot_candidates says so in a comment. Pinned so the exclusion stays
    deliberate rather than quietly becoming an accident again."""
    unreachable = set(ffmod.INGREDIENTS) - _reachable(ffmod)
    assert unreachable == {"flour", "cornstarch"}, sorted(unreachable)


def test_the_fat_slot_reaches_every_oil(ffmod):
    assert set(ffmod.get_slot_candidates("oil")) == {
        n for n, i in ffmod.INGREDIENTS.items() if i.category == "oil/fat"}


# Ceviche is raw fish cured in citrus. It has no cooking fat and should not
# grow one — the exception is named rather than papered over.
NO_FAT_BY_DESIGN = {"Ceviche"}


def test_stir_fry_and_salad_templates_call_for_a_fat(ffmod):
    """Every template in these families except the deliberate exceptions."""
    for t in ffmod.DISH_TEMPLATES:
        if t["dish_type"] not in ("Stir-Fry & Wok", "Salad & Slaw"):
            continue
        if any(x in t["name"] for x in NO_FAT_BY_DESIGN):
            continue
        assert "oil" in t["structure"], f"{t['name']!r} has no fat slot"


def test_generated_stir_fries_name_a_fat(engine, ffmod):
    """The point of the fix, end to end rather than by inspection."""
    for _ in range(20):
        r = engine.generate_recipe(dish_type="Stir-Fry & Wok")
        assert "oil" in r["ingredients"], f"{r['name']} has no fat"
        assert ffmod.INGREDIENTS[r["ingredients"]["oil"]].category == "oil/fat"


def test_every_used_slot_has_a_display_role(ffmod):
    """A slot with no role_labels entry renders its raw key to the user —
    "Role: rice_type" rather than "Role: the rice"."""
    src = SRC.read_text(encoding="utf-8")
    block = src[src.index("role_labels = {"):]
    block = block[:block.index("}")]
    labelled = set(re.findall(r'"([a-z_]+)":', block))
    used = {s for t in ffmod.DISH_TEMPLATES for s in t["structure"]}
    assert not (used - labelled), f"slots with no display label: {sorted(used - labelled)}"


# ─── the science, not just the plumbing ────────────────────────────────

def test_no_compound_is_defined_but_unused(ffmod):
    """A compound with a description and no ingredient is dead weight in a
    database whose entire value is the mapping. Seven were orphaned, and at
    least one had clearly been written FOR a specific ingredient and never
    wired to it — chavicol's own description reads "basil, spicy, warm" while
    basil did not have it."""
    used = {c for ing in ffmod.INGREDIENTS.values() for c in ing.compounds}
    orphans = sorted(set(ffmod.COMPOUNDS) - used)
    assert not orphans, f"compounds defined but attached to nothing: {orphans}"


def test_override_tables_reference_real_ingredients(ffmod):
    """An override keyed on an ingredient that does not exist never applies —
    the lookup falls through to the category default and the data looks
    present. Both ghosts here (squid, arugula) turned out to be evidence that
    the ingredient was meant to exist, so they were added rather than the
    overrides deleted."""
    ghosts = {}
    for tbl_name in ("TEXTURE_OVERRIDES", "TASTE_OVERRIDES"):
        missing = [k for k in getattr(ffmod, tbl_name) if k not in ffmod.INGREDIENTS]
        if missing:
            ghosts[tbl_name] = missing
    assert not ghosts, f"overrides for non-existent ingredients: {ghosts}"


def test_the_overrides_that_were_dead_now_apply(ffmod):
    assert ffmod.get_textures("squid") == ["chewy", "tender"]
    assert ffmod.get_taste_profile("arugula") == {"bitter": 0.5, "spicy": 0.3}


def test_2_acetyl_1_pyrroline_is_not_filed_as_a_pyrazine(ffmod):
    """A pyrroline is a five-membered ring with one nitrogen; a pyrazine is
    six-membered with two. In a database whose selling point is the chemistry,
    filing one as the other is a straightforward error — and the category is
    what colours the node in the graph."""
    assert ffmod.COMPOUNDS["acetyl_pyrroline"].category == "pyrroline"


def test_the_compounds_written_for_an_ingredient_reach_it(ffmod):
    """Each of these was defined with a description naming its source and then
    left unattached. The description is the assertion."""
    expected = {
        "basil": "chavicol",
        "cherry": "acetophenone",
        "jasmine_rice": "indole",
        "black_tea": "linalool_oxide",
        "red_wine": "whiskey_lactone",
    }
    for ing, compound in expected.items():
        assert ing in ffmod.INGREDIENTS, f"{ing} is not an ingredient"
        assert compound in ffmod.INGREDIENTS[ing].compounds, \
            f"{ing} should carry {compound}"
