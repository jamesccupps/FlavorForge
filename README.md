# ⚗ FlavorForge

**A procedural cooking engine that generates novel recipes using molecular flavor science, texture pairing, and taste balance analysis — with optional AI Chef integration.**

FlavorForge doesn't just mash random ingredients together. It uses a database of 297 real ingredients mapped to 84 aroma compounds (linalool, furaneol, methylpyrazine, etc.) to find scientifically-grounded flavor pairings. Then it layers on texture contrast analysis and taste balance checking to make sure the dish actually works.

Send the result to your local Ollama instance or Claude API, and the AI gets a prompt loaded with molecular pairing data, texture gaps, taste balance issues, and cuisine direction — so it generates a recipe that's both creative and cookable.

---

## Features

### 🧪 Pairing Explorer
Select any ingredient and see its top 25 molecular pairings ranked by shared aroma compound rarity. Discover that strawberry and tomato share 5 compounds, or that coffee and chocolate are connected through 6 different molecules.

### 🕸 Flavor Graph
Interactive network visualization of the entire ingredient database. Nodes are ingredients, edges are shared compounds. Adjust the similarity threshold, filter by category, click nodes to inspect.

### 🎲 Recipe Generator
Generate random recipe concepts filtered by dish type (Pizza, Pasta, Soup, Curry, etc.). Each recipe shows:
- What every ingredient is and why it's there
- Molecular connections between ingredients
- Texture and taste balance analysis with suggestions
- Novelty score

### 🍕 Build a Dish
Choose a dish type → pick a template → fill in each slot with guided suggestions. The system recommends ingredients based on:
- **Molecular pairing** — shared aroma compounds
- **Texture gaps** — "missing crunch, try nuts or breadcrumbs"
- **Taste balance** — "no acid, consider lemon or vinegar"

Includes 24 noodle/pasta types, 9 breads, 7 rices, 8 broths, 16 cooking sauces, and 21 dressings.

### 🌉 Bridge Finder
Pick two ingredients that seem incompatible (chocolate + salmon) and find a third ingredient that shares compounds with both — bridging the gap.

### 🧊 My Pantry
Check off what's in your fridge/cupboard. Hit "What Can I Make?" to find recipes using only your ingredients. "Almost There" shows recipes where you're one ingredient short — your smart shopping list.

Pantry persists between sessions.

### 🤖 AI Chef
Send any generated recipe to Ollama or Claude API. The prompt includes:
- Ingredient profiles with texture tags and taste percentages
- Molecular pairing explanations
- Contrast pairing suggestions
- Texture/taste balance warnings with fix suggestions
- Cuisine direction and dietary flags
- Structured output format

Save AI-generated recipes as text files to `~/FlavorForge_Recipes/`.

---

## Screenshot

![FlavorForge main window](docs/screenshots/main-window.png)

## The Database

297 ingredients across 17 categories, 84 aroma compounds, 1,632 flavor links.

| Category | Count | Examples |
|---|---|---|
| Grains & Starches | 48 | 24 noodles/pastas, 9 breads, 7 rices, plus quinoa / polenta / farro / couscous |
| Vegetables | 42 | tomato, beet, fennel, bok choy, artichoke |
| Spices | 36 | garam masala, za'atar, Old Bay, five spice |
| Dairy & Cheese | 26 | gruyere, cotija, labneh, mascarpone |
| Fermented | 25 | miso, gochujang, kimchi, balsamic |
| Sauces | 24 | marinara, alfredo, curry paste, chimichurri |
| Fruits | 19 | strawberry, fig, passion fruit, lychee |
| Nuts & Seeds | 14 | tahini, macadamia, peanut butter |
| Proteins | 13 | chicken, beef, duck, tofu, tempeh |
| Herbs | 12 | basil, tarragon, lemongrass, sage |
| Seafood | 9 | salmon, shrimp, scallop, lobster, anchovy |
| Mushrooms | 7 | chanterelle, morel, shiitake, truffle |
| Legumes | 5 | lentils, chickpeas, black beans |
| Sweeteners | 5 | honey, maple syrup, molasses |
| Alliums | 5 | garlic, onion, shallot, leek, scallion |
| Citrus | 4 | lemon, lime, orange, yuzu |
| Oils & Fats | 3 | olive oil, butter, sesame oil |

