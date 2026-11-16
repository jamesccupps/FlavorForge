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
    # Missed by the app's own list until 3.3.1.
    "gelatin": "meat", "custard": "egg", "béchamel": "dairy", "pad thai sauce": "fish",
}
# Phrases containing an animal word that are not animal products. Stripped
# before the scan — "peanut butter" is not butter, and a {nut} slot puts it
# into the rendered method regularly.
NOT_ANIMAL = ("coconut milk", "oat milk", "almond milk", "soy milk",
              "cashew milk", "coconut cream", "cashew cream", "coconut yogurt",
              "peanut butter", "almond butter", "cashew butter", "nut butter",
              "ice cream maker")


def _method_violations(text, diet, ffmod):
    # Any nut's name before "butter" is a nut butter: "{nut} butter" renders
    # as "pistachio butter", "macadamia butter" and so on.
    nut_butters = tuple(f"{i.name.lower()} butter" for i in ffmod.INGREDIENTS.values()
                        if i.category == "nut")
    for phrase in NOT_ANIMAL + nut_butters:
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
    """28 of 102 templates name an animal product in their instructions —
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


def _template(ffmod, fragment):
    matches = [t for t in ffmod.DISH_TEMPLATES if fragment in t["name"]]
    assert len(matches) == 1, f"{fragment!r} matches {len(matches)} templates"
    return matches[0]


# One row per template an outside review found misread in 3.3.0. The first
# four were missed, so a chosen diet was broken; the last three were caught
# for words that are not animal products, so vegans lost dishes that are vegan.
@pytest.mark.parametrize("fragment,expected", [
    ("Panna Cotta", {"dairy", "meat"}),            # cream; set with gelatin
    ("Tart with {spice} Custard", {"dairy", "egg"}),
    ("{cheese} Gratin", {"dairy"}),                # {cheese} béchamel
    ("Pad Thai", {"fish"}),                        # pad thai sauce
    ("Sorbet", set()),                             # "ice cream maker"
    ("{nut} Dip", set()),                          # "{nut} butter"
    ("Chutney", set()),                            # was "serve with cheese, meat"
])
def test_the_method_scan_reads_these_templates_correctly(ffmod, fragment, expected):
    assert ffmod.method_diet_tags(_template(ffmod, fragment)) == expected


def test_a_herb_butter_would_still_be_dairy(ffmod):
    """Only a {nut} slot makes "butter" a nut butter."""
    fake = {"technique": "Finish with {herb} butter.", "name": "x"}
    assert ffmod.method_diet_tags(fake) == {"dairy"}


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


def test_a_seed_the_diet_forbids_is_refused_not_placed(engine):
    """Through 3.2 this returned a bacon dish whose own report said it suited
    no diet at all — the seed won and the diet was dropped without a word."""
    r = engine.generate_recipe(seed_ingredient="bacon", diet="vegan")
    assert "error" in r
    assert "bacon" in r["error"] and "vegan" in r["error"]


def _viable(ffmod, dish, diet):
    return [t for t in ffmod.DISH_TEMPLATES
            if t["dish_type"] == dish and ffmod.template_allows(t, diet)
            and all(ffmod.get_slot_candidates(s, diet=diet) for s in t["structure"])]


@pytest.mark.parametrize("diet", ["pescatarian", "vegetarian", "vegan"])
def test_every_dish_type_either_honours_the_diet_or_says_it_cannot(engine, ffmod, diet):
    """The silent fallback this replaces: with no template left, generation
    used the unfiltered list, so a vegan Sauce & Dip came back as aioli and
    nothing said the diet had been dropped."""
    for dish in ffmod.DISH_TYPES[1:]:
        for _ in range(5):
            r = engine.generate_recipe(dish_type=dish, diet=diet)
            if _viable(ffmod, dish, diet):
                assert "error" not in r, (dish, r.get("error"))
                assert diet in r["diet"]["suits"], (dish, r["ingredients"])
            else:
                assert "error" in r and dish in r["error"], (dish, r)


def test_a_dish_type_the_diet_rules_out_entirely_is_refused(engine, ffmod, monkeypatch):
    """The refusal path, tested directly. The sweep above can only reach it
    when the data happens to contain an impossible pair, and since 3.3.1 it
    may not: the vegan Sauce & Dip that 3.3.0 refused was refused for three
    false matches (a nut butter, an ice cream maker, a serving suggestion)."""
    creamy = {"name": "{vegetable} Cream Dip", "dish_type": "Sauce & Dip",
              "structure": {"vegetable": 1},
              "technique": "Blend {vegetable} with cream.", "needs": ["vegetable"]}
    monkeypatch.setattr(ffmod, "DISH_TEMPLATES", [creamy])
    r = engine.generate_recipe(dish_type="Sauce & Dip", diet="vegan")
    assert "error" in r and "Sauce & Dip" in r["error"] and "vegan" in r["error"]


def test_cli_refuses_a_seed_the_diet_forbids(cli):
    code, out, err = cli("--recipe", "--seed", "bacon", "--diet", "vegan")
    assert code != 0
    assert "not vegan" in err
    assert out == ""


# ─── the label on a recipe made with no diet chosen ────────────────────

def test_the_label_never_contradicts_the_method(ffmod):
    """Through 3.3.0 the label read only the slots, so with no diet chosen a
    cream-and-gelatin panna cotta printed "SUITS: vegan". An outside review
    measured 17% of no-diet recipes labelled with a diet their own method
    rules out. Every template, a spread of random fills."""
    import random
    rng = random.Random(7)
    for t in ffmod.DISH_TEMPLATES:
        method = ffmod.method_diet_tags(t)
        for _ in range(20):
            fill = [rng.choice(ffmod.get_slot_candidates(s)) for s in t["structure"]]
            label = ffmod.recipe_diet(t, fill)
            for diet in label["suits"]:
                assert not (method & ffmod.DIET_FORBIDS[diet]), \
                    f"{t['name']} labelled {diet}, method says {sorted(method)}"
            assert method <= set(label["contains"])


def _only(monkeypatch, ffmod, fragment):
    t = next(t for t in ffmod.DISH_TEMPLATES if fragment in t["name"])
    monkeypatch.setattr(ffmod, "DISH_TEMPLATES", [t])
    return t


def test_a_generated_panna_cotta_is_not_called_vegan(engine, ffmod, monkeypatch):
    _only(monkeypatch, ffmod, "Panna Cotta")
    r = engine.generate_recipe()                      # no diet chosen
    assert r["diet"]["suits"] == [] and {"dairy", "meat"} <= set(r["diet"]["contains"])
    prompt = engine.recipe_to_ai_prompt(r)
    dietary = [l for l in prompt.splitlines() if l.startswith("DIETARY:")]
    assert not dietary or "vegan" not in dietary[0], "the AI Chef was told it is vegan"


def test_pantry_recipes_carry_the_same_label(engine, ffmod, monkeypatch):
    """They carried no diet information at all, so a pantry recipe sent to
    the AI Chef was labelled from its ingredients alone."""
    t = _only(monkeypatch, ffmod, "Panna Cotta")
    pantry = {ffmod.get_slot_candidates(s)[0] for s in t["structure"]}
    pantry |= {ffmod.get_slot_candidates(s)[1] for s in t["structure"]}
    found = engine.pantry_recipes(pantry)
    assert found, "the pantry should make at least one panna cotta"
    for r in found:
        assert "vegetarian" not in r["diet"]["suits"], r["name"]
    short = engine.almost_there(set(sorted(pantry)[:-1]))
    assert short, "one item short should still find a near miss"
    for r in short:
        assert "vegetarian" not in r["diet"]["suits"], r["name"]


@pytest.mark.parametrize("fragment,term", [
    ("Wonton Soup", "wonton skins"),     # usually egg
    ("Dumplings with", "dumpling skins"),
    ("Pot Pie", "pastry dough"),         # usually butter or lard
    ("Quiche", "pie crust"),
    ("Custard", "tart shell"),
    ("Shepherd's Pie", "gravy"),         # usually meat stock
    ("Gumbo", "stock"),                  # "add stock": which one is the cook's call
])
def test_method_words_that_depend_on_the_brand_say_check_the_label(ffmod, fragment, term):
    """The ingredient table could already say "check the label" on kimchi;
    nothing could say it about a method that wraps the filling in wonton
    skins. An outside review listed these."""
    t = _template(ffmod, fragment)
    assert term in ffmod.recipe_diet(t, [])["verify"]


def test_a_named_stock_is_not_a_check_the_label_item(ffmod):
    for text in ("Simmer in vegetable stock.", "Simmer in chicken stock."):
        assert "stock" not in ffmod.method_verify_terms({"technique": text})


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
