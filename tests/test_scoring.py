"""The pairing score: what it must guarantee regardless of the formula.

The engine's whole claim is that shared *rare* aroma compounds mean something
and shared ubiquitous ones do not. Under the original formula that claim did
not hold up numerically. The weight was ``0.5 + 0.5 * (1 - freq/N)``, so a
compound present in 64% of the database still scored 0.68 against a maximum of
1.0 — 70% as much as a compound found in one ingredient. The floor, not the
rarity term, dominated.

The measurable consequence: of the 31,387 ingredient pairs the app reported as
having *any* connection, 16,501 — 52.6% — shared nothing but hexanal, linalool
or nonanal. Over half of everything called a "pairing" was three near-universal
green/citrus notes.

The tests below are written against the *property* rather than the formula, so
they survive a change of weighting: rarer must beat commoner, the ubiquitous
floor must be low, and the pairings that are chemically real must stay at the
top. The last is what stops a "fix" that simply flattens everything to zero.
"""
import itertools
import statistics

import pytest

# Present in >30% of ingredients — what the engine itself calls "boring".
UBIQUITOUS = {"hexanal", "linalool", "nonanal"}


# ─── invariants that must hold for any weighting ───────────────────────

def test_scores_are_bounded(engine, ffmod):
    for a, b in itertools.islice(itertools.combinations(ffmod.INGREDIENTS, 2), 4000):
        score, _ = engine.weighted_similarity(a, b)
        assert 0.0 <= score <= 1.0, f"{a}/{b} -> {score}"


def test_an_ingredient_with_no_compounds_scores_zero(engine):
    for other in ("chicken", "tomato", "basil"):
        assert engine.weighted_similarity("salt", other) == (0.0, set())


def test_an_unknown_ingredient_scores_zero(engine):
    assert engine.weighted_similarity("unobtainium", "tomato") == (0.0, set())
    assert engine.weighted_similarity("tomato", "unobtainium") == (0.0, set())


def test_scoring_is_symmetric(engine, ffmod):
    for a, b in itertools.islice(itertools.combinations(ffmod.INGREDIENTS, 2), 2000):
        assert engine.weighted_similarity(a, b)[0] == engine.weighted_similarity(b, a)[0]


def test_sharing_nothing_scores_zero(engine, ffmod):
    found = False
    for a, b in itertools.combinations(list(ffmod.INGREDIENTS)[:120], 2):
        if not (ffmod.INGREDIENTS[a].compounds & ffmod.INGREDIENTS[b].compounds):
            assert engine.weighted_similarity(a, b)[0] == 0.0
            found = True
    assert found, "no disjoint pair in the sample; the test proved nothing"


# ─── the property the README actually claims ───────────────────────────

def test_rarer_compounds_outweigh_commoner_ones(engine, ffmod):
    """Monotonicity: across the whole compound set, weight must fall as the
    compound gets more common. Nothing in the original formula violated this —
    it was the *magnitude* that was wrong — so this is the floor, not the bar."""
    weights = [(engine._compound_freq[c], engine._compound_weight(c))
               for c in ffmod.COMPOUNDS]
    weights.sort()
    for (f1, w1), (f2, w2) in zip(weights, weights[1:]):
        if f1 < f2:
            assert w1 >= w2, f"freq {f1} weighted {w1} < freq {f2} weighted {w2}"


def test_a_ubiquitous_compound_is_heavily_discounted(engine):
    """The bar the old formula failed. hexanal is in ~63% of the database; it
    must not count anywhere near what a rare compound counts."""
    hexanal = engine._compound_weight("hexanal")
    rare = engine._compound_weight("geosmin")        # 1 ingredient
    assert hexanal < 0.25 * rare, (
        f"hexanal weighted {hexanal:.3f} against rare {rare:.3f} — "
        f"{hexanal/rare:.0%} of a unique compound is not a discount")


def test_ubiquitous_only_pairs_score_far_below_real_ones(engine, ffmod):
    """These are the 52.6%. They are not wrong to be non-zero — the compounds
    really are shared — but they must not compete with a real match.

    Asserted distributionally, not against a fixed number, because a fixed
    number cannot do the job: measured across all 32,269 connected pairs, the
    two populations overlap so heavily that 83.6% of pairs WITH a distinctive
    shared compound score below the highest ubiquitous-only pair. A pair of
    four-compound ingredients that share three ubiquitous ones genuinely is
    three-quarters identical by profile; the score is right, it is the
    *shortlist* that must exclude it. That is why get_pairings and find_bridge
    filter on the shared set rather than on a threshold."""
    noise, real = [], []
    for a, b in itertools.combinations(list(ffmod.INGREDIENTS)[:220], 2):
        shared = ffmod.INGREDIENTS[a].compounds & ffmod.INGREDIENTS[b].compounds
        if not shared:
            continue
        score = engine.weighted_similarity(a, b)[0]
        (noise if shared <= UBIQUITOUS else real).append(score)

    assert len(noise) > 200 and len(real) > 200, (len(noise), len(real))
    noise_median = statistics.median(noise)
    real_median = statistics.median(real)
    assert noise_median < real_median / 3, (
        f"ubiquitous-only median {noise_median:.3f} against real "
        f"{real_median:.3f} — the rarity weighting is not separating them")


