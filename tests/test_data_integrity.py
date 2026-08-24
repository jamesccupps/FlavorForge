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
