"""Recipe generation: seeds, dish types, and the shape of what comes back.

The generator is the feature people actually use, and it was the least
constrained part of the codebase — nothing checked that asking for a salmon
recipe produced a recipe with salmon in it as the protein.
"""
import random

import pytest

SEEDS = ["salmon", "chicken", "tomato", "basil", "honey", "quinoa",
         "spaghetti", "olive_oil", "parmesan", "lemon", "shiitake", "chickpea"]


# ─── shape ─────────────────────────────────────────────────────────────

def test_a_recipe_has_every_field_the_ui_reads(engine):
    r = engine.generate_recipe()
    for key in ("name", "technique", "ingredients", "novelty", "connections", "dish_type"):
        assert key in r, f"missing {key}"
    assert r["ingredients"], "a recipe with no ingredients"
    assert 0.0 <= r["novelty"] <= 1.0


def test_no_placeholder_survives_into_the_output(engine, ffmod):
    """An unfilled slot leaves literal braces in the dish name — "Braised
    {protein} with {veg}" rendered to the user verbatim."""
    for _ in range(120):
        r = engine.generate_recipe()
        assert "{" not in r["name"], r["name"]
        assert "}" not in r["name"], r["name"]
        assert "{" not in r["technique"], r["technique"]


def test_no_placeholder_survives_for_any_dish_type(engine, ffmod):
    for dish in ffmod.DISH_TYPES:
        for _ in range(12):
            r = engine.generate_recipe(dish_type=dish)
            assert "{" not in r["name"] and "{" not in r["technique"], (dish, r["name"])


def test_every_chosen_ingredient_is_real(engine, ffmod):
    for _ in range(80):
        r = engine.generate_recipe()
        for slot, name in r["ingredients"].items():
            assert name in ffmod.INGREDIENTS, f"{slot} -> {name!r}"


def test_a_recipe_never_repeats_an_ingredient(engine):
    """Two slots holding the same thing reads as a mistake, and it is one."""
    for _ in range(80):
        r = engine.generate_recipe()
        names = list(r["ingredients"].values())
        assert len(names) == len(set(names)), names


def test_connections_reference_ingredients_that_are_in_the_recipe(engine):
    for _ in range(40):
        r = engine.generate_recipe()
        present = set(r["ingredients"].values())
        for conn in r["connections"]:
            a, b = conn["pair"]
            assert a in present and b in present
            assert conn["shared"], "a connection with no shared compounds"


# ─── seeds ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_a_seeded_recipe_contains_the_seed(engine, seed):
    for _ in range(10):
        r = engine.generate_recipe(seed_ingredient=seed)
        assert seed in r["ingredients"].values(), f"{seed} missing from {r['name']}"


@pytest.mark.parametrize("seed", SEEDS)
def test_the_seed_lands_in_a_slot_that_can_hold_it(engine, ffmod, seed):
    """The bug this pins: a template was chosen at random and the seed placed
    afterwards, so it landed somewhere valid only when it happened to fit —
    measured at 35% of the time. The other 65% fell through to the "accent"
    fallback, which is how asking for a salmon recipe produced a mushroom soup
    with salmon bolted on beside it. Olive oil failed 30 times out of 30."""
    for _ in range(10):
        r = engine.generate_recipe(seed_ingredient=seed)
        slot = next(s for s, v in r["ingredients"].items() if v == seed)
        assert seed in ffmod.slot_candidate_set(slot), (
            f"{seed} placed in {slot!r}, which cannot hold it — {r['name']}")


def test_a_seed_and_a_dish_type_compose(engine):
    for seed, dish in (("salmon", "Soup"), ("honey", "Dessert & Sweet"),
                       ("quinoa", "Bowl"), ("parmesan", "Pizza & Flatbread")):
        r = engine.generate_recipe(seed_ingredient=seed, dish_type=dish)
        assert r["dish_type"] == dish, "the explicit dish type must win"
        assert seed in r["ingredients"].values()