def test_the_two_populations_cannot_be_split_by_a_threshold(engine, ffmod):
    """The finding that dictates the design above, pinned so nobody 'simplifies'
    the set-based filter into a min_score and believes it equivalent."""
    noise_max, real_below = 0.0, 0
    reals = []
    for a, b in itertools.combinations(list(ffmod.INGREDIENTS)[:220], 2):
        shared = ffmod.INGREDIENTS[a].compounds & ffmod.INGREDIENTS[b].compounds
        if not shared:
            continue
        score = engine.weighted_similarity(a, b)[0]
        if shared <= UBIQUITOUS:
            noise_max = max(noise_max, score)
        else:
            reals.append(score)
    real_below = sum(1 for s in reals if s < noise_max)
    assert real_below > 0.5 * len(reals), (
        "the populations now separate cleanly by score, so the set-based "
        "filter may no longer be necessary — re-derive it before removing")


def test_ubiquitous_noise_falls_out_of_the_top_results(engine, ffmod):
    """The user-visible payoff: the Pairing tab shows 25 rows, and they should
    be 25 real ones."""
    for seed in ("strawberry", "garlic", "salmon", "mushroom_button", "lemon"):
        top = engine.get_pairings(seed, 25)
        noise = [p for p in top if p["shared_compounds"] <= UBIQUITOUS]
        assert not noise, (
            f"{seed}: {len(noise)} of 25 top pairings share only "
            f"{UBIQUITOUS}: {[p['ingredient'] for p in noise][:5]}")


# ─── the chemistry that must survive the change ────────────────────────

REAL_PAIRINGS = [
    # (seed, partner, the compounds that justify it)
    ("strawberry", "raspberry", {"furaneol", "ionone"}),
    ("garlic", "onion", {"diallyl_disulfide"}),
    ("salmon", "oyster", {"trimethylamine"}),
    ("coffee", "chocolate", {"methylpyrazine", "furfural"}),
    ("tomato", "strawberry", {"furaneol"}),
    ("arugula", "horseradish", {"allyl_isothiocyanate"}),
    ("bay_leaf", "nutmeg", {"sabinene", "terpinene"}),
]


@pytest.mark.parametrize("seed,partner,why", REAL_PAIRINGS)
def test_the_chemically_real_pairings_stay_near_the_top(engine, seed, partner, why):
    """A weighting that scored everything at zero would satisfy every test
    above. This is what stops that."""
    top = [p["ingredient"] for p in engine.get_pairings(seed, 15)]
    assert partner in top, f"{partner} fell out of {seed}'s top 15: {top[:8]}"
    shared = engine.weighted_similarity(seed, partner)[1]
    assert why <= shared, f"{seed}/{partner} no longer share {why - shared}"


def test_an_ingredient_is_not_its_own_pairing(engine):
    assert all(p["ingredient"] != "garlic" for p in engine.get_pairings("garlic", 25))


def test_identical_profiles_score_at_the_ceiling(engine, ffmod):
    """Two ingredients with the same compound set are as similar as it gets."""
    score, shared = engine.weighted_similarity("garlic", "garlic_powder")
    assert score > 0.5, f"garlic/garlic powder only {score:.3f}"
    assert "allicin" in shared


# ─── find_bridge must use the same notion of rarity ────────────────────

def test_bridges_are_rarity_weighted_like_pairings(engine, ffmod):
    """find_bridge used raw compound COUNTS while weighted_similarity used
    rarity, so the app held two different ideas of what "connected" means. A
    bridge whose only link to both ends is hexanal is not a bridge."""
    seen = 0
    for a, b in (("pork", "apple"), ("strawberry", "basil"), ("beef", "coffee")):
        for br in engine.find_bridge(a, b):
            assert not (br["connects_to_a"] <= UBIQUITOUS
                        and br["connects_to_b"] <= UBIQUITOUS), (
                f"{br['ingredient']} 'bridges' {a} and {b} on nothing but "
                f"{br['connects_to_a'] | br['connects_to_b']}")
            seen += 1
    assert seen > 10, "not enough bridges sampled"


