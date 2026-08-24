"""Dietary classification and filtering.

A claim about food that somebody might act on, so the tests are stricter than
elsewhere: they check the classification, the two independent filters it drives
(ingredients and template prose), and then sweep thousands of generated recipes
looking for anything that contradicts its own label.

v3.0 inferred diet from the ingredient category and got two things backwards in
opposite directions — tofu and tempeh are category "protein", so a tofu
stir-fry was reported as NOT vegetarian, while egg, which IS vegetarian, was
excluded for the same reason. There was also no way to ASK for a diet; it was
only ever reported after the fact.
"""
import re

import pytest

# Words that would contradict a diet if they appeared in a recipe's method.
ANIMAL_WORDS = {
    "parmesan": "dairy", "pecorino": "dairy", "mozzarella": "dairy",
    "cheese": "dairy", "butter": "dairy", "cream": "dairy", "milk": "dairy",
    "yogurt": "dairy", "buttermilk": "dairy", "ghee": "dairy",
    "egg": "egg", "eggs": "egg", "mayo": "egg", "mayonnaise": "egg",
    "bacon": "meat", "prosciutto": "meat", "pancetta": "meat", "lard": "meat",
    "anchovy": "fish", "anchovies": "fish", "fish sauce": "fish", "dashi": "fish",
    "honey": "honey",
}
# Phrases containing an animal word that are not animal products. Stripped
# before the scan — "peanut butter" is not butter, and a {nut} slot puts it
# into the rendered method regularly.
NOT_ANIMAL = ("coconut milk", "oat milk", "almond milk", "soy milk",
              "cashew milk", "coconut cream", "cashew cream", "coconut yogurt",
              "peanut butter", "almond butter", "cashew butter", "nut butter")


def _method_violations(text, diet, ffmod):
    for phrase in NOT_ANIMAL:
        text = text.replace(phrase, " ")
    forbidden = ffmod.DIET_FORBIDS[diet]
    return [w for w, tag in ANIMAL_WORDS.items()
            if tag in forbidden and re.search(r"\b" + re.escape(w) + r"\b", text)]


# ─── the classification ────────────────────────────────────────────────

def test_the_two_bugs_from_v3(ffmod):
    """Tofu and tempeh are plants filed under "protein"; egg is an animal
    product that is nonetheless vegetarian. The category could express
    neither."""
    assert ffmod.diet_allows("tofu", "vegetarian")
    assert ffmod.diet_allows("tempeh", "vegetarian")
    assert ffmod.diet_allows("tofu", "vegan")
    assert ffmod.diet_allows("egg", "vegetarian")
    assert not ffmod.diet_allows("egg", "vegan")


@pytest.mark.parametrize("name,diet,allowed", [
    # animal products that do not sit in an animal category
    ("chicken_stock", "vegetarian", False),
    ("bone_broth", "vegetarian", False),
    ("beef_stock", "vegetarian", False),
    ("fish_sauce", "vegetarian", False),
    ("fish_sauce", "pescatarian", True),
    ("worcestershire", "vegetarian", False),      # anchovy
    ("dashi", "vegetarian", False),               # bonito
    ("egg_noodles", "vegan", False),              # the grain aisle
    ("brioche", "vegan", False),
    ("honey", "vegetarian", True),
    ("honey", "vegan", False),
    ("ranch", "vegan", False),                    # mayonnaise and buttermilk
    ("mayo", "vegan", False),
    ("pesto", "vegan", False),                    # parmesan, traditionally
    # plants that do not sit in a plant category
    ("coconut_milk", "vegan", True),              # filed under dairy
    ("cashew_cream", "vegan", True),
    ("oat_milk", "vegan", True),
    ("coconut_yogurt", "vegan", True),
    ("peanut_butter", "vegan", True),
    ("seitan", "vegan", True),
    ("nutritional_yeast", "vegan", True),
    # meat and fish
    ("bacon", "pescatarian", False),
    ("salmon", "pescatarian", True),
    ("salmon", "vegetarian", False),
    ("duck_fat", "vegetarian", False),
    ("ghee", "vegetarian", True),
    ("ghee", "vegan", False),
])
def test_specific_classifications(ffmod, name, diet, allowed):
    assert name in ffmod.INGREDIENTS, f"{name} is not an ingredient"
    assert ffmod.diet_allows(name, diet) is allowed


