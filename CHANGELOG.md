# Changelog

## [3.2.0] — 2026-08-24

Answers "what else should this have?" with what the data said, not what
sounded good.

### Added

- **Diet filtering, as an input.** Recipe tab dropdown, `--diet` on the CLI:
  omnivore, pescatarian, vegetarian, vegan. Previously diet was only ever
  *reported*, after the fact, and there was no way to ask for one.
- **26 ingredients**, chosen from measured shortfalls: plant proteins (seitan,
  jackfruit, halloumi, paneer), dairy alternatives (nutritional yeast, cashew
  cream, oat milk, coconut yogurt), five herbs (chervil, savory, shiso, Thai
  basil, lovage), three citrus (yuzu, blood orange, mandarin), four fats (ghee,
  peanut, walnut, duck), three legumes and three sweeteners.
  **Not** more pasta shapes: 24 noodles already share 8 compound profiles
  between them, so another adds a dropdown row and nothing to the chemistry.

### Fixed

- **Diet was inferred from the ingredient category and got it backwards in
  both directions.** Tofu and tempeh are category "protein", so a tofu stir-fry
  was reported as NOT vegetarian; egg, which is vegetarian, was excluded for
  the same reason. It is now classified per ingredient, because the category
  cannot carry it: chicken stock is a "sauce", fish sauce and Worcestershire
  are "fermented", coconut milk is filed under "dairy" because it behaves like
  cream in a pan, and mayonnaise is egg rather than milk.
- **Animal products hiding in the grain aisle.** Egg noodles contain egg and
  were untagged, so a vegan recipe could be generated whose noodle was egg
  noodles. Brioche likewise.
- **Recipe methods that contradicted their own label.** 29 of 102 templates
  name an animal product in prose no slot holds — "finish with cream", "top
  with a fried egg" — so a vegan dish could instruct you to add parmesan. Those
  templates are now excluded from diets that forbid what they assume, derived
  by scanning the prose so it cannot drift as templates are edited. A chowder
  without cream is not a chowder; the honest answer is that it is not vegan.
- Ambiguous ingredients are flagged rather than guessed. Whether kimchi,
  caramel, curry paste, naan, gnocchi or chocolate suits a diet depends on the
  jar, and the app says so instead of picking an answer or silently dropping
  half the condiments.

### Performance

- Pair scores are memoised and the union weight derived rather than summed.
  Dragging the Graph tab's threshold slider re-derived all 45,753 pairs on
  every movement: **142 ms → 10.5 ms**. Surprise Me 63 ms → 32 ms warm.

### Notes

- 182 → 237 tests. The diet tests sweep 2,400 generated recipes checking that
  none contradicts its own label, in ingredients or in prose.

## [3.1.0] — 2026-08-24

Acts on an independent audit of 3.0. Two changes alter results you may have
relied on — see **Changed** first.

### Changed

- **Pairing scores are now inverse-document-frequency weighted, which changes
  every number the app displays.** The old weight was `0.5 + 0.5 × rarity`.
  Monotonic, so it looked right, but the constant floor swamped the rarity
  term: hexanal, present in 63% of the database, scored 0.68 against a ceiling
  of 1.0 — 70% of what a compound found in a single ingredient was worth.
  Measured before the change: of the 31,387 ingredient pairs the app reported
  as connected, 16,501 — **52.6%** — shared nothing but hexanal, linalool or
  nonanal. Over half of every "pairing" was three compounds that are in almost
  everything. Under IDF, hexanal is worth 8% of a unique compound.
- **The similarity is now genuinely Jaccard**, weighted shared over weighted
  union. It never was: it divided by the average profile size, while the README
  has called it "rarity-weighted Jaccard similarity" since 1.0. Identical
  profiles now score 1.0, as they should.
- **Ranked lists drop matches resting entirely on compounds present in >30% of
  the database.** The filter works on the shared *set*, not a score threshold,
  because a threshold cannot do the job — 83.6% of pairs with a genuinely
  distinctive shared compound score below the highest ubiquitous-only pair.
- **`find_bridge` is rarity-weighted too.** It used raw compound counts and
  divided by the bridge's own profile size, so a small ingredient sharing
  hexanal with both ends floated to the top. "Zucchini bridges pork and apple"
  was a real result. A bridge is now scored by the weaker of its two links.

What this does to real queries: garlic → onion reaches the top five;
`mushroom_button` surfaces eggplant, chanterelle, walnut and morel on
1-octen-3-ol, where it previously returned ten rows of hexanal coincidence;
pork/apple bridges are parmesan, vinegar and black tea on diacetyl and
methional.

### Added

- **A command line.** The engine could only be driven through 2,000 lines of
  Tk — not scriptable, not usable over SSH, not usable at all without a GUI
  toolkit. `--pair`, `--substitute`, `--bridge`, `--compound`, `--recipe`,
  `--list`. No arguments still starts the GUI. The tkinter import is guarded,
  so the data, engine and CLI load on a headless box.
- **Substitutions.** A different question from a pairing: a pairing goes *with*
  an ingredient, a substitute stands *in* for it. Same category, and the same
  subtype where there is one, so a stock is never offered in place of a
  vinaigrette. Aroma matches rank above role-only matches, and role-only
  matches say so. In the Pairing tab and on the CLI.
- **Compound lookup.** The database could only be read one way — pick an
  ingredient, see its compounds. `--compound geosmin` answers the other half,
  or searches names and descriptions.
- **A model picker for the AI Chef**, with Claude Opus 5, Sonnet 5 and
  Haiku 4.5, so the model cannot go stale in a source constant again.
- **Six ingredients**: bay leaf, marjoram, arugula, squid, black tea, red wine.
- **171 tests and CI** on Linux and Windows across Python 3.10–3.13. The
  repository previously had none.