def test_a_bridge_must_genuinely_touch_both_sides(engine):
    for br in engine.find_bridge("pork", "apple"):
        assert br["connects_to_a"] and br["connects_to_b"]
        assert br["ingredient"] not in ("pork", "apple")


def test_bridge_scores_are_bounded(engine):
    for pair in (("pork", "apple"), ("salmon", "strawberry"), ("beef", "lemon")):
        for br in engine.find_bridge(*pair):
            assert 0.0 <= br["score"] <= 1.0, f"{br['ingredient']} -> {br['score']}"


# ─── novelty ───────────────────────────────────────────────────────────

def test_novelty_is_bounded(engine, ffmod):
    import random
    rng = random.Random(0)
    names = list(ffmod.INGREDIENTS)
    for _ in range(300):
        picks = rng.sample(names, rng.randint(2, 7))
        assert 0.0 <= engine.novelty_score(picks) <= 1.0


def test_novelty_needs_at_least_two_ingredients(engine):
    assert engine.novelty_score([]) == 0.0
    assert engine.novelty_score(["tomato"]) == 0.0


def test_novelty_ignores_unknown_names(engine):
    """A slot that could not be filled leaves a name the database has never
    heard of; it must not crash the scorer."""
    assert 0.0 <= engine.novelty_score(["tomato", "not_a_real_thing", "basil"]) <= 1.0


# ─── determinism ───────────────────────────────────────────────────────

def test_manual_accumulation_really_is_order_sensitive():
    """Establishes the hazard the sort exists for, on every interpreter.

    sum() over floats gained Neumaier compensated summation in CPython 3.12,
    so on 3.12+ it is order-insensitive and this hazard is invisible through
    sum() alone — which is precisely why the first CI run for this release was
    green on all four 3.12/3.13 legs and red on all four 3.10/3.11 legs.
    Accumulating by hand is naive on every version, so it demonstrates the
    problem anywhere.
    """
    vals = [1.0, 1e16, -1e16]
    fwd = 0.0
    for v in vals:
        fwd += v
    rev = 0.0
    for v in reversed(vals):
        rev += v
    assert fwd != rev, "float addition has become associative; revisit the sort"


def test_the_weight_sum_does_not_depend_on_iteration_order(engine, ffmod, monkeypatch):
    """The property, asserted against order-sensitive weights.

    On 3.10/3.11 this fails without the sort. On 3.12+ sum() compensates and
    it passes either way, so the source check below is what carries the
    guarantee there — noted rather than hidden, because a test that only bites
    on half the matrix should say so.
    """
    keys = sorted(ffmod.COMPOUNDS)[:3]
    monkeypatch.setattr(engine, "_weight",
                        {keys[0]: 1.0, keys[1]: 1e16, keys[2]: -1e16})
    expected = engine._sum_weights(keys)
    for order in ([keys[2], keys[1], keys[0]], [keys[1], keys[2], keys[0]]):
        assert engine._sum_weights(order) == expected,             f"summation depends on order: {order}"
    assert engine._sum_weights(set(keys)) == expected


def test_the_weight_sum_is_explicitly_ordered():
    """The check that holds on every interpreter, including the ones where
    sum() hides the problem."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "flavorforge.py").read_text(encoding="utf-8")
    body = src[src.index("def _sum_weights("):]
    body = body[:body.index("\n    def ")]
    assert re.search(r"for c in sorted\(", body),         "_sum_weights no longer imposes an order; it will drift by hash order on 3.11"


def test_symmetry_holds_across_the_whole_database(engine, ffmod):
    """The sweep the CI failure came from, run over every pair rather than the
    first 2,000, now that the result no longer depends on iteration order."""
    names = list(ffmod.INGREDIENTS)
    for a, b in itertools.combinations(names, 2):
        x = engine.weighted_similarity(a, b)[0]
        y = engine.weighted_similarity(b, a)[0]
        assert x == y, f"{a}/{b}: {x!r} vs {y!r}"


def test_bridge_scores_are_symmetric_in_their_inputs(engine):
    """find_bridge sums over sets the same way and had the same exposure."""
    for a, b in (("pork", "apple"), ("beef", "coffee"), ("strawberry", "basil")):
        fwd = {x["ingredient"]: x["score"] for x in engine.find_bridge(a, b)}
        rev = {x["ingredient"]: x["score"] for x in engine.find_bridge(b, a)}
        assert fwd == rev, f"{a}/{b} bridges differ by argument order"