### 102 Recipe Templates across 16 Dish Types
One-Pot, Pasta & Noodles, Stir-Fry & Wok, Curry & Stew, Tacos & Wraps, Bowl, Soup (13 templates including chowders, ramen, pho, tom yum, gazpacho), Casserole & Bake (including mac & cheese), Grilled & Seared (including fried chicken), Salad & Slaw (including ceviche), Breakfast & Brunch, Sandwich (including burgers), Pizza & Flatbread, Dessert & Sweet, Snack & Appetizer (including wings, nachos, dumplings, empanadas, loaded fries), Sauce & Dip.

---

## Installation

### Requirements
- **Python 3.8+**
- **tkinter** (included with Python on most systems)
- No pip packages required — 100% standard library

### Quick Start
```bash
git clone https://github.com/jamesccupps/FlavorForge.git
cd FlavorForge
python flavorforge.py
```

### Windows
Download and double-click `flavorforge.py`, or:
```powershell
python flavorforge.py
```

### Linux
tkinter may need to be installed separately:
```bash
# Ubuntu/Debian
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

python3 flavorforge.py
```

### macOS
```bash
python3 flavorforge.py
```

---

## AI Chef Setup

FlavorForge works standalone — the AI Chef tab is optional.

### Ollama (Local, Free)
1. Install [Ollama](https://ollama.ai)
2. Pull a model: `ollama pull qwen2.5:14b` (or llama3, mistral, etc.)
3. In FlavorForge → AI Chef tab → set URL to `http://localhost:11434` and model name
4. Hit "Test" → "Save"

### Claude API (Anthropic)
1. Get an API key from [console.anthropic.com](https://console.anthropic.com)
2. In FlavorForge → AI Chef tab → switch provider to "anthropic"
3. Paste your API key
4. Hit "Save"

---

## How It Works

### Molecular Flavor Pairing
Each ingredient is mapped to its key volatile aroma compounds. When two ingredients share compounds — especially rare ones — they harmonize on a molecular level. FlavorForge uses a **rarity-weighted Jaccard similarity** score: sharing a common compound like hexanal (appears in 60%+ of ingredients) scores low, while sharing gamma-decalactone (peach, coconut — appears in <5%) scores high.

### Texture Contrast
Every ingredient has texture tags (crispy, creamy, chewy, tender, etc.). The balance system checks for missing texture dimensions and suggests fixes: "Missing crunch — try adding nuts, seeds, or crispy onions."

### Taste Balance
Ingredients carry taste profiles across 7 dimensions: salty, sweet, sour, bitter, umami, fatty, spicy. The system identifies gaps: "Heavy on salt but missing acid — add citrus, vinegar, or pickled element."

### Smart Slot Types
Templates use specialized slot types that filter to the right ingredients:
- `noodle` → 24 pasta/noodle options (spaghetti, udon, rice noodles, gnocchi...)
- `bread` → 9 bread options (sourdough, ciabatta, naan, pita...)
- `rice_type` → 7 rice options (jasmine, basmati, arborio, sticky...)
- `broth` → 8 stock/broth options (dashi, bone broth, coconut broth...)
- `cooking_sauce` → 16 sauces (marinara, pesto, alfredo, curry paste...)
- `dressing` → 21 condiment dressings (gochujang, harissa, miso...)

---

## Data Files

FlavorForge saves user data to your home directory:

| File | Purpose |
|---|---|
| `~/.flavorforge_config.json` | AI Chef settings (provider, URL, model) |
| `~/.flavorforge_pantry.json` | Your pantry ingredient list |
| `~/.flavorforge_saved_recipes.json` | Saved recipe concepts |
| `~/FlavorForge_Recipes/` | AI-generated full recipe text files |

---

## Project Stats

- **4,874 lines** of Python
- **297 ingredients** across 17 categories
- **84 aroma compounds** with descriptions
- **1,632 flavor links**
- **102 recipe templates** across 16 dish types
- **24 slot types** including grain, sauce, and broth subtypes
- **7 tabs**: Pairing Explorer, Flavor Graph, Recipe Generator, Build a Dish, Bridge Finder, My Pantry, AI Chef
- **Zero external dependencies** — pure Python stdlib + tkinter

---

## License

MIT License — see [LICENSE](LICENSE).

---

## Credits

Flavor compound data is based on research from:
- **FlavorDB** — Indian Institute of Technology
- **Ahn et al. (2011)** — "Flavor network and the principles of food pairing" (Scientific Reports)
- **Foodpairing.com** methodology

Built by [James Cupps]