def test_every_seafood_is_excluded_from_vegetarian(ffmod):
    for n, i in ffmod.INGREDIENTS.items():
        if i.category == "seafood":
            assert not ffmod.diet_allows(n, "vegetarian"), n
            assert ffmod.diet_allows(n, "pescatarian"), n


def test_every_dairy_is_excluded_from_vegan_unless_it_is_a_plant(ffmod):
    plants = {"coconut_milk", "cashew_cream", "oat_milk", "coconut_yogurt"}
    for n, i in ffmod.INGREDIENTS.items():
        if i.category == "dairy":
            assert ffmod.diet_allows(n, "vegan") is (n in plants), n


def test_an_unclassified_ingredient_is_not_assumed_vegan(ffmod):
    """The fallback must fail safe. A new seafood or dairy entry added without
    a DIET_TAGS line should still be excluded, not silently permitted."""
    assert ffmod.diet_tags("squid") == {"fish"}
    assert "dairy" in ffmod.diet_tags("brie")


def test_ambiguous_ingredients_are_flagged_not_guessed(ffmod):
    """Whether kimchi is vegan depends on the jar. Saying so is better than
    picking an answer, and better than dropping every condiment."""
    for n in ("kimchi", "caramel", "curry_paste", "chocolate", "naan", "gnocchi"):
        assert "verify" in ffmod.diet_tags(n), n
    # A "verify" item is never auto-excluded — it is surfaced.
    assert ffmod.diet_allows("kimchi", "vegan")


def test_dietary_profile_reports_what_it_found(ffmod):
    p = ffmod.dietary_profile(["tofu", "broccoli", "sesame_oil"])
    assert "vegan" in p["suits"] and "vegetarian" in p["suits"]
    assert p["contains"] == [] and p["verify"] == []

    p = ffmod.dietary_profile(["chicken", "parmesan", "honey"])
    assert p["suits"] == []
    assert set(p["contains"]) == {"meat", "dairy", "honey"}

    p = ffmod.dietary_profile(["tofu", "kimchi"])
    assert p["verify"] == ["kimchi"]


def test_the_diets_are_nested_correctly(ffmod):
    """Anything vegan is vegetarian is pescatarian. A classification that
    breaks that ordering is wrong somewhere."""
    for n in ffmod.INGREDIENTS:
        if ffmod.diet_allows(n, "vegan"):
            assert ffmod.diet_allows(n, "vegetarian"), n
        if ffmod.diet_allows(n, "vegetarian"):
            assert ffmod.diet_allows(n, "pescatarian"), n


# ─── the template-prose filter ─────────────────────────────────────────

def test_template_methods_are_scanned_for_what_the_slots_cannot_see(ffmod):
    """29 of 102 templates name an animal product in their instructions —
    "finish with cream", "top with a fried egg" — which no slot holds. Without
    this, a vegan recipe could be produced whose own method says add parmesan.
    """
    tagged = [t for t in ffmod.DISH_TEMPLATES if ffmod.method_diet_tags(t)]
    assert len(tagged) > 20, f"only {len(tagged)} templates tagged; the scan looks broken"
    assert len(tagged) < len(ffmod.DISH_TEMPLATES), "every template tagged; scan too broad"


def test_a_chowder_is_not_offered_as_vegan(ffmod):
    chowders = [t for t in ffmod.DISH_TEMPLATES if "Chowder" in t["name"]]
    assert chowders, "no chowder template to check"
    for t in chowders:
        assert not ffmod.template_allows(t, "vegan")


def test_plant_milks_do_not_tag_a_template_as_dairy(ffmod):
    fake = {"technique": "Simmer in coconut milk and finish with cashew cream.",
            "name": "x"}
    assert ffmod.method_diet_tags(fake) == set()


def test_nut_butters_do_not_tag_a_template_as_dairy(ffmod):
    """Found the hard way: \\bbutter\\b matches "peanut butter"."""
    fake = {"technique": "Whisk peanut butter into the sauce.", "name": "x"}
    assert ffmod.method_diet_tags(fake) == set()


def test_a_real_dairy_mention_is_still_caught(ffmod):
    """Guard on the guard above — the exclusions must not have blinded it."""
    fake = {"technique": "Finish with butter and a spoon of cream.", "name": "x"}
    assert "dairy" in ffmod.method_diet_tags(fake)
    fake = {"technique": "Render the bacon, then add a splash of fish sauce.", "name": "x"}
    assert ffmod.method_diet_tags(fake) == {"meat", "fish"}


