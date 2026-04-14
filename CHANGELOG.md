# Changelog

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