- `pyproject.toml`, a `flavorforge` console script, and `--version`.

### Fixed

- **No generated recipe could contain a cooking fat.** The `oil` slot was
  declared and used by none of the 102 templates, so 0 of 3 oil/fat
  ingredients could ever be selected — while `_add_staples` listed olive oil
  as a pantry staple and `analyze_balance` advised "Needs richness — add
  butter, oil", advice the generator could not take.
- **65% of seeded recipes bolted the seed on as an "accent".** A template was
  chosen at random and the seed placed afterwards, so it landed in a real slot
  only if it happened to fit. Asking for a salmon recipe produced a mushroom
  soup with salmon beside it; olive oil failed 30 times out of 30. Now 0 of
  300.
- **Seven compounds were defined and attached to no ingredient** — 8% of the
  database was inert. chavicol's own description reads "basil, spicy, warm"
  and basil did not have it. Each is now attached where the chemistry puts it
  (chavicol → basil, acetophenone → cherry, indole → jasmine rice,
  linalool_oxide → black tea, whiskey_lactone → red wine) or removed, for the
  two with no honest home in this database.
- **Two override tables were keyed on ingredients that did not exist**, so
  they silently never applied. Both were evidence the ingredient was meant to
  be here; squid and arugula are now in.
- **2-acetyl-1-pyrroline was filed as a pyrazine.** It is a pyrroline — five
  atoms and one nitrogen against six and two.
- **The module docstring was three versions stale**: 190 ingredients where
  there were 297, 77 templates where there were 102, and a dish-type count
  that included the "Any" filter. Now asserted against the data.
- **The AI Chef was pinned to `claude-sonnet-4-20250514`**, three model
  generations old. A config saved by 3.0 is migrated forward on load rather
  than 404-ing on the first generation.
- **Claude responses did not stream** while Ollama's did, so the same tab
  behaved completely differently by provider — thirty seconds of spinner, then
  everything at once.
- **A truncated recipe looked finished.** `stop_reason` was never inspected, so
  a response cut off at the token ceiling simply stopped mid-step. `max_tokens`
  also rises from 4096 to 16000.
- **All three home-directory files truncated in place.** The pantry, the saved
  recipes and the config — which holds the API key — are now written to a temp
  file and atomically replaced. The config is owner-only on POSIX. Reads
  tolerate a byte-order mark, which Notepad writes and plain UTF-8 rejects.
- **The UDP-style slot maps inside `generate_recipe`** duplicated
  `SLOT_CAT_MAP`, had drifted from it, were rebuilt on every one of 60
  iterations, and did not understand subtypes — a grain seed could be placed
  in a noodle slot.
- README corrections: coffee and chocolate share 7 compounds, not 6, and
  gamma-decalactone is in 5.7% of the database, not "<5%".

### Performance

- Slot candidate lists are computed once per slot rather than rebuilt on every
  lookup — 8,715 full scans of the ingredient database per Surprise Me, 57% of
  its wall time. Surprise Me 102 ms → 41 ms; `generate_recipe` 2.39 ms →
  0.87 ms.

## v3.0.0 (2026-04-14)

### Major Features
- **Build a Dish** tab — guided dish building with ingredient slot suggestions
- **My Pantry** tab — check off what you have, find recipes, smart shopping list
- **AI Chef** tab — send recipes to Ollama or Claude API for full recipe generation
- **Save recipes** — save concepts and AI-generated recipes
- **Texture & Taste Balance** system — analyzes crunch, creaminess, salt, acid, umami
- **102 recipe templates** across 16 dish types including burgers, wings, nachos, dumplings, mac & cheese, ceviche, chowders, ramen, and more

### Ingredients & Data
- **297 ingredients** with flavor descriptions
- **84 aroma compounds** from flavor science research
- **1,632 flavor links**
- **24 noodle/pasta varieties** — spaghetti through udon, each with descriptions
- **9 bread types** — sourdough, ciabatta, brioche, naan, pita, etc.
- **7 rice varieties** — jasmine, basmati, arborio, sticky, wild, etc.
- **8 broth/stock bases** — chicken, beef, bone broth, dashi, coconut broth, miso broth
- **11 cooking sauces** — marinara, pesto, alfredo, curry paste, enchilada sauce, etc.
- **Seasonings & condiments** — salt, MSG, garlic powder, hot sauce, sriracha, BBQ sauce, ranch, etc.
- **Spice blends** — garam masala, za'atar, five spice, Old Bay, Italian seasoning, etc.
- Every ingredient shows a description explaining what it is

### Quality
- Smart slot types prevent stocks in pizza sauce slots, chocolate in salad dressings
- Compound rarity weighting — rare shared compounds score higher than common ones
- Boring compound filtering in displays — hides hexanal/nonanal noise
- Dietary flags in AI prompts (vegetarian, pescatarian)
- Balance suggestions for texture gaps and taste imbalances

### Performance
- Compound frequency cached at startup — 9x faster recipe generation
- Surprise Me optimized — 20x faster (0.12s vs 2.4s)
- Pantry search 50x faster

### Technical
- Windows high-DPI fix (SetProcessDpiAwareness)
- Zero external dependencies — pure Python stdlib + tkinter
- All user data persists between sessions via JSON files

## v2.0.0

- Expanded to 155 ingredients, 77 templates
- Added AI Chef integration (Ollama/Claude)
- Added dish type filtering
- Added more spice blends and condiments

## v1.0.0

- Initial release
- 81 ingredients, 52 compounds
- Pairing Explorer, Flavor Graph, Recipe Generator, Bridge Finder
- 18 dish templates