def test_every_diet_still_has_templates(ffmod):
    for d in ffmod.DIETS:
        n = sum(1 for t in ffmod.DISH_TEMPLATES if ffmod.template_allows(t, d))
        assert n >= 40, f"{d} left with only {n} templates"


# ─── generation ────────────────────────────────────────────────────────

@pytest.mark.parametrize("diet", ["pescatarian", "vegetarian", "vegan"])
def test_no_generated_recipe_contains_a_forbidden_ingredient(engine, ffmod, diet):
    for _ in range(300):
        r = engine.generate_recipe(diet=diet)
        for name in r["ingredients"].values():
            assert ffmod.diet_allows(name, diet), \
                f"{name} in a {diet} recipe: {r['name']}"


@pytest.mark.parametrize("diet", ["pescatarian", "vegetarian", "vegan"])
def test_no_generated_method_contradicts_its_own_diet(engine, ffmod, diet):
    """The half the slot filter cannot see."""
    for _ in range(300):
        r = engine.generate_recipe(diet=diet)
        bad = _method_violations(r["technique"].lower(), diet, ffmod)
        assert not bad, f"{diet}: method mentions {bad} — {r['technique']}"


def test_the_reported_profile_matches_the_requested_diet(engine, ffmod):
    for diet in ("pescatarian", "vegetarian", "vegan"):
        for _ in range(80):
            r = engine.generate_recipe(diet=diet)
            assert diet in r["diet"]["suits"], (diet, r["name"], r["diet"])


def test_a_diet_and_a_dish_type_compose(engine, ffmod):
    for dish in ("Soup", "Bowl", "Salad & Slaw", "Pasta & Noodles"):
        for _ in range(20):
            r = engine.generate_recipe(dish_type=dish, diet="vegan")
            assert r["dish_type"] == dish
            for name in r["ingredients"].values():
                assert ffmod.diet_allows(name, "vegan"), (dish, name)


def test_a_diet_and_a_seed_compose(engine, ffmod):
    for seed in ("tofu", "chickpea", "shiitake", "quinoa"):
        for _ in range(15):
            r = engine.generate_recipe(seed_ingredient=seed, diet="vegan")
            assert seed in r["ingredients"].values()
            for name in r["ingredients"].values():
                assert ffmod.diet_allows(name, "vegan")


def test_surprise_me_honours_a_diet(engine, ffmod):
    for _ in range(6):
        r = engine.surprise_me(diet="vegan")
        for name in r["ingredients"].values():
            assert ffmod.diet_allows(name, "vegan"), r["name"]


def test_omnivore_and_none_do_not_filter(engine, ffmod):
    """A diet that forbids nothing must not narrow the pool, or every recipe
    becomes a subset for no reason."""
    assert (ffmod.get_slot_candidates("protein", diet="omnivore")
            == ffmod.get_slot_candidates("protein"))
    assert (ffmod.get_slot_candidates("protein", diet=None)
            == ffmod.get_slot_candidates("protein"))


def test_a_diet_actually_narrows_the_pool(engine, ffmod):
    """Guard on the guard: prove the filter does something, so the test above
    is not passing because filtering is broken everywhere."""
    full = len(ffmod.get_slot_candidates("protein"))
    veg = len(ffmod.get_slot_candidates("protein", diet="vegetarian"))
    assert veg < full, "the vegetarian filter removed no proteins"


def test_meat_free_diets_have_enough_protein_to_be_useful(ffmod):
    """The filter is what exposed this: before 3.2 a vegetarian had 3 usable
    proteins and a vegan 2, so every meat-free recipe was tofu or tempeh."""
    for diet, floor in (("vegetarian", 4), ("vegan", 3)):
        n = len(ffmod.get_slot_candidates("protein", diet=diet))
        assert n >= floor, f"{diet} has only {n} proteins to choose from"


# ─── the CLI ───────────────────────────────────────────────────────────

def test_cli_diet(cli):
    code, out, _ = cli("--recipe", "--diet", "vegan")
    assert code == 0
    assert "vegan" in out


def test_cli_rejects_an_unknown_diet(cli):
    with pytest.raises(SystemExit):
        cli("--recipe", "--diet", "carnivore")