def test_an_unknown_seed_is_ignored_not_fatal(engine):
    r = engine.generate_recipe(seed_ingredient="unobtainium")
    assert "error" not in r and r["ingredients"]


def test_a_seed_that_no_template_can_hold_is_still_honoured(engine, ffmod):
    """flour is held out of every slot on purpose — it is an ingredient of a
    dish, not a component to choose between. Seeding on it should still return
    a recipe containing it rather than silently dropping what was asked for."""
    used = {s for t in ffmod.DISH_TEMPLATES for s in t["structure"]}
    assert not any("flour" in ffmod.slot_candidate_set(s) for s in used),         "flour is now selectable; pick a different unreachable ingredient"
    r = engine.generate_recipe(seed_ingredient="flour")
    assert "flour" in r["ingredients"].values()


# ─── dish types ────────────────────────────────────────────────────────

def test_a_dish_type_is_honoured(engine, ffmod):
    for dish in ffmod.DISH_TYPES:
        if dish == "Any":
            continue
        for _ in range(6):
            assert engine.generate_recipe(dish_type=dish)["dish_type"] == dish


def test_any_means_no_filter(engine):
    seen = {engine.generate_recipe(dish_type="Any")["dish_type"] for _ in range(150)}
    assert len(seen) > 5, f"'Any' only produced {seen}"


def test_an_unknown_dish_type_falls_back_rather_than_failing(engine):
    r = engine.generate_recipe(dish_type="Molecular Gastronomy")
    assert "error" not in r and r["ingredients"]


# ─── surprise_me ───────────────────────────────────────────────────────

def test_surprise_me_returns_a_usable_recipe(engine):
    for _ in range(5):
        r = engine.surprise_me()
        assert "error" not in r
        assert r["ingredients"] and "{" not in r["name"]


def test_surprise_me_honours_a_dish_type(engine):
    for _ in range(4):
        assert engine.surprise_me(dish_type="Soup")["dish_type"] == "Soup"


def test_surprise_me_varies(engine):
    """It picks from the top candidates at random; always returning the same
    dish would make the button pointless."""
    names = {engine.surprise_me()["name"] for _ in range(12)}
    assert len(names) > 3, names


# ─── slot candidate caching ────────────────────────────────────────────

def test_the_slot_cache_matches_a_fresh_computation(ffmod):
    """The cache exists for speed — surprise_me rebuilt these ~8,700 times per
    click, 57% of its wall time. It must not change any answer."""
    for slot in {s for t in ffmod.DISH_TEMPLATES for s in t["structure"]}:
        assert sorted(ffmod.get_slot_candidates(slot)) == \
            sorted(ffmod._compute_slot_candidates(slot))


def test_exclusions_are_honoured_and_do_not_poison_the_cache(ffmod):
    slot = "vegetable"
    full = ffmod.get_slot_candidates(slot)
    victim = full[0]
    trimmed = ffmod.get_slot_candidates(slot, exclude={victim})
    assert victim not in trimmed
    assert len(trimmed) == len(full) - 1
    assert victim in ffmod.get_slot_candidates(slot), "exclusion leaked into the cache"


def test_the_caller_cannot_mutate_the_cache(ffmod):
    got = ffmod.get_slot_candidates("herb")
    got.append("not_an_ingredient")
    assert "not_an_ingredient" not in ffmod.get_slot_candidates("herb")


def test_subtype_slots_stay_distinct(ffmod):
    """noodle, bread and rice_type all map to the grain category but must not
    return each other's members — this is what stops rice being served as the
    noodle."""
    noodles = ffmod.slot_candidate_set("noodle")
    breads = ffmod.slot_candidate_set("bread")
    rice = ffmod.slot_candidate_set("rice_type")
    assert noodles and breads and rice
    assert not (noodles & breads) and not (noodles & rice) and not (breads & rice)
