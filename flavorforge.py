#!/usr/bin/env python3
"""
FlavorForge - Procedural Cooking Engine v3.1
Generates novel recipes based on molecular flavor compound pairing theory.
Uses real aroma compound data to find scientifically-grounded ingredient combinations.
303 ingredients, 82 compounds, 102 templates across 16 dish types.
AI Chef integration (Ollama / Claude API) for full recipe generation.

Author: James Cupps
Version: 3.1.0
"""

import ctypes
import sys

# ── Fix fuzzy rendering on Windows high-DPI displays ──
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # System DPI aware
        except Exception:
            pass

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    HAVE_TK = True
except ImportError:                       # headless box, or no python3-tk
    tk = ttk = messagebox = scrolledtext = None
    HAVE_TK = False

import argparse
import math
import random
import json
import threading
import urllib.request
import urllib.error
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

# ═══════════════════════════════════════════════════════════════════
# FLAVOR COMPOUND DATABASE
# Based on real aroma chemistry data (FlavorDB, Ahn et al. 2011)
# Compounds are key volatile/aroma molecules that define flavor
# ═══════════════════════════════════════════════════════════════════

__version__ = "3.1.0"

COMPOUND_CATEGORIES = {
    "terpene": "#4CAF50",
    "aldehyde": "#FF9800",
    "ester": "#2196F3",
    "ketone": "#9C27B0",
    "phenol": "#F44336",
    "sulfur": "#FFEB3B",
    "acid": "#00BCD4",
    "alcohol": "#E91E63",
    "lactone": "#8BC34A",
    "pyrazine": "#795548",
    "pyrroline": "#6D4C41",
    "furanone": "#FF5722",
    "thiazole": "#607D8B",
    "amine": "#CDDC39",
    "other": "#78909C",
}

@dataclass
class Compound:
    name: str
    category: str
    description: str

COMPOUNDS = {
    # ── Terpenes ──
    "linalool": Compound("linalool", "terpene", "floral, lavender, citrus"),
    "limonene": Compound("limonene", "terpene", "citrus, orange peel"),
    "myrcene": Compound("myrcene", "terpene", "earthy, musky, herbal"),
    "pinene": Compound("pinene", "terpene", "pine, resinous, fresh"),
    "geraniol": Compound("geraniol", "terpene", "rose, geranium, sweet"),
    "carvone": Compound("carvone", "terpene", "spearmint, caraway"),
    "eucalyptol": Compound("eucalyptol", "terpene", "eucalyptus, cooling, camphor"),
    "ocimene": Compound("ocimene", "terpene", "sweet, herbal, woody"),
    "terpinene": Compound("terpinene", "terpene", "herbal, citrus, woody"),
    "sabinene": Compound("sabinene", "terpene", "woody, spicy, citrus"),
    # ── Phenols ──
    "eugenol": Compound("eugenol", "phenol", "clove, warm, spicy"),
    "thymol": Compound("thymol", "phenol", "thyme, medicinal, herbal"),
    "guaiacol": Compound("guaiacol", "phenol", "smoky, woody, bacon"),
    "4vg": Compound("4-vinylguaiacol", "phenol", "clove, smoky, spicy"),
    "cresol": Compound("cresol", "phenol", "smoky, tarry, medicinal"),
    "anethole": Compound("anethole", "phenol", "anise, licorice, sweet"),
    "estragole": Compound("estragole", "phenol", "tarragon, anise, sweet"),
    "chavicol": Compound("chavicol", "phenol", "basil, spicy, warm"),
    # ── Aldehydes ──
    "cinnamaldehyde": Compound("cinnamaldehyde", "aldehyde", "cinnamon, warm, sweet"),
    "vanillin": Compound("vanillin", "aldehyde", "vanilla, sweet, creamy"),
    "benzaldehyde": Compound("benzaldehyde", "aldehyde", "almond, cherry, marzipan"),
    "hexanal": Compound("hexanal", "aldehyde", "green, grassy, fresh-cut"),
    "nonanal": Compound("nonanal", "aldehyde", "waxy, citrus, fatty"),
    "octanal": Compound("octanal", "aldehyde", "citrus, green, fatty"),
    "decanal": Compound("decanal", "aldehyde", "orange peel, waxy"),
    "citral": Compound("citral", "aldehyde", "lemon, citrus, fresh"),
    "furfural": Compound("furfural", "aldehyde", "almond, bread, caramel"),
    "methional": Compound("methional", "aldehyde", "potato, cooked, brothy"),
    "phenylacetaldehyde": Compound("phenylacetaldehyde", "aldehyde", "honey, floral, hyacinth"),
    "cuminaldehyde": Compound("cuminaldehyde", "aldehyde", "cumin, warm, green"),
    "trans_2_nonenal": Compound("trans-2-nonenal", "aldehyde", "cucumber, fatty, green"),
    # ── Esters ──
    "ethyl_butyrate": Compound("ethyl butyrate", "ester", "pineapple, fruity"),
    "ethyl_acetate": Compound("ethyl acetate", "ester", "fruity, solvent-like"),
    "isoamyl_acetate": Compound("isoamyl acetate", "ester", "banana, pear"),
    "methyl_anthranilate": Compound("methyl anthranilate", "ester", "grape, concord"),
    "ethyl_hexanoate": Compound("ethyl hexanoate", "ester", "apple, fruity, wine"),
    "ethyl_cinnamate": Compound("ethyl cinnamate", "ester", "cinnamon, balsamic, fruity"),
    # ── Ketones ──
    "diacetyl": Compound("diacetyl", "ketone", "buttery, creamy"),
    "acetoin": Compound("acetoin", "ketone", "buttery, yogurt"),
    "ionone": Compound("ionone", "ketone", "violet, floral, berry"),
    "damascenone": Compound("damascenone", "ketone", "rose, honey, cooked apple"),
    "nootkatone": Compound("nootkatone", "ketone", "grapefruit, citrus"),
    "acetophenone": Compound("acetophenone", "ketone", "floral, almond, cherry"),
    "zingerone": Compound("zingerone", "ketone", "ginger, sweet, spicy"),
    "menthone": Compound("menthone", "ketone", "minty, slightly woody"),
    # ── Sulfur compounds ──
    "allicin": Compound("allicin", "sulfur", "garlic, pungent"),
    "diallyl_disulfide": Compound("diallyl disulfide", "sulfur", "garlic, cooked onion"),
    "dimethyl_sulfide": Compound("dimethyl sulfide", "sulfur", "cabbage, truffle, corn"),
    "thiophene": Compound("thiophene", "sulfur", "roasted, meaty"),
    "allyl_isothiocyanate": Compound("allyl isothiocyanate", "sulfur", "mustard, wasabi, horseradish"),
    "dimethyl_trisulfide": Compound("dimethyl trisulfide", "sulfur", "cooked cabbage, savory, umami"),
    "methyl_thioacetate": Compound("methyl thioacetate", "sulfur", "cheesy, sulfurous, fermented"),
    # ── Acids ──
    "acetic_acid": Compound("acetic acid", "acid", "vinegar, sharp, sour"),
    "citric_acid": Compound("citric acid", "acid", "sour, citrus"),
    "malic_acid": Compound("malic acid", "acid", "tart apple, sour"),
    "lactic_acid": Compound("lactic acid", "acid", "sour milk, tangy"),
    "tartaric_acid": Compound("tartaric acid", "acid", "grape, wine, tart"),
    "butyric_acid": Compound("butyric acid", "acid", "cheesy, rancid, sharp"),
    # ── Pyrazines ──
    "methoxypyrazine": Compound("methoxypyrazine", "pyrazine", "green bell pepper, earthy"),
    "methylpyrazine": Compound("methylpyrazine", "pyrazine", "roasted, nutty, cocoa"),
    "acetylpyrazine": Compound("acetylpyrazine", "pyrazine", "popcorn, roasted, bread crust"),
    # A pyrroline, not a pyrazine: five-membered ring with one nitrogen,
    # against six with two. Filed under pyrazine it was the wrong class of
    # molecule in a database whose selling point is the chemistry.
    "acetyl_pyrroline": Compound("2-acetyl-1-pyrroline", "pyrroline", "basmati rice, popcorn, pandan"),
    # ── Furanones ──
    "furaneol": Compound("furaneol", "furanone", "strawberry, caramel, sweet"),
    "sotolon": Compound("sotolon", "furanone", "maple, curry, fenugreek"),
    "maltol": Compound("maltol", "furanone", "caramel, cotton candy, toasty"),
    "ethyl_maltol": Compound("ethyl maltol", "furanone", "cotton candy, caramelized sugar"),
    # ── Lactones ──
    "gamma_decalactone": Compound("gamma-decalactone", "lactone", "peach, creamy, coconut"),
    "gamma_octalactone": Compound("gamma-octalactone", "lactone", "coconut, creamy"),
    "whiskey_lactone": Compound("whiskey lactone", "lactone", "coconut, woody, oaky"),
    "delta_decalactone": Compound("delta-decalactone", "lactone", "creamy, milky, peach"),
    # ── Alcohols ──
    "1_octen_3_ol": Compound("1-octen-3-ol", "alcohol", "mushroom, earthy, damp"),
    "phenethyl_alcohol": Compound("phenethyl alcohol", "alcohol", "rose, honey, floral"),
    "geosmin": Compound("geosmin", "alcohol", "earthy, beet, petrichor"),
    "menthol": Compound("menthol", "alcohol", "cooling, minty"),
    "linalool_oxide": Compound("linalool oxide", "alcohol", "floral, woody, earthy"),
    # ── Thiazoles ──
    "thiazole": Compound("thiazole", "thiazole", "meaty, roasted, nutty"),
    # ── Amines ──
    "trimethylamine": Compound("trimethylamine", "amine", "fishy, marine, briny"),
    "indole": Compound("indole", "amine", "floral, jasmine (low conc), fecal (high)"),
    # ── Other ──
    "capsaicin": Compound("capsaicin", "other", "hot, burning, chili heat"),
    "piperine": Compound("piperine", "other", "sharp, biting, pepper heat"),
    "coumarin": Compound("coumarin", "other", "hay, vanilla, tonka bean"),
    "rotundone": Compound("rotundone", "other", "black pepper, spicy, woody"),
}

# ═══════════════════════════════════════════════════════════════════
# INGREDIENT DATABASE
# Counts are asserted against the data in tests/test_data_integrity.py,
# so a stale number here is a red build rather than a wrong README.
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Ingredient:
    name: str
    category: str
    compounds: Set[str]
    cooking_methods: List[str]
    flavor_notes: str

CATEGORIES = {
    "protein": "#e74c3c",
    "vegetable": "#27ae60",
    "fruit": "#f39c12",
    "herb": "#2ecc71",
    "spice": "#e67e22",
    "dairy": "#f1c40f",
    "grain": "#d4a574",
    "nut": "#a0522d",
    "oil/fat": "#daa520",
    "fermented": "#8e44ad",
    "seafood": "#3498db",
    "mushroom": "#7f8c8d",
    "allium": "#c0392b",
    "citrus": "#f9a825",
    "sweetener": "#ffb6c1",
    "legume": "#6d9b3a",
    "sauce": "#d35400",
}

INGREDIENTS = {
    # ═══════════════ PROTEINS ═══════════════
    "chicken": Ingredient("chicken", "protein",
        {"hexanal", "nonanal", "thiophene", "diacetyl", "methylpyrazine", "octanal", "methional"},
        ["roast", "grill", "braise", "poach", "fry"], "mild, savory, versatile"),
    "beef": Ingredient("beef", "protein",
        {"hexanal", "thiophene", "methylpyrazine", "guaiacol", "nonanal", "4vg", "diacetyl", "methional"},
        ["grill", "braise", "roast", "sear", "smoke"], "rich, umami, meaty"),
    "pork": Ingredient("pork", "protein",
        {"hexanal", "nonanal", "octanal", "methylpyrazine", "diacetyl", "thiophene", "methional"},
        ["roast", "braise", "grill", "smoke", "fry"], "mild, sweet, fatty"),
    "lamb": Ingredient("lamb", "protein",
        {"methylpyrazine", "4vg", "thiophene", "hexanal", "cresol", "nonanal", "methional"},
        ["roast", "grill", "braise", "stew"], "gamey, rich, earthy"),
    "duck": Ingredient("duck", "protein",
        {"hexanal", "nonanal", "thiophene", "methylpyrazine", "diacetyl", "octanal", "gamma_decalactone"},
        ["roast", "confit", "sear", "smoke", "braise"], "rich, fatty, dark meat"),
    "turkey": Ingredient("turkey", "protein",
        {"hexanal", "nonanal", "methylpyrazine", "thiophene", "diacetyl", "methional"},
        ["roast", "smoke", "braise", "grill", "ground"], "mild, lean, savory"),
    "bacon": Ingredient("bacon", "protein",
        {"guaiacol", "4vg", "methylpyrazine", "thiophene", "hexanal", "nonanal", "cresol", "diacetyl"},
        ["fry", "bake", "smoke", "crumble"], "smoky, salty, fatty, umami"),
    "tofu": Ingredient("tofu", "protein",
        {"hexanal", "nonanal", "1_octen_3_ol", "acetoin"},
        ["fry", "braise", "grill", "scramble", "steam", "smoke"], "mild, neutral, absorbs flavor"),
    "tempeh": Ingredient("tempeh", "protein",
        {"hexanal", "nonanal", "1_octen_3_ol", "methylpyrazine", "acetoin"},
        ["fry", "grill", "crumble", "braise", "steam"], "nutty, earthy, fermented"),
    "egg": Ingredient("egg", "protein",
        {"dimethyl_sulfide", "diacetyl", "nonanal", "hexanal", "thiophene", "methional"},
        ["fry", "scramble", "poach", "boil", "bake"], "rich, sulfurous, custard"),

    # ═══════════════ SEAFOOD ═══════════════
    "salmon": Ingredient("salmon", "seafood",
        {"hexanal", "nonanal", "diacetyl", "dimethyl_sulfide", "1_octen_3_ol", "trimethylamine"},
        ["grill", "bake", "poach", "cure", "smoke"], "rich, fatty, ocean"),
    "shrimp": Ingredient("shrimp", "seafood",
        {"dimethyl_sulfide", "methylpyrazine", "thiazole", "nonanal", "acetylpyrazine", "trimethylamine"},
        ["sauté", "grill", "boil", "fry"], "sweet, briny, delicate"),
    "scallop": Ingredient("scallop", "seafood",
        {"dimethyl_sulfide", "nonanal", "diacetyl", "methional", "trimethylamine"},
        ["sear", "raw", "poach", "grill"], "sweet, buttery, delicate"),
    "crab": Ingredient("crab", "seafood",
        {"dimethyl_sulfide", "trimethylamine", "methylpyrazine", "nonanal", "thiazole", "methional"},
        ["boil", "steam", "sauté", "bake"], "sweet, briny, rich"),
    "tuna": Ingredient("tuna", "seafood",
        {"hexanal", "nonanal", "trimethylamine", "dimethyl_sulfide", "thiophene"},
        ["sear", "raw", "grill", "can"], "meaty, clean, ocean"),
    "anchovy": Ingredient("anchovy", "seafood",
        {"trimethylamine", "methylpyrazine", "dimethyl_sulfide", "butyric_acid", "methional"},
        ["cure", "melt", "sauce", "paste"], "intense, salty, umami bomb"),
    "lobster": Ingredient("lobster", "seafood",
        {"dimethyl_sulfide", "trimethylamine", "nonanal", "methional", "diacetyl", "hexanal"},
        ["boil", "steam", "grill", "bake"], "sweet, rich, buttery"),
    "oyster": Ingredient("oyster", "seafood",
        {"dimethyl_sulfide", "trimethylamine", "nonanal", "1_octen_3_ol", "methional", "hexanal"},
        ["raw", "grill", "fry", "roast"], "briny, mineral, oceanic, zinc"),
    "mussels": Ingredient("mussels", "seafood",
        {"dimethyl_sulfide", "trimethylamine", "nonanal", "hexanal", "dimethyl_trisulfide"},
        ["steam", "braise", "grill", "fry"], "briny, sweet, plump"),

    # ═══════════════ VEGETABLES ═══════════════
    "tomato": Ingredient("tomato", "vegetable",
        {"hexanal", "citral", "geraniol", "furaneol", "ionone", "dimethyl_sulfide", "linalool"},
        ["raw", "roast", "stew", "sauce", "grill"], "acidic, sweet, umami"),
    "carrot": Ingredient("carrot", "vegetable",
        {"myrcene", "pinene", "limonene", "linalool", "ionone", "nonanal", "terpinene"},
        ["roast", "raw", "braise", "purée", "pickle"], "sweet, earthy, bright"),
    "bell_pepper": Ingredient("bell pepper", "vegetable",
        {"methoxypyrazine", "linalool", "hexanal", "nonanal", "limonene"},
        ["raw", "roast", "sauté", "stuff", "grill"], "sweet, vegetal, crisp"),
    "broccoli": Ingredient("broccoli", "vegetable",
        {"dimethyl_sulfide", "allyl_isothiocyanate", "hexanal", "nonanal", "linalool", "dimethyl_trisulfide"},
        ["steam", "roast", "sauté", "raw", "stir-fry"], "cruciferous, green, earthy"),
    "sweet_potato": Ingredient("sweet potato", "vegetable",
        {"maltol", "furaneol", "linalool", "ionone", "nonanal", "phenethyl_alcohol"},
        ["roast", "bake", "fry", "purée", "mash"], "sweet, starchy, caramel"),
    "beet": Ingredient("beet", "vegetable",
        {"geosmin", "linalool", "dimethyl_sulfide", "nonanal", "malic_acid"},
        ["roast", "raw", "pickle", "purée", "boil"], "earthy, sweet, mineral"),
    "corn": Ingredient("corn", "vegetable",
        {"dimethyl_sulfide", "acetylpyrazine", "furaneol", "hexanal", "maltol", "acetyl_pyrroline"},
        ["grill", "boil", "roast", "cream", "pop"], "sweet, starchy, toasty"),
    "celery": Ingredient("celery", "vegetable",
        {"myrcene", "limonene", "pinene", "hexanal", "linalool", "sabinene"},
        ["raw", "braise", "sauté", "stock"], "green, aromatic, fresh"),
    "cauliflower": Ingredient("cauliflower", "vegetable",
        {"dimethyl_sulfide", "allyl_isothiocyanate", "methylpyrazine", "nonanal", "dimethyl_trisulfide"},
        ["roast", "purée", "fry", "steam", "rice"], "mild, nutty when roasted"),
    "asparagus": Ingredient("asparagus", "vegetable",
        {"dimethyl_sulfide", "hexanal", "methoxypyrazine", "nonanal", "linalool"},
        ["roast", "grill", "steam", "sauté"], "green, grassy, mineral"),
    "eggplant": Ingredient("eggplant", "vegetable",
        {"hexanal", "nonanal", "linalool", "1_octen_3_ol", "furfural"},
        ["grill", "roast", "fry", "braise", "smoke"], "meaty, absorbent, smoky"),
    "zucchini": Ingredient("zucchini", "vegetable",
        {"hexanal", "nonanal", "trans_2_nonenal", "linalool"},
        ["grill", "sauté", "raw", "spiralize", "bake"], "mild, fresh, squash"),
    "spinach": Ingredient("spinach", "vegetable",
        {"hexanal", "dimethyl_sulfide", "linalool", "nonanal", "geraniol"},
        ["raw", "sauté", "wilt", "cream", "blend"], "earthy, iron, green"),
    "kale": Ingredient("kale", "vegetable",
        {"hexanal", "dimethyl_sulfide", "allyl_isothiocyanate", "nonanal", "linalool"},
        ["raw", "sauté", "chip", "braise", "blend"], "bitter, earthy, hearty"),
    "fennel": Ingredient("fennel", "vegetable",
        {"anethole", "limonene", "pinene", "myrcene", "linalool", "estragole"},
        ["raw", "roast", "braise", "grill", "shave"], "anise, sweet, crisp"),
    "radish": Ingredient("radish", "vegetable",
        {"allyl_isothiocyanate", "hexanal", "nonanal", "methoxypyrazine"},
        ["raw", "roast", "pickle", "sauté"], "peppery, crisp, bright"),
    "cabbage": Ingredient("cabbage", "vegetable",
        {"dimethyl_sulfide", "allyl_isothiocyanate", "hexanal", "nonanal", "dimethyl_trisulfide"},
        ["raw", "braise", "ferment", "sauté", "roast"], "cruciferous, sweet, crunchy"),
    "peas": Ingredient("peas", "legume",
        {"hexanal", "dimethyl_sulfide", "methoxypyrazine", "linalool", "nonanal", "acetoin"},
        ["raw", "boil", "purée", "sauté"], "sweet, green, bright"),
    "brussels_sprouts": Ingredient("Brussels sprouts", "vegetable",
        {"dimethyl_sulfide", "allyl_isothiocyanate", "methylpyrazine", "hexanal", "dimethyl_trisulfide"},
        ["roast", "shred", "fry", "braise", "char"], "nutty, bitter, caramelized"),
    "artichoke": Ingredient("artichoke", "vegetable",
        {"hexanal", "linalool", "nonanal", "phenylacetaldehyde", "furfural"},
        ["steam", "braise", "grill", "fry", "roast"], "nutty, earthy, mineral"),
    "parsnip": Ingredient("parsnip", "vegetable",
        {"myrcene", "pinene", "nonanal", "furfural", "maltol", "terpinene"},
        ["roast", "purée", "fry", "braise"], "sweet, nutty, starchy"),
    "turnip": Ingredient("turnip", "vegetable",
        {"allyl_isothiocyanate", "dimethyl_sulfide", "hexanal", "nonanal"},
        ["roast", "mash", "braise", "raw"], "peppery, mild, slightly bitter"),
    "cucumber": Ingredient("cucumber", "vegetable",
        {"trans_2_nonenal", "hexanal", "nonanal", "linalool"},
        ["raw", "pickle", "blend", "compress"], "cool, green, fresh, watery"),
    "avocado": Ingredient("avocado", "vegetable",
        {"hexanal", "nonanal", "ethyl_acetate", "linalool", "acetoin"},
        ["raw", "smash", "blend", "grill"], "creamy, mild, fatty, green"),

    # ═══════════════ FRUITS ═══════════════
    "strawberry": Ingredient("strawberry", "fruit",
        {"furaneol", "linalool", "ethyl_butyrate", "hexanal", "gamma_decalactone", "ionone", "geraniol"},
        ["raw", "macerate", "bake", "purée", "jam"], "sweet, fragrant, bright"),
    "apple": Ingredient("apple", "fruit",
        {"ethyl_butyrate", "hexanal", "ethyl_acetate", "damascenone", "linalool", "malic_acid", "ethyl_hexanoate"},
        ["raw", "bake", "sauce", "cider", "poach"], "crisp, tart, sweet"),
    "banana": Ingredient("banana", "fruit",
        {"isoamyl_acetate", "eugenol", "linalool", "vanillin", "ethyl_butyrate"},
        ["raw", "bake", "fry", "flambe", "freeze"], "sweet, creamy, tropical"),
    "lemon": Ingredient("lemon", "citrus",
        {"citral", "limonene", "linalool", "pinene", "geraniol", "citric_acid", "nonanal"},
        ["juice", "zest", "preserve", "garnish"], "bright, sour, clean"),
    "orange": Ingredient("orange", "citrus",
        {"limonene", "linalool", "decanal", "citral", "octanal", "myrcene", "citric_acid", "nootkatone"},
        ["juice", "zest", "segment", "marmalade"], "sweet, citrus, bright"),
    "grapefruit": Ingredient("grapefruit", "citrus",
        {"nootkatone", "limonene", "linalool", "citral", "myrcene", "pinene"},
        ["juice", "segment", "broil", "zest"], "bitter, citrus, tart"),
    "lime": Ingredient("lime", "citrus",
        {"citral", "limonene", "linalool", "pinene", "terpinene", "citric_acid"},
        ["juice", "zest", "garnish", "pickle"], "tart, bright, tropical"),
    "peach": Ingredient("peach", "fruit",
        {"gamma_decalactone", "linalool", "ionone", "benzaldehyde", "hexanal", "furaneol", "delta_decalactone"},
        ["raw", "grill", "poach", "bake", "jam"], "sweet, floral, juicy"),
    "mango": Ingredient("mango", "fruit",
        {"myrcene", "limonene", "ethyl_butyrate", "linalool", "furaneol", "gamma_octalactone"},
        ["raw", "purée", "pickle", "dry", "salsa"], "tropical, sweet, resinous"),
    "pineapple": Ingredient("pineapple", "fruit",
        {"ethyl_butyrate", "ethyl_hexanoate", "furaneol", "vanillin", "linalool"},
        ["raw", "grill", "juice", "bake"], "tropical, tart, enzymatic"),
    "raspberry": Ingredient("raspberry", "fruit",
        {"ionone", "linalool", "geraniol", "furaneol", "hexanal", "damascenone"},
        ["raw", "purée", "bake", "jam", "sauce"], "tart, fragrant, intense"),
    "coconut": Ingredient("coconut", "fruit",
        {"gamma_octalactone", "gamma_decalactone", "vanillin", "nonanal", "maltol", "delta_decalactone"},
        ["raw", "toast", "milk", "cream", "bake"], "sweet, creamy, tropical"),
    "grape": Ingredient("grape", "fruit",
        {"methyl_anthranilate", "linalool", "geraniol", "hexanal", "ethyl_acetate", "rotundone"},
        ["raw", "juice", "wine", "roast", "jam"], "sweet, floral, wine-like"),
    "fig": Ingredient("fig", "fruit",
        {"benzaldehyde", "linalool", "furaneol", "hexanal", "phenethyl_alcohol", "eugenol"},
        ["raw", "roast", "jam", "dry", "grill"], "honey, jammy, seedy, complex"),
    "date": Ingredient("date", "fruit",
        {"maltol", "furaneol", "vanillin", "furfural", "acetoin", "linalool"},
        ["raw", "stuff", "purée", "bake", "caramel"], "intensely sweet, caramel, chewy"),
    "pomegranate": Ingredient("pomegranate", "fruit",
        {"linalool", "hexanal", "geraniol", "citric_acid", "malic_acid", "ethyl_acetate"},
        ["raw", "juice", "reduce", "garnish"], "tart, fruity, complex, jewel-like"),
    "cherry": Ingredient("cherry", "fruit",
        {"benzaldehyde", "linalool", "eugenol", "hexanal", "ethyl_acetate", "malic_acid",
         "acetophenone"},
        ["raw", "bake", "jam", "poach", "dry"], "sweet-tart, almond, rich"),
    "passion_fruit": Ingredient("passion fruit", "fruit",
        {"ethyl_butyrate", "linalool", "hexanal", "ethyl_hexanoate", "ionone", "geraniol"},
        ["raw", "purée", "sauce", "curd"], "intensely tart, tropical, floral"),
    "blackberry": Ingredient("blackberry", "fruit",
        {"ionone", "linalool", "hexanal", "furaneol", "geraniol", "damascenone"},
        ["raw", "bake", "jam", "sauce", "muddle"], "sweet-tart, dark, earthy"),
    "apricot": Ingredient("apricot", "fruit",
        {"gamma_decalactone", "linalool", "benzaldehyde", "hexanal", "ionone", "myrcene"},
        ["raw", "dry", "jam", "poach", "grill"], "sweet, slightly tart, stone fruit"),
    "watermelon": Ingredient("watermelon", "fruit",
        {"trans_2_nonenal", "hexanal", "nonanal", "linalool", "geraniol"},
        ["raw", "juice", "grill", "pickle rind"], "refreshing, light, sweet"),
    "guava": Ingredient("guava", "fruit",
        {"ethyl_butyrate", "myrcene", "limonene", "linalool", "hexanal", "ethyl_hexanoate"},
        ["raw", "purée", "jam", "juice", "paste"], "tropical, musky, sweet-tart"),
    "lychee": Ingredient("lychee", "fruit",
        {"geraniol", "linalool", "citral", "phenethyl_alcohol", "damascenone"},
        ["raw", "syrup", "sorbet", "cocktail"], "floral, perfumed, sweet, rose"),

    # ═══════════════ HERBS ═══════════════
    "basil": Ingredient("basil", "herb",
        {"linalool", "eugenol", "myrcene", "pinene", "geraniol", "limonene", "estragole",
         "chavicol"},
        ["raw", "chiffonade", "infuse", "pesto"], "sweet, peppery, anise"),
    "cilantro": Ingredient("cilantro", "herb",
        {"linalool", "decanal", "geraniol", "pinene", "citral"},
        ["raw", "garnish", "blend", "salsa"], "bright, citrus, polarizing"),
    "mint": Ingredient("mint", "herb",
        {"menthol", "limonene", "linalool", "pinene", "carvone", "myrcene", "menthone"},
        ["raw", "muddle", "infuse", "garnish"], "cooling, fresh, sweet"),
    "rosemary": Ingredient("rosemary", "herb",
        {"pinene", "linalool", "myrcene", "limonene", "eucalyptol", "carvone"},
        ["roast", "infuse", "grill", "bake"], "piney, resinous, woody"),
    "thyme": Ingredient("thyme", "herb",
        {"thymol", "linalool", "myrcene", "pinene", "limonene", "geraniol"},
        ["roast", "braise", "infuse", "sauté"], "earthy, minty, woody"),
    "oregano": Ingredient("oregano", "herb",
        {"thymol", "carvone", "linalool", "myrcene", "pinene", "4vg"},
        ["dry", "sauté", "infuse", "bake"], "pungent, warm, slightly bitter"),
    "tarragon": Ingredient("tarragon", "herb",
        {"estragole", "anethole", "linalool", "limonene", "ocimene", "eugenol"},
        ["raw", "infuse", "sauce", "vinegar"], "anise, sweet, elegant"),
    "sage": Ingredient("sage", "herb",
        {"pinene", "eucalyptol", "linalool", "myrcene", "thymol", "sabinene"},
        ["fry", "infuse", "roast", "brown butter"], "musty, warm, savory, earthy"),
    "dill": Ingredient("dill", "herb",
        {"carvone", "limonene", "linalool", "myrcene", "pinene"},
        ["raw", "garnish", "pickle", "sauce"], "feathery, fresh, anise-like"),
    "chives": Ingredient("chives", "herb",
        {"diallyl_disulfide", "dimethyl_sulfide", "linalool", "pinene"},
        ["raw", "garnish", "fold", "snip"], "mild onion, delicate, fresh"),
    "lemongrass": Ingredient("lemongrass", "herb",
        {"citral", "limonene", "myrcene", "linalool", "geraniol", "citric_acid"},
        ["bruise", "infuse", "mince", "paste"], "citrus, ginger-like, floral"),
    "parsley": Ingredient("parsley", "herb",
        {"myrcene", "pinene", "linalool", "limonene", "methoxypyrazine"},
        ["raw", "garnish", "blend", "chimichurri"], "clean, green, slightly peppery"),

    # ═══════════════ SPICES ═══════════════
    "cinnamon": Ingredient("cinnamon", "spice",
        {"cinnamaldehyde", "eugenol", "linalool", "pinene", "vanillin", "coumarin", "ethyl_cinnamate"},
        ["toast", "grind", "infuse", "bake"], "warm, sweet, woody"),
    "ginger": Ingredient("ginger", "spice",
        {"citral", "linalool", "myrcene", "geraniol", "pinene", "limonene", "zingerone"},
        ["grate", "slice", "juice", "candy", "infuse"], "spicy, bright, warm"),
    "cumin": Ingredient("cumin", "spice",
        {"cuminaldehyde", "methylpyrazine", "pinene", "limonene", "myrcene", "linalool"},
        ["toast", "grind", "bloom"], "earthy, warm, nutty"),
    "clove": Ingredient("clove", "spice",
        {"eugenol", "vanillin", "pinene", "linalool", "acetylpyrazine", "coumarin"},
        ["whole", "grind", "infuse", "stud"], "intense, warm, numbing"),
    "cardamom": Ingredient("cardamom", "spice",
        {"linalool", "limonene", "pinene", "myrcene", "geraniol", "citral", "eucalyptol", "sabinene"},
        ["crush", "grind", "infuse", "toast"], "floral, citrus, eucalyptus"),
    "black_pepper": Ingredient("black pepper", "spice",
        {"pinene", "limonene", "myrcene", "linalool", "carvone", "piperine", "rotundone", "sabinene"},
        ["crack", "grind", "toast"], "sharp, biting, warm"),
    "turmeric": Ingredient("turmeric", "spice",
        {"pinene", "myrcene", "linalool", "limonene", "citral", "terpinene"},
        ["grind", "bloom", "paste"], "earthy, bitter, warm"),
    "nutmeg": Ingredient("nutmeg", "spice",
        {"myrcene", "pinene", "linalool", "eugenol", "geraniol", "sabinene", "terpinene"},
        ["grate", "grind", "infuse"], "warm, sweet, woody"),
    "vanilla": Ingredient("vanilla", "spice",
        {"vanillin", "linalool", "eugenol", "maltol", "phenethyl_alcohol", "acetoin", "coumarin"},
        ["scrape", "infuse", "extract"], "sweet, creamy, floral"),
    "star_anise": Ingredient("star anise", "spice",
        {"anethole", "linalool", "pinene", "limonene", "eugenol", "myrcene", "estragole"},
        ["whole", "grind", "infuse"], "licorice, sweet, warm"),
    "coriander_seed": Ingredient("coriander seed", "spice",
        {"linalool", "pinene", "limonene", "geraniol", "myrcene", "citral"},
        ["toast", "grind", "crush"], "citrus, floral, nutty"),
    "fenugreek": Ingredient("fenugreek", "spice",
        {"sotolon", "linalool", "pinene", "myrcene"},
        ["toast", "grind", "sprout"], "maple, curry, bitter"),
    "saffron": Ingredient("saffron", "spice",
        {"pinene", "linalool", "geraniol", "ionone", "hexanal"},
        ["bloom", "infuse", "steep"], "honey, floral, metallic"),
    "mustard": Ingredient("mustard", "spice",
        {"allyl_isothiocyanate", "myrcene", "pinene", "acetic_acid"},
        ["grind", "mix", "bloom"], "sharp, hot, pungent"),
    "paprika": Ingredient("paprika", "spice",
        {"capsaicin", "methylpyrazine", "hexanal", "nonanal", "limonene", "linalool"},
        ["bloom", "dust", "rub", "smoke"], "sweet, mild heat, smoky"),
    "cayenne": Ingredient("cayenne", "spice",
        {"capsaicin", "limonene", "hexanal", "methylpyrazine"},
        ["grind", "dust", "bloom", "sauce"], "hot, sharp, clean heat"),
    "szechuan_pepper": Ingredient("Sichuan pepper", "spice",
        {"limonene", "linalool", "myrcene", "pinene", "geraniol", "sabinene", "terpinene"},
        ["toast", "grind", "infuse"], "numbing, citrus, floral, electric"),
    "allspice": Ingredient("allspice", "spice",
        {"eugenol", "myrcene", "pinene", "linalool", "limonene", "cinnamaldehyde"},
        ["grind", "whole", "infuse", "brine"], "clove, cinnamon, nutmeg, warm"),
    "sumac": Ingredient("sumac", "spice",
        {"citric_acid", "malic_acid", "limonene", "linalool", "geraniol"},
        ["dust", "garnish", "marinade"], "tart, citrusy, fruity"),
    "juniper": Ingredient("juniper", "spice",
        {"pinene", "myrcene", "limonene", "linalool", "sabinene", "terpinene"},
        ["crush", "infuse", "brine", "smoke"], "pine, resinous, gin-like, forest"),

    # ═══════════════ SEASONINGS & SPICE BLENDS ═══════════════
    "salt": Ingredient("salt", "spice",
        set(),  # No aroma compounds — enhances perception of others
        ["season", "brine", "cure", "finish"], "salty, enhances all flavors"),
    "msg": Ingredient("MSG", "spice",
        set(),  # Glutamate receptor, not volatile
        ["season", "dissolve"], "umami, savory depth, meaty"),
    "garlic_powder": Ingredient("garlic powder", "spice",
        {"allicin", "diallyl_disulfide", "methylpyrazine", "thiophene"},
        ["season", "rub", "dust", "mix"], "concentrated garlic, roasty"),
    "onion_powder": Ingredient("onion powder", "spice",
        {"diallyl_disulfide", "dimethyl_sulfide", "thiophene", "methylpyrazine", "hexanal"},
        ["season", "rub", "dust", "mix"], "sweet onion, concentrated"),
    "red_pepper_flakes": Ingredient("red pepper flakes", "spice",
        {"capsaicin", "limonene", "hexanal", "methylpyrazine", "piperine"},
        ["sprinkle", "bloom", "infuse"], "hot, fruity, smoky heat"),
    "chili_powder": Ingredient("chili powder", "spice",
        {"capsaicin", "cuminaldehyde", "methylpyrazine", "limonene", "pinene", "linalool"},
        ["rub", "bloom", "stew", "dust"], "warm, earthy, mild heat, complex"),
    "curry_powder": Ingredient("curry powder", "spice",
        {"linalool", "cuminaldehyde", "pinene", "myrcene", "limonene", "sotolon", "terpinene"},
        ["bloom", "simmer", "rub", "dust"], "warm, earthy, aromatic, complex"),
    "garam_masala": Ingredient("garam masala", "spice",
        {"eugenol", "cinnamaldehyde", "linalool", "pinene", "limonene", "piperine", "sabinene"},
        ["finish", "toast", "bloom"], "warm, sweet, aromatic, layered"),
    "five_spice": Ingredient("five spice", "spice",
        {"anethole", "cinnamaldehyde", "eugenol", "limonene", "pinene", "linalool"},
        ["rub", "dust", "bloom", "marinade"], "sweet, anise, warm, complex"),
    "zaatar": Ingredient("za'atar", "spice",
        {"thymol", "citric_acid", "malic_acid", "limonene", "linalool", "methylpyrazine"},
        ["sprinkle", "crust", "dip", "finish"], "herby, tangy, nutty, Middle Eastern"),
    "italian_seasoning": Ingredient("Italian seasoning", "spice",
        {"thymol", "linalool", "eugenol", "myrcene", "pinene", "limonene", "carvone"},
        ["sprinkle", "simmer", "rub", "bake"], "herby, warm, Mediterranean"),
    "old_bay": Ingredient("Old Bay", "spice",
        {"eugenol", "pinene", "allyl_isothiocyanate", "capsaicin", "limonene", "carvone"},
        ["season", "sprinkle", "boil", "rub"], "celery, mustard, paprika, warm"),
    "everything_bagel": Ingredient("everything bagel seasoning", "spice",
        {"diallyl_disulfide", "dimethyl_sulfide", "methylpyrazine", "pinene"},
        ["sprinkle", "crust", "finish"], "onion, garlic, sesame, poppy, savory"),
    "sesame_seeds": Ingredient("sesame seeds", "spice",
        {"methylpyrazine", "acetylpyrazine", "hexanal", "furfural"},
        ["toast", "sprinkle", "grind", "crust"], "nutty, toasty, subtle"),
    "poppy_seeds": Ingredient("poppy seeds", "spice",
        {"hexanal", "nonanal", "linalool", "furfural", "myrcene"},
        ["sprinkle", "bake", "grind"], "nutty, mild, crunchy"),

    # ═══════════════ CONDIMENTS ═══════════════
    "hot_sauce": Ingredient("hot sauce", "fermented",
        {"capsaicin", "acetic_acid", "allicin", "hexanal", "lactic_acid"},
        ["dash", "drizzle", "mix", "marinade"], "hot, tangy, vinegary, sharp"),
    "sriracha": Ingredient("sriracha", "fermented",
        {"capsaicin", "allicin", "acetic_acid", "hexanal", "furaneol"},
        ["drizzle", "mix", "dip", "marinade"], "hot, sweet, garlicky, bright"),
    "mayo": Ingredient("mayonnaise", "dairy",
        {"hexanal", "nonanal", "acetic_acid", "diacetyl"},
        ["spread", "mix", "bind", "dress"], "rich, tangy, creamy, neutral"),
    "ketchup": Ingredient("ketchup", "fermented",
        {"furaneol", "hexanal", "acetic_acid", "dimethyl_sulfide", "maltol"},
        ["dip", "glaze", "mix", "sauce"], "sweet, tangy, tomato, umami"),
    "bbq_sauce": Ingredient("BBQ sauce", "fermented",
        {"guaiacol", "furaneol", "maltol", "acetic_acid", "vanillin", "capsaicin"},
        ["glaze", "marinade", "dip", "baste"], "smoky, sweet, tangy, complex"),
    "ranch": Ingredient("ranch dressing", "dairy",
        {"diacetyl", "lactic_acid", "diallyl_disulfide", "linalool", "hexanal"},
        ["dip", "dress", "drizzle"], "creamy, herby, tangy, garlicky"),
    "white_sugar": Ingredient("sugar", "sweetener",
        set(),  # Sucrose — taste not aroma
        ["dissolve", "caramelize", "bake", "cream"], "sweet, clean, neutral"),
    "flour": Ingredient("flour", "grain",
        {"hexanal", "nonanal", "maltol"},
        ["dredge", "thicken", "bake", "roux"], "mild, wheaty, starchy"),
    "cornstarch": Ingredient("cornstarch", "grain",
        set(),
        ["thicken", "dredge", "coat"], "neutral, thickener"),

    # ═══════════════ ALLIUMS ═══════════════
    "garlic": Ingredient("garlic", "allium",
        {"allicin", "diallyl_disulfide", "methylpyrazine", "thiophene", "dimethyl_sulfide", "methional"},
        ["raw", "roast", "sauté", "confit", "ferment"], "pungent, savory, sweet when cooked"),
    "onion": Ingredient("onion", "allium",
        {"diallyl_disulfide", "dimethyl_sulfide", "thiophene", "hexanal", "linalool", "dimethyl_trisulfide"},
        ["raw", "caramelize", "sauté", "roast", "pickle"], "sharp raw, sweet cooked"),
    "shallot": Ingredient("shallot", "allium",
        {"diallyl_disulfide", "dimethyl_sulfide", "linalool", "hexanal"},
        ["raw", "sauté", "confit", "fry"], "mild, sweet, refined"),
    "leek": Ingredient("leek", "allium",
        {"diallyl_disulfide", "dimethyl_sulfide", "hexanal", "linalool"},
        ["braise", "sauté", "soup", "grill"], "mild, sweet, delicate"),
    "green_onion": Ingredient("green onion", "allium",
        {"diallyl_disulfide", "dimethyl_sulfide", "hexanal", "linalool", "pinene"},
        ["raw", "grill", "garnish", "sauté"], "fresh, mild onion, versatile"),

    # ═══════════════ DAIRY ═══════════════
    "butter": Ingredient("butter", "dairy",
        {"diacetyl", "acetoin", "hexanal", "nonanal", "gamma_decalactone", "vanillin", "delta_decalactone", "butyric_acid"},
        ["melt", "brown", "cream", "clarify"], "rich, creamy, nutty when browned"),
    "parmesan": Ingredient("parmesan", "dairy",
        {"diacetyl", "ethyl_butyrate", "methylpyrazine", "hexanal", "acetic_acid", "acetoin", "butyric_acid"},
        ["grate", "shave", "rind"], "sharp, savory, crystalline"),
    "blue_cheese": Ingredient("blue cheese", "dairy",
        {"methylpyrazine", "diacetyl", "1_octen_3_ol", "nonanal", "acetoin", "hexanal", "butyric_acid", "methyl_thioacetate"},
        ["crumble", "melt", "sauce"], "pungent, tangy, funky"),
    "goat_cheese": Ingredient("goat cheese", "dairy",
        {"diacetyl", "acetoin", "butyric_acid", "hexanal", "nonanal", "lactic_acid"},
        ["crumble", "spread", "bake", "whip"], "tangy, earthy, bright"),
    "yogurt": Ingredient("yogurt", "dairy",
        {"diacetyl", "acetoin", "lactic_acid", "acetic_acid"},
        ["raw", "marinade", "sauce", "bake"], "tangy, creamy, tart"),
    "cream": Ingredient("cream", "dairy",
        {"diacetyl", "acetoin", "gamma_decalactone", "nonanal", "vanillin", "delta_decalactone"},
        ["whip", "reduce", "infuse", "pour"], "rich, sweet, smooth"),
    "ricotta": Ingredient("ricotta", "dairy",
        {"diacetyl", "acetoin", "lactic_acid", "hexanal", "nonanal"},
        ["spread", "bake", "stuff", "dollop"], "mild, milky, fresh, grainy"),
    "gruyere": Ingredient("gruyere", "dairy",
        {"diacetyl", "methylpyrazine", "acetoin", "butyric_acid", "hexanal", "nonanal", "thiophene"},
        ["melt", "grate", "fondue", "gratinée"], "nutty, sweet, earthy, complex"),
    "mascarpone": Ingredient("mascarpone", "dairy",
        {"diacetyl", "acetoin", "gamma_decalactone", "vanillin", "delta_decalactone"},
        ["spread", "fold", "whip", "layer"], "ultra-rich, sweet, velvety"),

    # ═══════════════ NUTS ═══════════════
    "almond": Ingredient("almond", "nut",
        {"benzaldehyde", "methylpyrazine", "hexanal", "vanillin", "linalool", "furfural"},
        ["toast", "grind", "blanch", "butter"], "sweet, marzipan, delicate"),
    "walnut": Ingredient("walnut", "nut",
        {"hexanal", "nonanal", "methylpyrazine", "1_octen_3_ol"},
        ["toast", "chop", "candy", "press"], "earthy, tannic, rich"),
    "pistachio": Ingredient("pistachio", "nut",
        {"linalool", "limonene", "myrcene", "pinene", "hexanal", "methylpyrazine"},
        ["toast", "grind", "chop"], "sweet, green, earthy"),
    "peanut": Ingredient("peanut", "nut",
        {"methylpyrazine", "acetylpyrazine", "hexanal", "benzaldehyde", "furaneol"},
        ["roast", "grind", "boil", "butter"], "roasty, nutty, earthy"),
    "hazelnut": Ingredient("hazelnut", "nut",
        {"methylpyrazine", "acetylpyrazine", "vanillin", "hexanal", "linalool", "maltol", "furfural"},
        ["toast", "grind", "butter"], "rich, sweet, toasty"),
    "cashew": Ingredient("cashew", "nut",
        {"methylpyrazine", "hexanal", "nonanal", "acetylpyrazine", "furfural"},
        ["toast", "cream", "butter", "grind"], "buttery, mild, sweet"),
    "pecan": Ingredient("pecan", "nut",
        {"methylpyrazine", "vanillin", "hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["toast", "candy", "chop", "pie"], "buttery, sweet, maple-like"),
    "macadamia": Ingredient("macadamia", "nut",
        {"hexanal", "nonanal", "methylpyrazine", "gamma_decalactone", "furfural"},
        ["toast", "chop", "butter", "bake"], "buttery, rich, creamy, subtle"),
    "tahini": Ingredient("tahini", "nut",
        {"methylpyrazine", "acetylpyrazine", "hexanal", "furfural", "guaiacol"},
        ["raw", "dress", "sauce", "spread"], "nutty, bitter, toasty, earthy"),

    # ═══════════════ MUSHROOMS ═══════════════
    "shiitake": Ingredient("shiitake", "mushroom",
        {"1_octen_3_ol", "dimethyl_sulfide", "thiophene", "methylpyrazine", "hexanal", "dimethyl_trisulfide"},
        ["sauté", "dry", "braise", "grill"], "earthy, umami, meaty"),
    "truffle": Ingredient("truffle", "mushroom",
        {"dimethyl_sulfide", "1_octen_3_ol", "thiophene", "methylpyrazine", "nonanal", "dimethyl_trisulfide"},
        ["shave", "infuse", "finish"], "intense, earthy, musky"),
    "porcini": Ingredient("porcini", "mushroom",
        {"1_octen_3_ol", "hexanal", "nonanal", "methylpyrazine", "thiophene"},
        ["sauté", "dry", "braise", "risotto"], "nutty, woodsy, deep"),
    "oyster_mushroom": Ingredient("oyster mushroom", "mushroom",
        {"1_octen_3_ol", "hexanal", "nonanal", "benzaldehyde"},
        ["sauté", "fry", "grill", "braise"], "delicate, mild, slightly sweet"),
    "chanterelle": Ingredient("chanterelle", "mushroom",
        {"1_octen_3_ol", "hexanal", "nonanal", "linalool", "geraniol"},
        ["sauté", "cream", "dry", "pickle"], "fruity, peppery, apricot-like"),
    "morel": Ingredient("morel", "mushroom",
        {"1_octen_3_ol", "hexanal", "methylpyrazine", "nonanal", "furfural"},
        ["sauté", "cream", "stuff", "dry"], "earthy, nutty, complex, smoky"),

    # ═══════════════ GRAINS & STARCHES ═══════════════
    # ── Bread ──
    "bread": Ingredient("bread", "grain",
        {"acetylpyrazine", "methylpyrazine", "maltol", "furaneol", "hexanal", "diacetyl", "furfural"},
        ["toast", "grill", "crumb", "cube"], "yeasty, toasty, wheaty"),
    "sourdough": Ingredient("sourdough", "grain",
        {"acetic_acid", "lactic_acid", "acetylpyrazine", "maltol", "furfural", "diacetyl", "ethyl_acetate"},
        ["toast", "grill", "slice", "crouton"], "tangy, complex, chewy, crusty"),
    "ciabatta": Ingredient("ciabatta", "grain",
        {"acetylpyrazine", "maltol", "hexanal", "furfural", "diacetyl"},
        ["toast", "grill", "sandwich", "bruschetta"], "airy, olive oil, crusty, chewy"),
    "brioche": Ingredient("brioche", "grain",
        {"diacetyl", "vanillin", "maltol", "acetoin", "furaneol", "gamma_decalactone"},
        ["toast", "french toast", "bun", "bread pudding"], "buttery, rich, sweet, pillowy"),
    "pita": Ingredient("pita", "grain",
        {"acetylpyrazine", "maltol", "hexanal", "furfural", "methylpyrazine"},
        ["warm", "stuff", "chip", "toast"], "mild, pocket, soft, versatile"),
    "focaccia": Ingredient("focaccia", "grain",
        {"hexanal", "linalool", "pinene", "acetylpyrazine", "maltol", "furfural"},
        ["slice", "sandwich", "dip", "toast"], "herby, olive oil, dimpled, chewy"),
    "cornbread": Ingredient("cornbread", "grain",
        {"dimethyl_sulfide", "acetylpyrazine", "maltol", "furaneol", "diacetyl", "hexanal"},
        ["bake", "crumble", "slice", "stuff"], "sweet, corn, crumbly, rustic"),
    "naan": Ingredient("naan", "grain",
        {"acetylpyrazine", "methylpyrazine", "maltol", "diacetyl", "furfural", "lactic_acid"},
        ["grill", "bake", "char", "stuff"], "yeasty, charred, pillowy"),
    "tortilla": Ingredient("tortilla", "grain",
        {"acetylpyrazine", "maltol", "hexanal", "furfural", "dimethyl_sulfide"},
        ["warm", "fry", "wrap", "bake", "char"], "corn or flour, mild, pliable"),
    # ── Rice ──
    "rice": Ingredient("white rice", "grain",
        {"hexanal", "nonanal", "acetylpyrazine", "maltol", "acetyl_pyrroline"},
        ["boil", "steam", "fry", "toast"], "mild, starchy, fluffy"),
    "jasmine_rice": Ingredient("jasmine rice", "grain",
        {"acetyl_pyrroline", "hexanal", "nonanal", "linalool", "maltol", "indole"},
        ["steam", "boil", "coconut"], "floral, fragrant, soft, aromatic"),
    "basmati_rice": Ingredient("basmati rice", "grain",
        {"acetyl_pyrroline", "hexanal", "nonanal", "linalool", "myrcene"},
        ["boil", "pilaf", "steam", "biryani"], "nutty, fragrant, long-grain, separate"),
    "brown_rice": Ingredient("brown rice", "grain",
        {"hexanal", "nonanal", "acetylpyrazine", "maltol", "furfural"},
        ["boil", "steam", "pilaf"], "nutty, chewy, wholesome, earthy"),
    "arborio_rice": Ingredient("arborio rice", "grain",
        {"hexanal", "nonanal", "acetylpyrazine", "maltol", "diacetyl"},
        ["risotto", "pudding", "simmer"], "starchy, creamy, plump, absorbent"),
    "sticky_rice": Ingredient("sticky rice", "grain",
        {"acetyl_pyrroline", "hexanal", "nonanal", "maltol"},
        ["steam", "wrap", "mold"], "sweet, glutinous, chewy, clumpy"),
    "wild_rice": Ingredient("wild rice", "grain",
        {"hexanal", "nonanal", "methylpyrazine", "furfural", "acetylpyrazine"},
        ["boil", "pilaf", "salad", "stuff"], "earthy, nutty, chewy, smoky"),
    # ── Noodles & Pasta ──
    "spaghetti": Ingredient("spaghetti", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "toss", "twirl"], "wheaty, firm, classic, versatile"),
    "penne": Ingredient("penne", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "bake", "toss"], "wheaty, tubular, holds sauce, firm"),
    "fettuccine": Ingredient("fettuccine", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine", "diacetyl"},
        ["boil", "toss", "cream"], "rich, flat, egg noodle, silky"),
    "egg_noodles": Ingredient("egg noodles", "grain",
        {"hexanal", "maltol", "furfural", "diacetyl", "nonanal"},
        ["boil", "soup", "casserole", "butter"], "eggy, tender, comfort, homestyle"),
    "rice_noodles": Ingredient("rice noodles", "grain",
        {"hexanal", "nonanal", "acetyl_pyrroline", "maltol", "linalool"},
        ["soak", "stir-fry", "soup", "salad"], "slippery, delicate, glassy, neutral, Asian"),
    "udon": Ingredient("udon", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "stir-fry", "soup", "cold"], "thick, chewy, bouncy, wheaty, Japanese"),
    "soba": Ingredient("soba", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine", "methylpyrazine"},
        ["boil", "cold", "soup", "dip"], "nutty, buckwheat, earthy, firm, Japanese"),
    "ramen_noodles": Ingredient("ramen noodles", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine", "lactic_acid"},
        ["boil", "soup", "stir-fry"], "springy, alkaline, chewy, yellow"),
    "gnocchi": Ingredient("gnocchi", "grain",
        {"hexanal", "nonanal", "methional", "maltol", "diacetyl"},
        ["boil", "pan-fry", "bake", "sauce"], "pillowy, potato, dumpling, tender, Italian"),
    "orzo": Ingredient("orzo", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "pilaf", "salad", "soup"], "rice-shaped pasta, versatile, light"),
    # ── More Pasta Shapes ──
    "elbow_macaroni": Ingredient("elbow macaroni", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "bake", "casserole"], "curved, tubular, classic mac & cheese shape, holds sauce inside"),
    "shells": Ingredient("pasta shells", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "stuff", "bake", "toss"], "cup-shaped, catches sauce and cheese, great stuffed"),
    "rigatoni": Ingredient("rigatoni", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "bake", "toss"], "large ridged tubes, holds chunky sauce, hearty, al dente"),
    "rotini": Ingredient("rotini", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "salad", "casserole", "toss"], "spiral-shaped, traps sauce in twists, fun, versatile"),
    "farfalle": Ingredient("farfalle", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "salad", "cream", "toss"], "bow-tie shaped, thick center chewy edges, elegant"),
    "angel_hair": Ingredient("angel hair", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "toss", "nest"], "ultra-thin, delicate, cooks in 2 min, pairs with light sauces"),
    "linguine": Ingredient("linguine", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "toss", "twirl"], "flat and wide, between spaghetti and fettuccine, seafood classic"),
    "ziti": Ingredient("ziti", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "bake", "toss"], "smooth tubes, perfect for baked dishes, holds ricotta"),
    "cavatappi": Ingredient("cavatappi", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "bake", "mac"], "corkscrew tubes, ridged, ultimate mac & cheese pasta"),
    "orecchiette": Ingredient("orecchiette", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "toss", "broccoli rabe"], "little ear shapes, catches crumbled sausage and greens"),
    "lasagna_sheets": Ingredient("lasagna sheets", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine", "diacetyl"},
        ["layer", "bake", "roll"], "flat wide sheets for layering, absorbs sauce, becomes silky"),
    "vermicelli": Ingredient("vermicelli", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["boil", "stir-fry", "soup", "nest"], "very thin, quick-cooking, works in soups and Asian dishes"),
    "lo_mein_noodles": Ingredient("lo mein noodles", "grain",
        {"hexanal", "maltol", "furfural", "diacetyl", "acetylpyrazine"},
        ["boil", "stir-fry", "toss"], "chewy, egg-based, Chinese, absorbs sauce well"),
    "couscous": Ingredient("couscous", "grain",
        {"hexanal", "maltol", "furfural", "acetylpyrazine"},
        ["steam", "fluff", "salad", "pilaf"], "fluffy, tiny, North African, quick"),
    # ── Other Grains ──
    "oat": Ingredient("oat", "grain",
        {"hexanal", "vanillin", "maltol", "acetylpyrazine", "furaneol", "furfural"},
        ["toast", "boil", "bake", "grind"], "earthy, sweet, nutty"),
    "quinoa": Ingredient("quinoa", "grain",
        {"hexanal", "nonanal", "methylpyrazine", "acetylpyrazine", "linalool"},
        ["toast", "boil", "pilaf", "salad"], "nutty, earthy, mild"),
    "barley": Ingredient("barley", "grain",
        {"hexanal", "maltol", "methylpyrazine", "furfural", "vanillin"},
        ["toast", "simmer", "risotto", "soup"], "malty, chewy, sweet"),
    "polenta": Ingredient("polenta", "grain",
        {"dimethyl_sulfide", "acetylpyrazine", "maltol", "hexanal", "diacetyl"},
        ["simmer", "fry", "grill", "bake"], "corn, creamy, sweet"),
    "farro": Ingredient("farro", "grain",
        {"hexanal", "nonanal", "maltol", "methylpyrazine", "furfural"},
        ["boil", "salad", "risotto", "soup"], "nutty, chewy, ancient grain, hearty"),

    # ═══════════════ LEGUMES ═══════════════
    "chickpea": Ingredient("chickpea", "legume",
        {"hexanal", "nonanal", "methylpyrazine", "acetylpyrazine", "methoxypyrazine"},
        ["roast", "boil", "fry", "purée", "stew"], "nutty, earthy, starchy"),
    "lentil": Ingredient("lentil", "legume",
        {"hexanal", "nonanal", "methylpyrazine", "methional", "furfural"},
        ["simmer", "stew", "purée", "salad"], "earthy, peppery, hearty"),
    "black_bean": Ingredient("black bean", "legume",
        {"hexanal", "methylpyrazine", "furfural", "nonanal", "methional"},
        ["simmer", "fry", "purée", "stew"], "earthy, rich, meaty"),
    "edamame": Ingredient("edamame", "legume",
        {"hexanal", "dimethyl_sulfide", "nonanal", "linalool", "methoxypyrazine"},
        ["boil", "steam", "sauté", "purée"], "sweet, green, nutty, fresh"),

    # ═══════════════ FERMENTED ═══════════════
    "soy_sauce": Ingredient("soy sauce", "fermented",
        {"methylpyrazine", "acetylpyrazine", "furaneol", "guaiacol", "maltol", "acetic_acid", "methional"},
        ["season", "glaze", "marinade", "dip"], "salty, umami, complex"),
    "miso": Ingredient("miso", "fermented",
        {"methylpyrazine", "sotolon", "furaneol", "acetylpyrazine", "dimethyl_sulfide", "methional"},
        ["dissolve", "glaze", "marinade"], "salty, funky, sweet"),
    "fish_sauce": Ingredient("fish sauce", "fermented",
        {"trimethylamine", "methylpyrazine", "dimethyl_sulfide", "methional", "butyric_acid", "acetic_acid"},
        ["season", "dress", "marinade", "dip"], "pungent, umami, funky, depth"),
    "kimchi": Ingredient("kimchi", "fermented",
        {"allyl_isothiocyanate", "diallyl_disulfide", "lactic_acid", "acetic_acid", "dimethyl_sulfide", "capsaicin"},
        ["raw", "fry", "stew", "pancake"], "sour, spicy, funky, complex"),
    "coffee": Ingredient("coffee", "fermented",
        {"methylpyrazine", "acetylpyrazine", "guaiacol", "furaneol", "vanillin", "4vg", "maltol", "linalool", "furfural"},
        ["brew", "grind", "infuse", "espresso"], "bitter, roasty, complex"),
    "chocolate": Ingredient("chocolate", "fermented",
        {"methylpyrazine", "vanillin", "acetylpyrazine", "linalool", "furaneol", "maltol", "phenethyl_alcohol", "furfural"},
        ["melt", "temper", "grate", "ganache"], "rich, bitter, complex"),
    "wine_red": Ingredient("red wine", "fermented",
        {"ethyl_acetate", "linalool", "eugenol", "vanillin", "guaiacol", "4vg", "damascenone", "ionone", "tartaric_acid"},
        ["reduce", "deglaze", "braise", "marinade"], "tannic, fruity, complex"),
    "beer": Ingredient("beer", "fermented",
        {"linalool", "myrcene", "ethyl_acetate", "diacetyl", "4vg", "isoamyl_acetate"},
        ["braise", "batter", "reduce", "steam"], "bitter, malty, hoppy"),
    "vinegar": Ingredient("vinegar", "fermented",
        {"acetic_acid", "ethyl_acetate", "diacetyl", "acetoin"},
        ["dress", "deglaze", "pickle", "reduce"], "sharp, sour, bright"),
    "balsamic": Ingredient("balsamic vinegar", "fermented",
        {"acetic_acid", "furaneol", "maltol", "vanillin", "ethyl_acetate", "furfural"},
        ["drizzle", "reduce", "glaze", "dress"], "sweet, complex, syrupy, aged"),
    "sake": Ingredient("sake", "fermented",
        {"ethyl_acetate", "isoamyl_acetate", "linalool", "acetoin", "diacetyl", "lactic_acid"},
        ["deglaze", "poach", "marinade", "steam"], "clean, floral, rice, delicate"),

    # ═══════════════ OILS / FATS ═══════════════
    "olive_oil": Ingredient("olive oil", "oil/fat",
        {"hexanal", "nonanal", "linalool", "limonene", "pinene"},
        ["drizzle", "sauté", "fry", "dress"], "fruity, peppery, grassy"),
    "sesame_oil": Ingredient("sesame oil", "oil/fat",
        {"methylpyrazine", "acetylpyrazine", "hexanal", "guaiacol", "furaneol", "furfural"},
        ["drizzle", "finish", "stir-fry"], "nutty, toasty, rich"),
    "coconut_oil": Ingredient("coconut oil", "oil/fat",
        {"gamma_octalactone", "gamma_decalactone", "nonanal", "delta_decalactone"},
        ["fry", "bake", "sauté", "drizzle"], "coconut, mild, tropical"),

    # ═══════════════ SWEETENERS ═══════════════
    "honey": Ingredient("honey", "sweetener",
        {"phenethyl_alcohol", "linalool", "vanillin", "damascenone", "furaneol", "nonanal", "phenylacetaldehyde"},
        ["drizzle", "dissolve", "glaze", "bake"], "floral, sweet, complex"),
    "maple_syrup": Ingredient("maple syrup", "sweetener",
        {"sotolon", "vanillin", "maltol", "furaneol", "acetoin", "furfural"},
        ["drizzle", "glaze", "bake", "candy"], "caramel, woody, sweet"),
    "brown_sugar": Ingredient("brown sugar", "sweetener",
        {"maltol", "furaneol", "vanillin", "diacetyl", "acetoin"},
        ["dissolve", "caramelize", "bake", "rub"], "molasses, toffee, warm"),
    "caramel": Ingredient("caramel", "sweetener",
        {"maltol", "furaneol", "diacetyl", "vanillin", "furfural", "acetylpyrazine", "ethyl_maltol"},
        ["drizzle", "sauce", "candy", "flavor"], "rich, burnt sugar, buttery, complex"),

    # ═══════════════ SEEDS ═══════════════
    "sesame_seed": Ingredient("sesame seeds", "nut",
        {"methylpyrazine", "acetylpyrazine", "hexanal", "furfural", "guaiacol", "linalool"},
        ["toast", "sprinkle", "grind", "garnish"], "nutty, toasty, delicate"),
    "pumpkin_seed": Ingredient("pumpkin seeds", "nut",
        {"hexanal", "nonanal", "methylpyrazine", "linalool", "pinene"},
        ["toast", "press", "garnish", "blend"], "nutty, earthy, green"),
    "sunflower_seed": Ingredient("sunflower seeds", "nut",
        {"hexanal", "nonanal", "methylpyrazine", "linalool", "furfural"},
        ["toast", "butter", "garnish", "grind"], "mild, nutty, slightly sweet"),
    "flax_seed": Ingredient("flax seeds", "nut",
        {"hexanal", "nonanal", "linalool", "pinene", "furfural"},
        ["grind", "soak", "bake", "sprinkle"], "earthy, nutty, mild"),

    # ═══════════════ MORE DAIRY ═══════════════
    "cheddar": Ingredient("cheddar", "dairy",
        {"diacetyl", "acetoin", "butyric_acid", "methylpyrazine", "hexanal", "nonanal", "methional"},
        ["grate", "melt", "slice", "sauce"], "sharp, tangy, rich, aged"),
    "mozzarella": Ingredient("mozzarella", "dairy",
        {"diacetyl", "acetoin", "lactic_acid", "hexanal", "nonanal", "delta_decalactone"},
        ["tear", "melt", "slice", "bake"], "mild, milky, stretchy, fresh"),
    "feta": Ingredient("feta", "dairy",
        {"diacetyl", "acetoin", "butyric_acid", "lactic_acid", "hexanal", "acetic_acid"},
        ["crumble", "bake", "whip", "brine"], "salty, tangy, briny, crumbly"),
    "brie": Ingredient("brie", "dairy",
        {"diacetyl", "acetoin", "1_octen_3_ol", "gamma_decalactone", "nonanal", "dimethyl_sulfide"},
        ["bake", "slice", "spread", "melt"], "creamy, earthy, mushroomy, buttery"),
    "cream_cheese": Ingredient("cream cheese", "dairy",
        {"diacetyl", "acetoin", "lactic_acid", "gamma_decalactone", "nonanal"},
        ["spread", "whip", "bake", "fold"], "mild, tangy, smooth, rich"),

    # ═══════════════ MORE VEGETABLES ═══════════════
    "potato": Ingredient("potato", "vegetable",
        {"methional", "hexanal", "nonanal", "dimethyl_sulfide", "methylpyrazine", "acetylpyrazine"},
        ["roast", "mash", "fry", "bake", "boil"], "starchy, earthy, versatile"),
    "butternut_squash": Ingredient("butternut squash", "vegetable",
        {"nonanal", "hexanal", "maltol", "furaneol", "ionone", "linalool"},
        ["roast", "purée", "soup", "bake", "stuff"], "sweet, nutty, velvety"),
    "bok_choy": Ingredient("bok choy", "vegetable",
        {"dimethyl_sulfide", "hexanal", "allyl_isothiocyanate", "linalool", "nonanal"},
        ["stir-fry", "steam", "braise", "grill", "raw"], "mild, crisp, slightly sweet"),
    "snap_peas": Ingredient("snap peas", "vegetable",
        {"hexanal", "methoxypyrazine", "linalool", "dimethyl_sulfide", "nonanal"},
        ["raw", "stir-fry", "sauté", "blanch"], "sweet, crisp, green, fresh"),
    "tomatillo": Ingredient("tomatillo", "vegetable",
        {"hexanal", "linalool", "citric_acid", "malic_acid", "limonene", "nonanal"},
        ["roast", "raw", "simmer", "blend"], "tart, bright, citrusy, herbal"),
    "jalapeno": Ingredient("jalapeño", "vegetable",
        {"capsaicin", "methoxypyrazine", "hexanal", "limonene", "linalool"},
        ["raw", "roast", "pickle", "stuff", "char"], "spicy, bright, vegetal"),
    "poblano": Ingredient("poblano", "vegetable",
        {"methoxypyrazine", "hexanal", "capsaicin", "limonene", "nonanal"},
        ["roast", "stuff", "char", "blend", "dry"], "mild heat, earthy, rich"),
    "green_bean": Ingredient("green beans", "vegetable",
        {"hexanal", "methoxypyrazine", "linalool", "nonanal", "dimethyl_sulfide"},
        ["blanch", "sauté", "roast", "steam", "pickle"], "green, crisp, fresh"),
    "mushroom_button": Ingredient("button mushrooms", "mushroom",
        {"1_octen_3_ol", "hexanal", "nonanal", "linalool"},
        ["sauté", "raw", "stuff", "grill", "cream"], "mild, earthy, versatile"),
    "acorn_squash": Ingredient("acorn squash", "vegetable",
        {"nonanal", "hexanal", "maltol", "furaneol", "linalool"},
        ["roast", "stuff", "bake", "purée"], "sweet, nutty, hearty"),

    # ═══════════════ CONDIMENTS / PANTRY ═══════════════
    "gochujang": Ingredient("gochujang", "fermented",
        {"capsaicin", "methylpyrazine", "furaneol", "maltol", "acetic_acid", "acetylpyrazine"},
        ["glaze", "marinade", "sauce", "stir"], "sweet, spicy, funky, umami"),
    "harissa": Ingredient("harissa", "fermented",
        {"capsaicin", "cuminaldehyde", "linalool", "pinene", "limonene", "guaiacol"},
        ["paste", "marinade", "stir", "drizzle"], "smoky, spicy, complex, North African"),
    "hoisin": Ingredient("hoisin", "fermented",
        {"methylpyrazine", "furaneol", "maltol", "vanillin", "acetic_acid", "acetylpyrazine"},
        ["glaze", "dip", "marinade", "sauce"], "sweet, salty, umami, thick"),
    "chipotle": Ingredient("chipotle", "spice",
        {"capsaicin", "guaiacol", "4vg", "methylpyrazine", "hexanal", "cresol"},
        ["purée", "rehydrate", "sauce", "rub"], "smoky, moderate heat, deep, complex"),
    "coconut_milk": Ingredient("coconut milk", "dairy",
        {"gamma_octalactone", "gamma_decalactone", "nonanal", "delta_decalactone", "vanillin"},
        ["simmer", "curry", "soup", "bake"], "rich, creamy, tropical, sweet"),
    "tomato_paste": Ingredient("tomato paste", "vegetable",
        {"furaneol", "hexanal", "methylpyrazine", "guaiacol", "dimethyl_sulfide", "maltol"},
        ["bloom", "sauce", "braise", "deglaze"], "concentrated, umami, sweet, intense"),
    "dijon": Ingredient("Dijon mustard", "fermented",
        {"allyl_isothiocyanate", "acetic_acid", "linalool", "pinene", "myrcene"},
        ["dress", "sauce", "marinade", "glaze"], "sharp, creamy, tangy, complex"),
    "worcestershire": Ingredient("Worcestershire", "fermented",
        {"acetic_acid", "trimethylamine", "dimethyl_sulfide", "methylpyrazine", "maltol", "methional"},
        ["season", "marinade", "sauce", "deglaze"], "umami, tangy, complex, aged"),

    # ═══════════════ SAUCES ═══════════════
    "tomato_sauce": Ingredient("tomato sauce", "sauce",
        {"furaneol", "hexanal", "dimethyl_sulfide", "geraniol", "ionone", "linalool", "citral"},
        ["simmer", "spread", "bake", "braise"], "sweet, acidic, tomatoey, smooth"),
    "marinara": Ingredient("marinara", "sauce",
        {"furaneol", "hexanal", "linalool", "eugenol", "allicin", "dimethyl_sulfide", "geraniol"},
        ["simmer", "spread", "dip", "bake"], "garlicky, herby, tomato, Italian"),
    "pesto": Ingredient("pesto", "sauce",
        {"linalool", "eugenol", "pinene", "myrcene", "methylpyrazine", "hexanal", "geraniol"},
        ["spread", "toss", "drizzle", "dollop"], "herby, nutty, garlicky, bright"),
    "alfredo": Ingredient("alfredo sauce", "sauce",
        {"diacetyl", "acetoin", "gamma_decalactone", "vanillin", "nonanal", "butyric_acid"},
        ["simmer", "toss", "bake", "pour"], "rich, buttery, cheesy, creamy"),
    "curry_paste": Ingredient("curry paste", "sauce",
        {"linalool", "citral", "myrcene", "limonene", "capsaicin", "geraniol", "zingerone", "pinene"},
        ["bloom", "simmer", "stir", "marinade"], "aromatic, spicy, complex, concentrated"),
    "enchilada_sauce": Ingredient("enchilada sauce", "sauce",
        {"capsaicin", "cuminaldehyde", "hexanal", "guaiacol", "acetic_acid", "methylpyrazine"},
        ["simmer", "pour", "bake", "dip"], "earthy, mild heat, tangy, smoky"),
    "teriyaki": Ingredient("teriyaki sauce", "sauce",
        {"methylpyrazine", "furaneol", "maltol", "acetic_acid", "zingerone", "ethyl_acetate"},
        ["glaze", "marinade", "stir-fry", "dip"], "sweet, salty, gingery, caramelized"),
    "bechamel": Ingredient("béchamel", "sauce",
        {"diacetyl", "acetoin", "vanillin", "nonanal", "maltol"},
        ["pour", "layer", "bake", "gratinée"], "creamy, buttery, mild, velvety"),
    "chimichurri": Ingredient("chimichurri", "sauce",
        {"linalool", "pinene", "myrcene", "limonene", "acetic_acid", "hexanal", "allicin"},
        ["drizzle", "marinade", "spoon", "dip"], "herby, garlicky, tangy, bright"),
    "salsa": Ingredient("salsa", "sauce",
        {"hexanal", "citral", "linalool", "capsaicin", "allicin", "citric_acid", "dimethyl_sulfide"},
        ["spoon", "dip", "top", "mix"], "fresh, spicy, bright, chunky"),
    "buffalo_sauce": Ingredient("buffalo sauce", "sauce",
        {"capsaicin", "acetic_acid", "diacetyl", "piperine"},
        ["toss", "drizzle", "dip", "glaze"], "hot, tangy, buttery, sharp"),

    # ═══════════════ STOCKS & BROTHS ═══════════════
    "chicken_stock": Ingredient("chicken stock", "sauce",
        {"hexanal", "nonanal", "methional", "diacetyl", "thiophene", "dimethyl_sulfide"},
        ["simmer", "base", "deglaze", "poach"], "savory, golden, rich, comforting, backbone of most soups"),
    "beef_stock": Ingredient("beef stock", "sauce",
        {"methylpyrazine", "hexanal", "nonanal", "thiophene", "guaiacol", "methional"},
        ["simmer", "base", "braise", "deglaze"], "deep, meaty, brown, robust, hearty base"),
    "vegetable_stock": Ingredient("vegetable stock", "sauce",
        {"hexanal", "nonanal", "dimethyl_sulfide", "linalool", "myrcene"},
        ["simmer", "base", "poach", "deglaze"], "light, clean, herby, versatile, veggie base"),
    "bone_broth": Ingredient("bone broth", "sauce",
        {"methional", "hexanal", "nonanal", "diacetyl", "thiophene", "dimethyl_sulfide", "methylpyrazine"},
        ["sip", "base", "simmer", "braise"], "gelatinous, deeply savory, collagen-rich, umami"),
    "dashi": Ingredient("dashi", "sauce",
        {"dimethyl_sulfide", "methylpyrazine", "trimethylamine", "hexanal", "methional"},
        ["base", "simmer", "season", "poach"], "clean, smoky, umami, Japanese stock from kelp and bonito"),
    "coconut_broth": Ingredient("coconut broth", "sauce",
        {"gamma_octalactone", "gamma_decalactone", "linalool", "citral", "nonanal", "vanillin"},
        ["simmer", "base", "curry", "poach"], "creamy, tropical, fragrant, Thai/Indian soup base"),
    "tomato_broth": Ingredient("tomato broth", "sauce",
        {"furaneol", "hexanal", "dimethyl_sulfide", "citral", "geraniol", "linalool"},
        ["simmer", "base", "poach"], "bright, acidic, tomatoey, light, Italian/Spanish base"),
    "miso_broth": Ingredient("miso broth", "sauce",
        {"methylpyrazine", "sotolon", "furaneol", "dimethyl_sulfide", "methional"},
        ["dissolve", "base", "simmer"], "salty, umami, fermented, warming, Japanese base"),

    # ═══════════════ MISSING ESSENTIALS ═══════════════
    "sour_cream": Ingredient("sour cream", "dairy",
        {"diacetyl", "acetoin", "lactic_acid", "acetic_acid", "nonanal"},
        ["dollop", "mix", "dress", "top"], "tangy, rich, cool, creamy"),
    "peanut_butter": Ingredient("peanut butter", "nut",
        {"methylpyrazine", "acetylpyrazine", "hexanal", "benzaldehyde", "furaneol", "furfural"},
        ["spread", "sauce", "blend", "bake"], "roasty, nutty, rich, creamy"),
    "green_beans": Ingredient("green beans", "vegetable",
        {"hexanal", "linalool", "nonanal", "methoxypyrazine", "dimethyl_sulfide"},
        ["steam", "sauté", "blanch", "roast", "fry"], "crisp, green, fresh, snappy"),
    "pickles": Ingredient("pickles", "fermented",
        {"acetic_acid", "lactic_acid", "allyl_isothiocyanate", "hexanal", "linalool"},
        ["chop", "slice", "garnish", "relish"], "sour, crunchy, briny, tangy"),

    # ═══════════════ MORE PROTEINS ═══════════════
    "sausage": Ingredient("sausage", "protein",
        {"methylpyrazine", "hexanal", "nonanal", "thiophene", "guaiacol", "4vg", "cresol", "allicin"},
        ["grill", "sauté", "crumble", "smoke", "bake"], "savory, spiced, fatty, smoky"),
    "prosciutto": Ingredient("prosciutto", "protein",
        {"methylpyrazine", "hexanal", "nonanal", "thiophene", "diacetyl", "guaiacol"},
        ["raw", "crisp", "wrap", "garnish"], "salty, nutty, delicate, aged"),
    "ground_beef": Ingredient("ground beef", "protein",
        {"hexanal", "thiophene", "methylpyrazine", "guaiacol", "nonanal", "4vg", "diacetyl", "methional"},
        ["brown", "shape", "stuff", "simmer", "grill"], "rich, umami, versatile"),

    # ═══════════════ STARCHES / NOODLES ═══════════════
    "pasta": Ingredient("pasta", "grain",
        {"hexanal", "nonanal", "acetylpyrazine", "maltol", "furfural"},
        ["boil", "bake", "toss", "stuff"], "wheaty, mild, versatile"),

    # ═══════════════ ADDITIONAL INGREDIENTS ═══════════════
    # ── More Cheeses ──
    "monterey_jack": Ingredient("Monterey Jack", "dairy",
        {"diacetyl", "acetoin", "hexanal", "nonanal", "lactic_acid", "delta_decalactone"},
        ["melt", "grate", "slice", "quesadilla"], "mild, buttery, great melter"),
    "swiss": Ingredient("Swiss cheese", "dairy",
        {"diacetyl", "acetoin", "methylpyrazine", "nonanal", "hexanal"},
        ["melt", "slice", "fondue", "gratinée"], "nutty, sweet, holey, mild"),
    "provolone": Ingredient("provolone", "dairy",
        {"diacetyl", "acetoin", "butyric_acid", "hexanal", "nonanal"},
        ["melt", "slice", "grate"], "sharp, smoky, tangy, Italian"),
    "cotija": Ingredient("cotija", "dairy",
        {"diacetyl", "butyric_acid", "lactic_acid", "hexanal", "acetic_acid"},
        ["crumble", "grate", "garnish"], "salty, crumbly, sharp, Mexican parmesan"),
    "pecorino": Ingredient("pecorino", "dairy",
        {"diacetyl", "butyric_acid", "methylpyrazine", "hexanal", "acetoin", "acetic_acid"},
        ["grate", "shave", "finish"], "sharp, salty, sheepy, crystalline"),
    # ── More Fermented/Wine ──
    "white_wine": Ingredient("white wine", "fermented",
        {"ethyl_acetate", "linalool", "citral", "geraniol", "nonanal", "tartaric_acid", "damascenone"},
        ["deglaze", "poach", "sauce", "braise"], "crisp, fruity, acidic, bright"),
    "rice_vinegar": Ingredient("rice vinegar", "fermented",
        {"acetic_acid", "ethyl_acetate", "acetoin", "lactic_acid"},
        ["dress", "pickle", "season", "dip"], "mild, sweet, delicate, Asian"),
    "apple_cider_vinegar": Ingredient("apple cider vinegar", "fermented",
        {"acetic_acid", "ethyl_acetate", "malic_acid", "ethyl_butyrate"},
        ["dress", "marinade", "pickle", "shrub"], "fruity, tangy, sharp, apple"),
    # ── More Condiments/Sauces ──
    "horseradish": Ingredient("horseradish", "fermented",
        {"allyl_isothiocyanate", "hexanal", "nonanal", "acetic_acid"},
        ["grate", "cream", "sauce", "garnish"], "sharp, nasal heat, pungent, sinus-clearing"),
    "tzatziki": Ingredient("tzatziki", "sauce",
        {"linalool", "lactic_acid", "diacetyl", "acetoin", "hexanal", "trans_2_nonenal"},
        ["dip", "spread", "dollop", "dress"], "cool, garlicky, cucumber, tangy, Greek"),
    "guacamole": Ingredient("guacamole", "sauce",
        {"hexanal", "nonanal", "citral", "allicin", "linalool", "citric_acid"},
        ["dip", "spread", "top", "side"], "creamy, bright, garlicky, fresh, avocado"),
    "hummus": Ingredient("hummus", "sauce",
        {"methylpyrazine", "hexanal", "nonanal", "citric_acid", "linalool", "furfural"},
        ["dip", "spread", "base", "dress"], "nutty, garlicky, lemony, earthy, tahini"),
    "aioli": Ingredient("aioli", "sauce",
        {"hexanal", "nonanal", "allicin", "acetic_acid", "diacetyl"},
        ["spread", "dip", "drizzle", "dollop"], "garlicky, rich, creamy, French mayo"),
    "tahini_sauce": Ingredient("tahini sauce", "sauce",
        {"methylpyrazine", "acetylpyrazine", "hexanal", "furfural", "citric_acid", "linalool"},
        ["drizzle", "dress", "dip", "dollop"], "nutty, sesame, creamy, lemony, Middle Eastern"),
    # ── More Dairy ──
    "buttermilk": Ingredient("buttermilk", "dairy",
        {"diacetyl", "acetoin", "lactic_acid", "acetic_acid", "hexanal"},
        ["marinade", "batter", "dress", "bake"], "tangy, creamy, tender-making, Southern"),
    "labneh": Ingredient("labneh", "dairy",
        {"diacetyl", "acetoin", "lactic_acid", "nonanal", "acetic_acid"},
        ["spread", "dollop", "dip", "base"], "thick, tangy, yogurt cheese, Middle Eastern"),
    "whipped_cream": Ingredient("whipped cream", "dairy",
        {"diacetyl", "acetoin", "gamma_decalactone", "vanillin", "delta_decalactone"},
        ["top", "fold", "pipe", "dollop"], "airy, sweet, light, cloud-like"),
    # ── More Veggies ──
    "roasted_red_pepper": Ingredient("roasted red pepper", "vegetable",
        {"methoxypyrazine", "hexanal", "nonanal", "linalool", "limonene", "furaneol"},
        ["purée", "slice", "stuff", "blend"], "sweet, smoky, silky, charred"),
    "sun_dried_tomato": Ingredient("sun-dried tomato", "vegetable",
        {"furaneol", "hexanal", "methylpyrazine", "dimethyl_sulfide", "guaiacol", "maltol"},
        ["chop", "blend", "rehydrate", "oil-pack"], "intense, chewy, concentrated umami, sweet-tart"),
    "bean_sprouts": Ingredient("bean sprouts", "vegetable",
        {"hexanal", "nonanal", "dimethyl_sulfide", "linalool", "trans_2_nonenal"},
        ["raw", "stir-fry", "blanch", "top"], "crisp, watery, fresh, mild, crunchy"),
    "water_chestnut": Ingredient("water chestnut", "vegetable",
        {"hexanal", "nonanal", "linalool", "dimethyl_sulfide", "furfural"},
        ["slice", "stir-fry", "dice", "can"], "crunchy, sweet, stays crisp when cooked"),
    "bamboo_shoot": Ingredient("bamboo shoot", "vegetable",
        {"hexanal", "nonanal", "dimethyl_sulfide", "linalool"},
        ["slice", "stir-fry", "braise", "pickle"], "mild, crunchy, earthy, slightly sweet"),
    "radicchio": Ingredient("radicchio", "vegetable",
        {"hexanal", "linalool", "nonanal", "dimethyl_sulfide"},
        ["raw", "grill", "roast", "shred"], "bitter, beautiful purple, becomes sweet grilled"),
    "endive": Ingredient("endive", "vegetable",
        {"hexanal", "linalool", "nonanal", "dimethyl_sulfide", "myrcene"},
        ["raw", "braise", "grill", "stuff"], "bitter, crisp, elegant, boat-shaped leaves"),
    "romaine": Ingredient("romaine lettuce", "vegetable",
        {"hexanal", "nonanal", "trans_2_nonenal", "linalool", "dimethyl_sulfide"},
        ["raw", "grill", "wrap", "chop"], "crisp, mild, crunchy, watery, sturdy"),

    # ═══════════ GAPS CLOSED IN 3.1 ═══════════
    # Two of these existed already as far as the override tables were
    # concerned: TEXTURE_OVERRIDES carried an entry for "squid" and
    # TASTE_OVERRIDES one for "arugula", neither of which was an ingredient.
    # The overrides were dead keys and the evidence that both were meant to be
    # here. The rest close obvious holes (no bay leaf in a cooking app) or give
    # a defined-but-unattached compound its real home.
    "bay_leaf": Ingredient("bay leaf", "herb",
        {"eucalyptol", "eugenol", "pinene", "linalool", "terpinene", "sabinene"},
        ["simmer", "braise", "infuse", "steep"],
        "resinous, tea-like, subtly medicinal — a background note you notice when it is gone"),
    "marjoram": Ingredient("marjoram", "herb",
        {"terpinene", "sabinene", "linalool", "eucalyptol", "ocimene", "thymol"},
        ["dried", "infuse", "sprinkle", "roast"],
        "sweeter and softer than oregano, floral-herbal"),
    "arugula": Ingredient("arugula", "vegetable",
        {"allyl_isothiocyanate", "hexanal", "1_octen_3_ol", "nonanal"},
        ["raw", "wilt", "top", "blend"],
        "peppery, bitter, mustardy — the glucosinolate bite"),
    "squid": Ingredient("squid", "seafood",
        {"trimethylamine", "dimethyl_sulfide", "methional", "hexanal", "thiophene"},
        ["fry", "grill", "braise", "sear", "poach"],
        "sweet, mild, briny — chewy unless cooked very fast or very slow"),
    "black_tea": Ingredient("black tea", "fermented",
        {"linalool_oxide", "linalool", "geraniol", "damascenone", "methional",
         "phenylacetaldehyde"},
        ["steep", "infuse", "smoke", "braise"],
        "tannic, malty, floral — the oxidised-leaf aroma"),
    "red_wine": Ingredient("red wine", "fermented",
        {"damascenone", "whiskey_lactone", "ethyl_hexanoate", "tartaric_acid",
         "phenethyl_alcohol", "rotundone"},
        ["reduce", "braise", "deglaze", "marinate"],
        "tannic, dark-fruited, oaky — rotundone gives the peppery reds their pepper"),
}

# ═══════════════════════════════════════════════════════════════════
# GRAIN SUBTYPES — so templates can request specific types of grain
# ═══════════════════════════════════════════════════════════════════

GRAIN_NOODLES = {
    "spaghetti", "penne", "fettuccine", "egg_noodles", "rice_noodles",
    "udon", "soba", "ramen_noodles", "gnocchi", "orzo", "pasta",
    "elbow_macaroni", "shells", "rigatoni", "rotini", "farfalle",
    "angel_hair", "linguine", "ziti", "cavatappi", "orecchiette",
    "lasagna_sheets", "vermicelli", "lo_mein_noodles",
}
GRAIN_BREADS = {
    "bread", "sourdough", "ciabatta", "brioche", "pita", "focaccia",
    "cornbread", "naan", "tortilla",
}
GRAIN_RICE = {
    "rice", "jasmine_rice", "basmati_rice", "brown_rice", "arborio_rice",
    "sticky_rice", "wild_rice",
}
GRAIN_OTHER = {
    "oat", "quinoa", "barley", "polenta", "farro", "couscous", "flour",
    "cornstarch",
}

# Broth/stock subtypes for soup bases
BROTH_TYPES = {
    "chicken_stock", "beef_stock", "vegetable_stock", "bone_broth",
    "dashi", "coconut_broth", "tomato_broth", "miso_broth",
}

# Cooking sauces (NOT stocks) for pizza, pasta, casserole
COOKING_SAUCES = {
    "tomato_sauce", "marinara", "pesto", "alfredo", "curry_paste",
    "enchilada_sauce", "teriyaki", "bechamel", "chimichurri", "salsa",
    "buffalo_sauce", "hummus", "tzatziki", "aioli", "guacamole", "tahini_sauce",
}

# Condiment-type fermented items suitable for dressings/glazes
DRESSINGS = {
    "soy_sauce", "miso", "fish_sauce", "vinegar", "balsamic",
    "gochujang", "hoisin", "harissa", "worcestershire", "dijon",
    "hot_sauce", "sriracha", "ketchup", "bbq_sauce", "kimchi",
    "rice_vinegar", "apple_cider_vinegar", "sake",
    "aioli", "tzatziki", "tahini_sauce",
}

# Grains you'd actually serve as a dish component (not flour/cornstarch)
EDIBLE_GRAINS = {
    n for n in (GRAIN_NOODLES | GRAIN_BREADS | GRAIN_RICE | GRAIN_OTHER)
    if n not in ("flour", "cornstarch")
}

# ═══════════════════════════════════════════════════════════════════
# TEXTURE & TASTE BALANCE SYSTEM
# Beyond aroma compounds — texture contrast and flavor balance
# make the difference between a good recipe and a great one.
# ═══════════════════════════════════════════════════════════════════

# Texture tags per category (defaults), with ingredient-level overrides
CATEGORY_TEXTURES = {
    "protein":   ["tender", "firm"],
    "seafood":   ["tender", "delicate"],
    "vegetable": ["crisp", "firm"],
    "fruit":     ["juicy", "soft"],
    "herb":      ["fresh", "leafy"],
    "spice":     ["dry", "powdery"],
    "dairy":     ["creamy", "smooth"],
    "grain":     ["chewy", "starchy"],
    "nut":       ["crunchy", "crumbly"],
    "oil/fat":   ["silky", "rich"],
    "fermented": ["liquid", "smooth"],
    "mushroom":  ["meaty", "tender"],
    "allium":    ["crisp", "pungent"],
    "citrus":    ["juicy", "bright"],
    "sweetener": ["syrupy", "smooth"],
    "legume":    ["starchy", "creamy"],
    "sauce":     ["smooth", "saucy"],
}

# Override textures for specific ingredients that differ from their category
TEXTURE_OVERRIDES = {
    "bacon": ["crispy", "fatty"], "tofu": ["soft", "silky"], "tempeh": ["firm", "crumbly"],
    "shrimp": ["snappy", "tender"], "scallop": ["buttery", "tender"], "squid": ["chewy", "tender"],
    "lobster": ["tender", "rich"], "oyster": ["briny", "slippery"],
    "eggplant": ["creamy", "meaty"], "potato": ["starchy", "fluffy"], "sweet_potato": ["creamy", "starchy"],
    "corn": ["juicy", "crunchy"], "avocado": ["creamy", "smooth"], "cucumber": ["crisp", "watery"],
    "beet": ["earthy", "firm"], "cabbage": ["crunchy", "leafy"], "kale": ["tough", "leafy"],
    "snap_peas": ["crunchy", "snappy"], "green_beans": ["crisp", "snappy"],
    "coconut": ["fatty", "flaky"], "banana": ["creamy", "soft"], "watermelon": ["watery", "crisp"],
    "parmesan": ["crystalline", "hard"], "feta": ["crumbly", "briny"],
    "blue_cheese": ["crumbly", "creamy"], "cream_cheese": ["smooth", "spreadable"],
    "gruyere": ["melty", "firm"], "mozzarella": ["stretchy", "melty"], "brie": ["gooey", "creamy"],
    "bread": ["crusty", "chewy"], "sourdough": ["crusty", "chewy"], "brioche": ["pillowy", "soft"],
    "ciabatta": ["crusty", "airy"], "pita": ["soft", "pocketable"], "naan": ["pillowy", "charred"],
    "tortilla": ["pliable", "soft"], "cornbread": ["crumbly", "moist"],
    "rice": ["fluffy", "separate"], "sticky_rice": ["glutinous", "chewy"],
    "arborio_rice": ["creamy", "starchy"], "gnocchi": ["pillowy", "tender"],
    "udon": ["thick", "bouncy"], "soba": ["firm", "nutty"], "rice_noodles": ["slippery", "delicate"],
    "ramen_noodles": ["springy", "chewy"],
    "peanut_butter": ["thick", "creamy"], "tahini": ["smooth", "creamy"],
    "kimchi": ["crunchy", "tangy"], "pickles": ["crunchy", "briny"],
    "chocolate": ["smooth", "snappy"], "caramel": ["sticky", "smooth"],
    "honey": ["viscous", "smooth"], "mayo": ["creamy", "thick"],
    "alfredo": ["creamy", "velvety"], "pesto": ["chunky", "herby"],
    "salsa": ["chunky", "fresh"], "chimichurri": ["herby", "loose"],
}

# Taste profile dimensions per category (0.0-1.0 scale)
# Dimensions: salty, sweet, sour, bitter, umami, fatty, spicy
CATEGORY_TASTES = {
    "protein":   {"umami": 0.6, "fatty": 0.4, "salty": 0.2},
    "seafood":   {"umami": 0.7, "salty": 0.4, "fatty": 0.3},
    "vegetable": {"bitter": 0.2, "sweet": 0.2},
    "fruit":     {"sweet": 0.7, "sour": 0.4},
    "herb":      {"bitter": 0.3},
    "spice":     {"bitter": 0.2, "spicy": 0.3},
    "dairy":     {"fatty": 0.7, "salty": 0.3, "umami": 0.2},
    "grain":     {"starchy": 0.7},
    "nut":       {"fatty": 0.5, "bitter": 0.2},
    "oil/fat":   {"fatty": 0.9},
    "fermented": {"umami": 0.6, "salty": 0.5, "sour": 0.4},
    "mushroom":  {"umami": 0.8, "earthy": 0.5},
    "allium":    {"umami": 0.3, "spicy": 0.3, "sweet": 0.2},
    "citrus":    {"sour": 0.8, "sweet": 0.2, "bitter": 0.2},
    "sweetener": {"sweet": 0.9},
    "legume":    {"starchy": 0.5, "umami": 0.3},
    "sauce":     {"umami": 0.4, "sour": 0.2, "salty": 0.3},
}

TASTE_OVERRIDES = {
    "bacon": {"salty": 0.7, "umami": 0.8, "fatty": 0.8, "smoky": 0.6},
    "anchovy": {"salty": 0.9, "umami": 0.9, "fatty": 0.3},
    "parmesan": {"salty": 0.7, "umami": 0.9, "fatty": 0.5},
    "soy_sauce": {"salty": 0.9, "umami": 0.9},
    "fish_sauce": {"salty": 0.8, "umami": 0.9, "sour": 0.2},
    "miso": {"salty": 0.7, "umami": 0.9, "sweet": 0.2},
    "lemon": {"sour": 0.9, "bitter": 0.2},
    "lime": {"sour": 0.9, "bitter": 0.3},
    "grapefruit": {"sour": 0.6, "bitter": 0.6},
    "honey": {"sweet": 0.9},
    "chocolate": {"bitter": 0.6, "sweet": 0.4, "fatty": 0.4},
    "coffee": {"bitter": 0.8, "umami": 0.2},
    "vinegar": {"sour": 0.9},
    "balsamic": {"sour": 0.6, "sweet": 0.5},
    "kimchi": {"sour": 0.6, "spicy": 0.7, "umami": 0.5, "salty": 0.5},
    "hot_sauce": {"spicy": 0.8, "sour": 0.5, "salty": 0.3},
    "sriracha": {"spicy": 0.7, "sweet": 0.3, "sour": 0.3},
    "gochujang": {"spicy": 0.6, "sweet": 0.4, "umami": 0.7},
    "cayenne": {"spicy": 0.9},
    "red_pepper_flakes": {"spicy": 0.7},
    "black_pepper": {"spicy": 0.5},
    "butter": {"fatty": 0.9, "sweet": 0.1},
    "cream": {"fatty": 0.8, "sweet": 0.2},
    "avocado": {"fatty": 0.7},
    "kale": {"bitter": 0.5},
    "arugula": {"bitter": 0.5, "spicy": 0.3},
    "sweet_potato": {"sweet": 0.6, "starchy": 0.5},
    "corn": {"sweet": 0.5, "starchy": 0.3},
    "tomato": {"sour": 0.4, "sweet": 0.3, "umami": 0.5},
    "tomato_sauce": {"sour": 0.4, "sweet": 0.3, "umami": 0.5},
    "marinara": {"sour": 0.4, "umami": 0.5, "sweet": 0.2},
    "alfredo": {"fatty": 0.8, "salty": 0.4, "umami": 0.3},
    "pesto": {"fatty": 0.5, "umami": 0.4, "salty": 0.3},
    "buffalo_sauce": {"spicy": 0.8, "sour": 0.5, "fatty": 0.3},
    "enchilada_sauce": {"spicy": 0.4, "sour": 0.4, "umami": 0.3},
    "teriyaki": {"sweet": 0.6, "salty": 0.7, "umami": 0.5},
    "salt": {"salty": 1.0},
    "msg": {"umami": 1.0},
    "white_sugar": {"sweet": 1.0},
    "feta": {"salty": 0.7, "sour": 0.3, "fatty": 0.4},
    "blue_cheese": {"salty": 0.6, "umami": 0.5, "fatty": 0.5, "bitter": 0.3},
    "worcestershire": {"umami": 0.8, "salty": 0.5, "sour": 0.4, "sweet": 0.2},
    "caramel": {"sweet": 0.8, "bitter": 0.2},
}


def get_textures(ingredient_name: str) -> List[str]:
    """Get texture tags for an ingredient."""
    if ingredient_name in TEXTURE_OVERRIDES:
        return TEXTURE_OVERRIDES[ingredient_name]
    if ingredient_name in INGREDIENTS:
        cat = INGREDIENTS[ingredient_name].category
        return CATEGORY_TEXTURES.get(cat, ["neutral"])
    return ["neutral"]


def get_taste_profile(ingredient_name: str) -> Dict[str, float]:
    """Get taste profile for an ingredient."""
    if ingredient_name in TASTE_OVERRIDES:
        return TASTE_OVERRIDES[ingredient_name]
    if ingredient_name in INGREDIENTS:
        cat = INGREDIENTS[ingredient_name].category
        return CATEGORY_TASTES.get(cat, {})
    return {}


def analyze_balance(ingredient_names: List[str]) -> dict:
    """
    Analyze the texture and taste balance of a set of ingredients.
    Returns strengths, weaknesses, and suggestions.
    """
    # Aggregate textures
    all_textures = []
    for name in ingredient_names:
        all_textures.extend(get_textures(name))
    texture_set = set(all_textures)

    # Aggregate taste dimensions
    taste_totals = defaultdict(float)
    for name in ingredient_names:
        for dim, val in get_taste_profile(name).items():
            taste_totals[dim] += val

    # Averaged over every ingredient, not just the ones carrying that
    # dimension: one very sour thing among six should read as mildly sour
    # overall, which is how the dish tastes. (A per-dimension counter used to
    # be maintained here and never read; this is the denominator that was
    # always intended.)
    taste_avg = {dim: total / len(ingredient_names)
                 for dim, total in taste_totals.items()} if ingredient_names else {}

    # Texture analysis
    has_crunchy = bool(texture_set & {"crunchy", "crispy", "crisp", "crusty", "snappy", "crumbly"})
    has_creamy = bool(texture_set & {"creamy", "smooth", "silky", "velvety", "soft", "pillowy", "gooey"})
    has_chewy = bool(texture_set & {"chewy", "bouncy", "springy", "glutinous", "thick", "firm"})

    texture_suggestions = []
    if not has_crunchy:
        texture_suggestions.append("Missing crunch — try adding nuts, seeds, crispy onions, or croutons")
    if not has_creamy and not any(d in taste_avg for d in ["fatty"]):
        texture_suggestions.append("Missing creaminess — consider cheese, avocado, cream, or a sauce")

    # Taste analysis
    taste_suggestions = []
    strong = [d for d, v in taste_avg.items() if v > 0.4]
    weak = []

    # Check for missing essential dimensions
    if taste_avg.get("sour", 0) < 0.15 and taste_avg.get("salty", 0) > 0.3:
        taste_suggestions.append("Heavy on salt but missing acid — add citrus, vinegar, or pickled element")
    if taste_avg.get("sour", 0) < 0.1:
        taste_suggestions.append("No acid to brighten — consider lemon, lime, vinegar, or tomato")
        weak.append("acid/sour")
    if taste_avg.get("fatty", 0) < 0.1 and taste_avg.get("umami", 0) > 0:
        taste_suggestions.append("Needs richness — add butter, oil, cream, cheese, or avocado")
        weak.append("fat")
    if taste_avg.get("umami", 0) < 0.1:
        taste_suggestions.append("Low umami depth — try parmesan, soy sauce, mushrooms, or miso")
        weak.append("umami")
    if taste_avg.get("sweet", 0) > 0.5 and taste_avg.get("sour", 0) < 0.2:
        taste_suggestions.append("Very sweet — needs acid to balance (citrus, vinegar)")
    if taste_avg.get("spicy", 0) > 0.5 and taste_avg.get("fatty", 0) < 0.2:
        taste_suggestions.append("Lots of heat but no fat to carry it — add cream, butter, or avocado")
    if taste_avg.get("salty", 0) < 0.1:
        taste_suggestions.append("Consider adding salt, soy sauce, or a salty cheese")
        weak.append("salt")
    if taste_avg.get("sweet", 0) < 0.05 and taste_avg.get("bitter", 0) > 0.3:
        taste_suggestions.append("Bitter-heavy — a touch of honey, sugar, or sweet fruit would balance")

    return {
        "textures": sorted(texture_set),
        "has_crunch": has_crunchy,
        "has_cream": has_creamy,
        "has_chewy": has_chewy,
        "texture_suggestions": texture_suggestions,
        "taste_profile": taste_avg,
        "taste_strong": strong,
        "taste_weak": weak,
        "taste_suggestions": taste_suggestions,
    }


# ═══════════════════════════════════════════════════════════════════
# DISH TEMPLATES — structural frameworks across every dish type
# Each template has a "dish_type" for filtering in the UI
# ═══════════════════════════════════════════════════════════════════

DISH_TYPES = [
    "Any", "One-Pot", "Pasta & Noodles", "Stir-Fry & Wok", "Curry & Stew",
    "Tacos & Wraps", "Bowl", "Soup", "Casserole & Bake", "Grilled & Seared",
    "Salad & Slaw", "Breakfast & Brunch", "Sandwich", "Pizza & Flatbread",
    "Dessert & Sweet", "Snack & Appetizer", "Sauce & Dip",
]

DISH_TEMPLATES = [
    # ──────────── ONE-POT ────────────
    {"name": "One-Pot {protein} with {vegetable}, {grain}, and {spice}",
     "dish_type": "One-Pot",
     "structure": {"protein": 1, "vegetable": 1, "grain": 1, "spice": 1},
     "technique": "Brown {protein} in the pot. Add diced {vegetable} and toast {spice}. Pour in stock, add {grain}, cover and simmer until everything is tender.",
     "needs": ["protein", "vegetable", "grain"]},
    {"name": "{protein} and {legume} Chili with {spice} and {vegetable}",
     "dish_type": "One-Pot",
     "structure": {"protein": 1, "legume": 1, "spice": 1, "vegetable": 1},
     "technique": "Brown {protein}, bloom {spice}. Add {legume}, diced {vegetable}, tomatoes. Simmer 45 min+, finish with lime and cilantro.",
     "needs": ["protein", "legume"]},
    {"name": "{fermented}-Braised {protein} with {vegetable} and {herb}",
     "dish_type": "One-Pot",
     "structure": {"fermented": 1, "protein": 1, "vegetable": 1, "herb": 1},
     "technique": "Brown {protein}, deglaze with {fermented}, add {vegetable}, braise low and slow. Finish with fresh {herb}.",
     "needs": ["protein", "vegetable"]},
    {"name": "{protein} and {vegetable} Pot Pie with {herb} Crust",
     "dish_type": "One-Pot",
     "structure": {"protein": 1, "vegetable": 1, "herb": 1},
     "technique": "Make creamy filling with {protein} and {vegetable}. Mix {herb} into pastry dough, top, and bake until golden and bubbling.",
     "needs": ["protein", "vegetable"]},
    {"name": "{protein} Jambalaya with {vegetable} and {spice}",
     "dish_type": "One-Pot",
     "structure": {"protein": 1, "vegetable": 1, "spice": 1},
     "technique": "Brown {protein}, sauté trinity + {vegetable}, toast {spice}, add rice and stock. Cook covered until rice absorbs liquid.",
     "needs": ["protein", "vegetable"]},
    {"name": "Smothered {vegetable} and {protein} Skillet with {cheese}",
     "dish_type": "One-Pot",
     "structure": {"vegetable": 1, "protein": 1, "cheese": 1},
     "technique": "Layer sliced {vegetable} and seared {protein} in cast iron. Smother with {cheese}, cover and cook until melted and bubbly.",
     "needs": ["protein", "vegetable"]},

    # ──────────── PASTA & NOODLES ────────────
    {"name": "{protein} and {vegetable} {noodle} with {cooking_sauce} and {cheese}",
     "dish_type": "Pasta & Noodles",
     "structure": {"protein": 1, "vegetable": 1, "noodle": 1, "cooking_sauce": 1, "cheese": 1},
     "technique": "Cook {noodle} al dente. Sauté {protein} and {vegetable}. Toss with {cooking_sauce} and pasta water. Finish with {cheese}.",
     "needs": ["protein", "vegetable"]},
    {"name": "{mushroom} and {herb} {noodle} with {cooking_sauce} and {cheese}",
     "dish_type": "Pasta & Noodles",
     "structure": {"mushroom": 1, "herb": 1, "noodle": 1, "cooking_sauce": 1, "cheese": 1},
     "technique": "Sauté {mushroom} until golden. Add {cooking_sauce}, simmer briefly. Toss with {noodle}, {herb}, and {cheese}.",
     "needs": ["mushroom"]},
    {"name": "Spicy {protein} Ramen with {vegetable} and {fermented}",
     "dish_type": "Pasta & Noodles",
     "structure": {"protein": 1, "vegetable": 1, "fermented": 1},
     "technique": "Build broth with {fermented} and aromatics. Cook ramen noodles. Top with seared {protein}, blanched {vegetable}, soft egg.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {nut} Pesto {noodle} with {cheese}",
     "dish_type": "Pasta & Noodles",
     "structure": {"vegetable": 1, "nut": 1, "noodle": 1, "cheese": 1},
     "technique": "Blend roasted {vegetable} with {nut}, olive oil, garlic into pesto. Toss with hot {noodle} and {cheese}.",
     "needs": ["vegetable", "nut"]},
    {"name": "{protein} Pad Thai with {nut} and {citrus}",
     "dish_type": "Pasta & Noodles",
     "structure": {"protein": 1, "nut": 1, "citrus": 1},
     "technique": "Soak rice noodles. Stir-fry {protein}, add noodles and pad thai sauce. Top with crushed {nut} and {citrus} wedge.",
     "needs": ["protein"]},
    {"name": "{protein} and {vegetable} {noodle} with {fermented}",
     "dish_type": "Pasta & Noodles",
     "structure": {"protein": 1, "vegetable": 1, "noodle": 1, "fermented": 1},
     "technique": "Cook {noodle}. Stir-fry {protein} and {vegetable} hot. Toss with noodles and {fermented}. Finish with sesame oil.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {cheese} Lasagna with {cooking_sauce} and {herb}",
     "dish_type": "Pasta & Noodles",
     "structure": {"vegetable": 1, "cheese": 1, "cooking_sauce": 1, "herb": 1},
     "technique": "Layer pasta sheets with {cooking_sauce}, roasted {vegetable}, {cheese}, and {herb}. Repeat layers. Bake until golden and bubbling.",
     "needs": ["vegetable"]},

    # ──────────── STIR-FRY & WOK ────────────
    {"name": "{protein} and {vegetable} Stir-Fry with {spice} and {fermented}",
     "dish_type": "Stir-Fry & Wok",
     "structure": {"protein": 1, "vegetable": 1, "spice": 1, "fermented": 1, "oil": 1},
     "technique": "Velvet {protein}. Wok-sear {vegetable} in {oil} over high heat. Add {protein} back with {spice} and {fermented} sauce. Serve over rice.",
     "needs": ["protein", "vegetable"]},
    {"name": "{protein} and {vegetable} Fried {rice_type} with {fermented}",
     "dish_type": "Stir-Fry & Wok",
     "structure": {"protein": 1, "vegetable": 1, "rice_type": 1, "fermented": 1, "oil": 1},
     "technique": "Use day-old {rice_type}. Scramble eggs in {oil}, push aside. Stir-fry diced {protein} and {vegetable}. Add rice, toss with {fermented}.",
     "needs": ["protein", "vegetable"]},
    {"name": "{fermented}-Glazed {protein} with {vegetable} and {nut}",
     "dish_type": "Stir-Fry & Wok",
     "structure": {"fermented": 1, "protein": 1, "vegetable": 1, "nut": 1, "oil": 1},
     "technique": "Stir-fry {protein} in {oil} until charred. Add {vegetable}. Glaze with {fermented}. Garnish with toasted {nut}.",
     "needs": ["protein", "vegetable"]},
    {"name": "Crispy {protein} with {vegetable} in {spice} Sauce",
     "dish_type": "Stir-Fry & Wok",
     "structure": {"protein": 1, "vegetable": 1, "spice": 1, "oil": 1},
     "technique": "Coat {protein} in cornstarch, deep fry in {oil} until crispy. Stir-fry {vegetable}. Toss everything in {spice} sauce.",
     "needs": ["protein", "vegetable"]},

    # ──────────── CURRY & STEW ────────────
    {"name": "{spice} {protein} Curry with {vegetable} and {herb}",
     "dish_type": "Curry & Stew",
     "structure": {"spice": 1, "protein": 1, "vegetable": 1, "herb": 1},
     "technique": "Bloom {spice} in oil. Brown {protein}. Add {vegetable} and coconut milk. Simmer until tender, finish with {herb}.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {legume} Curry with {spice}",
     "dish_type": "Curry & Stew",
     "structure": {"vegetable": 1, "legume": 1, "spice": 1},
     "technique": "Toast {spice}, sauté aromatics. Add {vegetable} and {legume} with tomatoes and coconut milk. Simmer 30 min. Serve with rice or naan.",
     "needs": ["vegetable", "legume"]},
    {"name": "{protein} Tagine with {fruit} and {spice}",
     "dish_type": "Curry & Stew",
     "structure": {"protein": 1, "fruit": 1, "spice": 1},
     "technique": "Brown {protein} with {spice} and onion. Add {fruit}, olives, and preserved lemon. Braise slowly until fork-tender.",
     "needs": ["protein", "fruit"]},
    {"name": "{protein} and {mushroom} Stew with {herb} and {grain}",
     "dish_type": "Curry & Stew",
     "structure": {"protein": 1, "mushroom": 1, "herb": 1, "grain": 1},
     "technique": "Brown {protein} in batches. Sauté {mushroom}. Combine in pot with stock and {herb}. Simmer 1hr+. Serve over {grain}.",
     "needs": ["protein", "mushroom"]},
    {"name": "{protein} Gumbo with {vegetable} and {spice}",
     "dish_type": "Curry & Stew",
     "structure": {"protein": 1, "vegetable": 1, "spice": 1},
     "technique": "Make dark roux. Cook trinity + {vegetable}. Add stock, {protein}, {spice}. Simmer long. Serve over rice with filé.",
     "needs": ["protein", "vegetable"]},

    # ──────────── TACOS & WRAPS ────────────
    {"name": "{spice}-Rubbed {protein} Tacos with {fruit} Salsa and {herb}",
     "dish_type": "Tacos & Wraps",
     "structure": {"spice": 1, "protein": 1, "fruit": 1, "herb": 1},
     "technique": "Rub {protein} with {spice}, cook until charred. Dice {fruit} into quick salsa with {herb}, onion, lime. Load into warm tortillas.",
     "needs": ["protein", "fruit"]},
    {"name": "{protein} Lettuce Wraps with {vegetable} and {fermented}",
     "dish_type": "Tacos & Wraps",
     "structure": {"protein": 1, "vegetable": 1, "fermented": 1},
     "technique": "Stir-fry minced {protein} with diced {vegetable} and {fermented} sauce. Spoon into crisp lettuce cups. Top with herbs and peanuts.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {cheese} Quesadillas with {accent} Crema",
     "dish_type": "Tacos & Wraps",
     "structure": {"vegetable": 1, "cheese": 1, "accent": 1},
     "technique": "Sauté {vegetable}. Fill tortillas with {cheese} and {vegetable}. Griddle until crispy. Mix {accent} into sour cream for dipping.",
     "needs": ["vegetable"]},
    {"name": "{protein} Burritos with {legume}, {vegetable}, and {cheese}",
     "dish_type": "Tacos & Wraps",
     "structure": {"protein": 1, "legume": 1, "vegetable": 1, "cheese": 1},
     "technique": "Season and cook {protein}. Warm {legume}. Assemble with {vegetable}, {cheese}, rice, salsa in large tortilla. Wrap tight.",
     "needs": ["protein", "legume", "vegetable"]},
    {"name": "Roasted {vegetable} Tacos with {nut} Crema and {spice}",
     "dish_type": "Tacos & Wraps",
     "structure": {"vegetable": 1, "nut": 1, "spice": 1},
     "technique": "Roast {vegetable} with {spice} until caramelized. Blend soaked {nut} into crema. Load tortillas, drizzle crema, garnish.",
     "needs": ["vegetable", "nut"]},

    # ──────────── BOWLS ────────────
    {"name": "{protein} Poke Bowl with {vegetable}, {fruit}, and {fermented}",
     "dish_type": "Bowl",
     "structure": {"protein": 1, "vegetable": 1, "fruit": 1, "fermented": 1},
     "technique": "Cube raw {protein}, marinate in {fermented}. Layer over rice with sliced {vegetable} and {fruit}. Drizzle with spicy mayo.",
     "needs": ["protein", "vegetable"]},
    {"name": "{protein} Bibimbap with {vegetable}, {fermented}, and {herb}",
     "dish_type": "Bowl",
     "structure": {"protein": 1, "vegetable": 1, "fermented": 1, "herb": 1},
     "technique": "Cook rice in stone bowl until crispy bottom. Arrange sautéed {vegetable}, {protein}, {herb}. Top with egg and {fermented} sauce.",
     "needs": ["protein", "vegetable"]},
    {"name": "{grain} Bowl with Roasted {vegetable}, {nut}, and {dressing} Dressing",
     "dish_type": "Bowl",
     "structure": {"grain": 1, "vegetable": 1, "nut": 1, "dressing": 1},
     "technique": "Cook {grain}. Roast {vegetable}. Toast {nut}. Whisk {dressing} into tahini dressing. Compose bowl, drizzle generously.",
     "needs": ["grain", "vegetable"]},
    {"name": "{mushroom} and {grain} Bowl with {dressing} Dressing",
     "dish_type": "Bowl",
     "structure": {"mushroom": 1, "grain": 1, "dressing": 1},
     "technique": "Sauté {mushroom} hot. Cook {grain}. Whisk {dressing} into dressing. Compose bowl.",
     "needs": ["mushroom", "grain"]},
    {"name": "{protein} {rice_type} Bowl with {vegetable}, {spice}, and {citrus}",
     "dish_type": "Bowl",
     "structure": {"protein": 1, "rice_type": 1, "vegetable": 1, "spice": 1, "citrus": 1},
     "technique": "Cook {rice_type}. Season {protein} with {spice}, cook. Quick-pickle {vegetable}. Layer over rice with {citrus} juice, herbs, and sauce.",
     "needs": ["protein", "vegetable"]},

    # ──────────── SOUP ────────────
    # Cream/Purée soups
    {"name": "Creamy {vegetable} Soup with {broth}, {spice}, and {garnish}",
     "dish_type": "Soup",
     "structure": {"vegetable": 1, "broth": 1, "spice": 1, "garnish": 1},
     "technique": "Sweat aromatics, add {vegetable}, toast {spice}. Cover with {broth}, simmer until tender. Blend smooth. Top with {garnish}.",
     "needs": ["vegetable"]},
    {"name": "{vegetable} Bisque with {broth} and {herb}",
     "dish_type": "Soup",
     "structure": {"vegetable": 1, "broth": 1, "herb": 1},
     "technique": "Roast {vegetable} until caramelized. Simmer in {broth} with aromatics. Blend silky smooth, finish with cream and {herb}.",
     "needs": ["vegetable"]},
    # Chowders
    {"name": "{protein} Chowder with {vegetable}, {broth}, and {herb}",
     "dish_type": "Soup",
     "structure": {"protein": 1, "vegetable": 1, "broth": 1, "herb": 1},
     "technique": "Render bacon or butter. Sauté diced {vegetable}. Add {broth} and cream, simmer. Add {protein} chunks, cook through. Finish with {herb}.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {cheese} Chowder with {broth}",
     "dish_type": "Soup",
     "structure": {"vegetable": 1, "cheese": 1, "broth": 1},
     "technique": "Dice {vegetable}, simmer in {broth} until tender. Add cream, melt in {cheese}. Season well, serve thick and creamy.",
     "needs": ["vegetable"]},
    # Clear/brothy soups
    {"name": "{protein} and {legume} Soup with {broth} and {spice}",
     "dish_type": "Soup",
     "structure": {"protein": 1, "legume": 1, "broth": 1, "spice": 1},
     "technique": "Brown {protein}. Sauté mirepoix with {spice}. Add {legume} and {broth}. Simmer 45 min until {legume} is tender.",
     "needs": ["protein", "legume"]},
    {"name": "{protein} Noodle Soup with {broth}, {vegetable}, and {herb}",
     "dish_type": "Soup",
     "structure": {"protein": 1, "broth": 1, "vegetable": 1, "herb": 1},
     "technique": "Simmer {protein} in {broth} until cooked. Add {vegetable} and noodles. Ladle into bowls, finish with {herb}.",
     "needs": ["protein", "vegetable"]},
    # Asian soups
    {"name": "{protein} Pho with {broth}, {herb}, and {citrus}",
     "dish_type": "Soup",
     "structure": {"protein": 1, "broth": 1, "herb": 1, "citrus": 1},
     "technique": "Toast spices, build aromatic {broth}. Cook rice noodles. Slice {protein} thin. Assemble in bowls with {herb} and {citrus}.",
     "needs": ["protein"]},
    {"name": "{protein} Ramen with {broth}, {vegetable}, and {fermented}",
     "dish_type": "Soup",
     "structure": {"protein": 1, "broth": 1, "vegetable": 1, "fermented": 1},
     "technique": "Build rich {broth}, season with {fermented}. Cook ramen noodles. Top with {protein}, {vegetable}, soft egg, and nori.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {mushroom} Miso Soup with {broth}",
     "dish_type": "Soup",
     "structure": {"vegetable": 1, "mushroom": 1, "broth": 1},
     "technique": "Warm {broth}. Dissolve miso paste. Add sliced {mushroom} and {vegetable}. Simmer gently — don't boil. Garnish with green onion.",
     "needs": ["vegetable", "mushroom"]},
    {"name": "{protein} Tom Yum with {broth}, {mushroom}, and {citrus}",
     "dish_type": "Soup",
     "structure": {"protein": 1, "broth": 1, "mushroom": 1, "citrus": 1},
     "technique": "Simmer {broth} with lemongrass, galangal, and chili. Add {mushroom} and {protein}. Finish with {citrus} juice and fish sauce.",
     "needs": ["protein", "mushroom"]},
    # Stew-like soups
    {"name": "{protein} and {vegetable} Stew with {broth} and {spice}",
     "dish_type": "Soup",
     "structure": {"protein": 1, "vegetable": 1, "broth": 1, "spice": 1},
     "technique": "Brown {protein} in batches. Sauté {vegetable} with {spice}. Deglaze with {broth}. Braise low and slow until fork-tender.",
     "needs": ["protein", "vegetable"]},
    # Cold soups
    {"name": "Chilled {vegetable} and {fruit} Gazpacho with {herb}",
     "dish_type": "Soup",
     "structure": {"vegetable": 1, "fruit": 1, "herb": 1},
     "technique": "Blend raw {vegetable} and {fruit} with olive oil, vinegar, and garlic. Chill at least 2 hours. Serve cold with {herb} and croutons.",
     "needs": ["vegetable", "fruit"]},
    # Wonton/dumpling soups
    {"name": "{protein} Wonton Soup with {broth}, {vegetable}, and {herb}",
     "dish_type": "Soup",
     "structure": {"protein": 1, "broth": 1, "vegetable": 1, "herb": 1},
     "technique": "Make {protein} filling, wrap in wonton skins. Simmer {broth} with {vegetable}. Drop in wontons, cook 3 min. Garnish with {herb}.",
     "needs": ["protein", "vegetable"]},

    # ──────────── CASSEROLE & BAKE ────────────
    {"name": "{protein} and {vegetable} Casserole with {cheese} and {herb}",
     "dish_type": "Casserole & Bake",
     "structure": {"protein": 1, "vegetable": 1, "cheese": 1, "herb": 1},
     "technique": "Layer {protein} and {vegetable} in baking dish. Pour {cheese} sauce over. Top with {herb} breadcrumbs. Bake 350°F 40 min.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {cheese} Gratin with {herb}",
     "dish_type": "Casserole & Bake",
     "structure": {"vegetable": 1, "cheese": 1, "herb": 1},
     "technique": "Slice {vegetable} thin. Layer with {cheese} béchamel and {herb}. Bake until golden and bubbling.",
     "needs": ["vegetable"]},
    {"name": "{protein} and {vegetable} Enchiladas with {cooking_sauce} and {cheese}",
     "dish_type": "Casserole & Bake",
     "structure": {"protein": 1, "vegetable": 1, "cooking_sauce": 1, "cheese": 1},
     "technique": "Shred cooked {protein}, mix with {vegetable}. Roll in tortillas, line in pan. Cover with {cooking_sauce} and {cheese}. Bake until bubbly.",
     "needs": ["protein", "vegetable"]},
    {"name": "Baked Pasta with {protein}, {vegetable}, {cooking_sauce}, and {cheese}",
     "dish_type": "Casserole & Bake",
     "structure": {"protein": 1, "vegetable": 1, "cooking_sauce": 1, "cheese": 1},
     "technique": "Toss cooked pasta with {cooking_sauce}, {protein}, and {vegetable}. Top with {cheese}. Bake at 375°F until bubbly and browned.",
     "needs": ["protein", "vegetable"]},
    {"name": "Stuffed {vegetable} with {protein}, {grain}, and {cheese}",
     "dish_type": "Casserole & Bake",
     "structure": {"vegetable": 1, "protein": 1, "grain": 1, "cheese": 1},
     "technique": "Hollow out {vegetable}. Mix {protein} with cooked {grain} and {cheese}. Stuff, top with more {cheese}, bake until tender.",
     "needs": ["vegetable", "protein", "grain"]},
    {"name": "{protein} Shepherd's Pie with {vegetable} and {herb}",
     "dish_type": "Casserole & Bake",
     "structure": {"protein": 1, "vegetable": 1, "herb": 1},
     "technique": "Brown {protein} with {vegetable} and {herb} in gravy. Top with mashed potato. Broil until golden peaks form.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {mushroom} Quiche with {cheese} and {herb}",
     "dish_type": "Casserole & Bake",
     "structure": {"vegetable": 1, "mushroom": 1, "cheese": 1, "herb": 1},
     "technique": "Blind-bake pie crust. Sauté {mushroom} and {vegetable}. Mix with eggs, cream, {cheese}, {herb}. Pour in, bake 375°F 35 min.",
     "needs": ["vegetable", "mushroom"]},
    # ── Mac & Cheese ──
    {"name": "{noodle} and {cheese} Mac with {protein} and {spice}",
     "dish_type": "Casserole & Bake",
     "structure": {"noodle": 1, "cheese": 1, "protein": 1, "spice": 1},
     "technique": "Cook {noodle}. Make {cheese} sauce with butter, flour, milk. Add {spice}. Toss with {protein}. Top with breadcrumbs. Bake until bubbly.",
     "needs": ["protein"]},
    {"name": "Baked {noodle} and {cheese} with {vegetable} and {herb}",
     "dish_type": "Casserole & Bake",
     "structure": {"noodle": 1, "cheese": 1, "vegetable": 1, "herb": 1},
     "technique": "Cook {noodle}. Make {cheese} béchamel. Fold in roasted {vegetable}. Pour into dish, top with more {cheese} and {herb} breadcrumbs. Bake golden.",
     "needs": ["vegetable"]},

    # ──────────── GRILLED & SEARED ────────────
    {"name": "Glazed {protein} with Roasted {vegetable} and {accent}",
     "dish_type": "Grilled & Seared",
     "structure": {"protein": 1, "vegetable": 1, "accent": 1},
     "technique": "Pan-sear {protein}, build a glaze with {accent}, roast {vegetable} alongside.",
     "needs": ["protein", "vegetable"]},
    {"name": "{nut}-Crusted {protein} with {vegetable} Purée",
     "dish_type": "Grilled & Seared",
     "structure": {"nut": 1, "protein": 1, "vegetable": 1},
     "technique": "Pulse {nut} into crust, press onto {protein}, bake. Purée roasted {vegetable} smooth.",
     "needs": ["nut", "protein", "vegetable"]},
    {"name": "{fruit} Gastrique over {protein} with {herb}",
     "dish_type": "Grilled & Seared",
     "structure": {"fruit": 1, "protein": 1, "herb": 1},
     "technique": "Reduce {fruit} with vinegar into gastrique. Sear {protein}, spoon sauce over, finish with {herb}.",
     "needs": ["fruit", "protein"]},
    {"name": "{protein} Skewers with {nut} Sauce and {herb}",
     "dish_type": "Grilled & Seared",
     "structure": {"protein": 1, "nut": 1, "herb": 1},
     "technique": "Thread {protein} onto skewers, grill. Blend {nut} into creamy sauce. Serve scattered with {herb}.",
     "needs": ["protein", "nut"]},
    {"name": "Smoked {protein} with {fruit} Glaze and {vegetable} Hash",
     "dish_type": "Grilled & Seared",
     "structure": {"protein": 1, "fruit": 1, "vegetable": 1},
     "technique": "Smoke {protein} low. Reduce {fruit} into sticky glaze. Crisp diced {vegetable} into hash. Plate together.",
     "needs": ["protein", "fruit", "vegetable"]},
    {"name": "{spice}-Rubbed {protein} with Charred {vegetable}",
     "dish_type": "Grilled & Seared",
     "structure": {"spice": 1, "protein": 1, "vegetable": 1},
     "technique": "Rub {protein} with {spice} blend, grill or sear. Char {vegetable} on high heat until blistered. Serve together.",
     "needs": ["protein", "vegetable"]},
    # ── Fried Chicken / Crispy ──
    {"name": "{spice}-Fried {protein} with {cooking_sauce} and {vegetable}",
     "dish_type": "Grilled & Seared",
     "structure": {"spice": 1, "protein": 1, "cooking_sauce": 1, "vegetable": 1},
     "technique": "Season {protein} with {spice}. Dredge in flour, buttermilk, flour again. Deep fry until golden and 165°F. Serve with {cooking_sauce} and {vegetable} slaw.",
     "needs": ["protein", "vegetable"]},

    # ──────────── SALAD & SLAW ────────────
    {"name": "{fruit} and {herb} Salad with {cheese}",
     "dish_type": "Salad & Slaw",
     "structure": {"fruit": 1, "herb": 1, "cheese": 1, "oil": 1},
     "technique": "Slice {fruit} thin, toss with torn {herb} leaves, shave {cheese} over, dress lightly.",
     "needs": ["fruit"]},
    {"name": "{fruit} and {vegetable} Slaw with {spice} Vinaigrette",
     "dish_type": "Salad & Slaw",
     "structure": {"fruit": 1, "vegetable": 1, "spice": 1, "oil": 1},
     "technique": "Shred {vegetable} and slice {fruit} thin. Toast {spice}, whisk into a {oil} vinaigrette. Toss and rest.",
     "needs": ["fruit", "vegetable"]},
    {"name": "{grain} Salad with {fruit}, {herb}, and {nut}",
     "dish_type": "Salad & Slaw",
     "structure": {"grain": 1, "fruit": 1, "herb": 1, "nut": 1, "oil": 1},
     "technique": "Cook {grain} and cool. Toss with diced {fruit}, chopped {herb}, and toasted {nut}. Dress with citrus vinaigrette.",
     "needs": ["grain", "fruit"]},
    {"name": "{protein} and {vegetable} Salad with {citrus} Dressing and {nut}",
     "dish_type": "Salad & Slaw",
     "structure": {"protein": 1, "vegetable": 1, "citrus": 1, "nut": 1, "oil": 1},
     "technique": "Grill or poach {protein}. Toss greens with shaved {vegetable}. Dress with {citrus}. Scatter toasted {nut}.",
     "needs": ["protein", "vegetable"]},
    # ── Ceviche ──
    {"name": "{protein} Ceviche with {citrus}, {vegetable}, and {herb}",
     "dish_type": "Salad & Slaw",
     "structure": {"protein": 1, "citrus": 1, "vegetable": 1, "herb": 1},
     "technique": "Dice {protein} small. Cure in {citrus} juice 20-30 min until opaque. Fold in diced {vegetable} and {herb}. Season, serve cold with chips.",
     "needs": ["protein", "vegetable"]},

    # ──────────── BREAKFAST & BRUNCH ────────────
    {"name": "{vegetable} and {cheese} Frittata with {herb}",
     "dish_type": "Breakfast & Brunch",
     "structure": {"vegetable": 1, "cheese": 1, "herb": 1},
     "technique": "Sauté {vegetable}. Pour whisked eggs with {cheese} and {herb} over top. Cook stovetop, finish under broiler.",
     "needs": ["vegetable"]},
    {"name": "{protein} and {vegetable} Shakshuka with {spice} and {herb}",
     "dish_type": "Breakfast & Brunch",
     "structure": {"protein": 1, "vegetable": 1, "spice": 1, "herb": 1},
     "technique": "Sauté {vegetable} with {spice} and tomato. Make wells, crack eggs. Add crumbled {protein}. Cover and cook. Top with {herb}.",
     "needs": ["vegetable"]},
    {"name": "{vegetable} and {protein} Hash with {spice}",
     "dish_type": "Breakfast & Brunch",
     "structure": {"vegetable": 1, "protein": 1, "spice": 1},
     "technique": "Dice and par-cook {vegetable}. Crisp with {protein} and {spice} in cast iron. Top with fried eggs.",
     "needs": ["vegetable", "protein"]},
    {"name": "Savory {grain} Porridge with {mushroom}, {herb}, and {cheese}",
     "dish_type": "Breakfast & Brunch",
     "structure": {"grain": 1, "mushroom": 1, "herb": 1, "cheese": 1},
     "technique": "Simmer {grain} in stock until creamy. Top with sautéed {mushroom}, {cheese}, and fresh {herb}. Drizzle good olive oil.",
     "needs": ["grain", "mushroom"]},
    {"name": "{grain} Porridge with {sweetener}, {spice}, and {nut}",
     "dish_type": "Breakfast & Brunch",
     "structure": {"grain": 1, "sweetener": 1, "spice": 1, "nut": 1},
     "technique": "Simmer {grain} until creamy. Swirl in {sweetener} and {spice}. Top with toasted {nut}.",
     "needs": ["grain"]},

    # ──────────── SANDWICH ────────────
    {"name": "{protein} and {vegetable} Sandwich on {bread} with {cheese} and {accent}",
     "dish_type": "Sandwich",
     "structure": {"protein": 1, "vegetable": 1, "bread": 1, "cheese": 1, "accent": 1},
     "technique": "Slice or pull {protein}. Layer on {bread} with {vegetable}, melted {cheese}, and {accent} spread. Press or toast.",
     "needs": ["protein", "vegetable"]},
    {"name": "{vegetable} and {cheese} Panini on {bread} with {herb} Pesto",
     "dish_type": "Sandwich",
     "structure": {"vegetable": 1, "cheese": 1, "bread": 1, "herb": 1},
     "technique": "Spread {herb} pesto on {bread}. Layer roasted {vegetable} and {cheese}. Press in panini grill until golden.",
     "needs": ["vegetable"]},
    {"name": "{protein} Melt on {bread} with {mushroom} and {cheese}",
     "dish_type": "Sandwich",
     "structure": {"protein": 1, "mushroom": 1, "bread": 1, "cheese": 1},
     "technique": "Sauté {mushroom}. Layer with sliced {protein} and {cheese} on {bread}. Griddle until cheese melts.",
     "needs": ["protein", "mushroom"]},
    # ── Burgers ──
    {"name": "{protein} Burger on {bread} with {cheese}, {vegetable}, and {cooking_sauce}",
     "dish_type": "Sandwich",
     "structure": {"protein": 1, "bread": 1, "cheese": 1, "vegetable": 1, "cooking_sauce": 1},
     "technique": "Form {protein} into patties, season well. Sear or grill until done. Toast {bread} bun. Stack with {cheese}, {vegetable}, and {cooking_sauce}.",
     "needs": ["protein", "vegetable"]},
    {"name": "{spice}-Seasoned {protein} Burger on {bread} with {cheese} and {accent}",
     "dish_type": "Sandwich",
     "structure": {"protein": 1, "bread": 1, "cheese": 1, "spice": 1, "accent": 1},
     "technique": "Mix {spice} into {protein}, form patties. Grill or smash on griddle. Melt {cheese} on top. Serve on toasted {bread} with {accent}.",
     "needs": ["protein"]},
    {"name": "Stuffed {protein} Burger on {bread} with {cheese} and {vegetable}",
     "dish_type": "Sandwich",
     "structure": {"protein": 1, "bread": 1, "cheese": 1, "vegetable": 1},
     "technique": "Stuff {cheese} inside {protein} patty, seal edges. Grill until cheese melts inside. Serve on {bread} with {vegetable} and pickles.",
     "needs": ["protein", "vegetable"]},

    # ──────────── PIZZA & FLATBREAD ────────────
    {"name": "{vegetable} and {cheese} Flatbread with {cooking_sauce} and {herb}",
     "dish_type": "Pizza & Flatbread",
     "structure": {"vegetable": 1, "cheese": 1, "cooking_sauce": 1, "herb": 1},
     "technique": "Spread {cooking_sauce} on flatbread. Top with {cheese} and sliced {vegetable}. Bake at 450°F until bubbly. Finish with fresh {herb}.",
     "needs": ["vegetable"]},
    {"name": "{protein} and {vegetable} Pizza with {cooking_sauce}, {cheese}, and {spice}",
     "dish_type": "Pizza & Flatbread",
     "structure": {"protein": 1, "vegetable": 1, "cooking_sauce": 1, "cheese": 1, "spice": 1},
     "technique": "Stretch dough. Spread {cooking_sauce}, then {cheese}. Top with {protein} and {vegetable}. Dust with {spice}. Bake at highest oven temp.",
     "needs": ["protein", "vegetable"]},
    {"name": "{fruit} and {cheese} Flatbread with {herb} and {sweetener}",
     "dish_type": "Pizza & Flatbread",
     "structure": {"fruit": 1, "cheese": 1, "herb": 1, "sweetener": 1},
     "technique": "Top flatbread with {cheese}. Add sliced {fruit}. Bake until bubbly. Drizzle {sweetener}, scatter {herb}.",
     "needs": ["fruit"]},
    {"name": "White Pizza with {cheese}, {vegetable}, and {herb}",
     "dish_type": "Pizza & Flatbread",
     "structure": {"cheese": 1, "vegetable": 1, "herb": 1},
     "technique": "Spread ricotta or cream base on dough. Layer {cheese} and {vegetable}. Bake at 475°F until charred. Finish with {herb} and olive oil.",
     "needs": ["vegetable"]},
    {"name": "{mushroom} and {cheese} Pizza with {cooking_sauce} and {allium}",
     "dish_type": "Pizza & Flatbread",
     "structure": {"mushroom": 1, "cheese": 1, "cooking_sauce": 1, "allium": 1},
     "technique": "Spread {cooking_sauce} on dough. Sauté {mushroom} with {allium} until golden, scatter on top with {cheese}. Bake until crisp.",
     "needs": ["mushroom"]},
    {"name": "{protein} Calzone with {cooking_sauce}, {vegetable}, and {cheese}",
     "dish_type": "Pizza & Flatbread",
     "structure": {"protein": 1, "cooking_sauce": 1, "vegetable": 1, "cheese": 1},
     "technique": "Spread {cooking_sauce} on half the dough. Fill with {protein}, {vegetable}, and {cheese}. Fold, crimp, and bake until golden. Serve with extra {cooking_sauce}.",
     "needs": ["protein", "vegetable"]},
    {"name": "{spice} {protein} Naan Pizza with {cooking_sauce}, {vegetable}, and {cheese}",
     "dish_type": "Pizza & Flatbread",
     "structure": {"spice": 1, "protein": 1, "cooking_sauce": 1, "vegetable": 1, "cheese": 1},
     "technique": "Season {protein} with {spice}, cook through. Spread {cooking_sauce} on naan, add {protein}, {vegetable}, and {cheese}. Broil until bubbly.",
     "needs": ["protein", "vegetable"]},

    # ──────────── DESSERT & SWEET ────────────
    {"name": "{spice} and {nut} Crumble over {fruit}",
     "dish_type": "Dessert & Sweet",
     "structure": {"spice": 1, "nut": 1, "fruit": 1},
     "technique": "Toss {fruit} with sugar and {spice}. Make crumble topping with crushed {nut}. Bake until bubbling.",
     "needs": ["fruit", "nut"]},
    {"name": "{fruit} Panna Cotta with {spice} and {sweetener}",
     "dish_type": "Dessert & Sweet",
     "structure": {"fruit": 1, "spice": 1, "sweetener": 1},
     "technique": "Infuse cream with {spice}. Set with gelatin. Unmold and top with macerated {fruit} and a drizzle of {sweetener}.",
     "needs": ["fruit"]},
    {"name": "{spice}-Infused {sweetener} with {fruit} and {nut}",
     "dish_type": "Dessert & Sweet",
     "structure": {"spice": 1, "sweetener": 1, "fruit": 1, "nut": 1},
     "technique": "Warm {sweetener} with {spice} until fragrant. Pour over fresh {fruit}. Scatter toasted {nut}.",
     "needs": ["fruit"]},
    {"name": "{nut} and {fruit} Tart with {spice} Custard",
     "dish_type": "Dessert & Sweet",
     "structure": {"nut": 1, "fruit": 1, "spice": 1},
     "technique": "Press ground {nut} into tart shell. Fill with {spice}-infused custard. Arrange {fruit} on top. Bake until set.",
     "needs": ["fruit", "nut"]},
    {"name": "{fruit} and {herb} Sorbet",
     "dish_type": "Dessert & Sweet",
     "structure": {"fruit": 1, "herb": 1},
     "technique": "Purée {fruit} with simple syrup and muddled {herb}. Churn in ice cream maker or freeze-and-stir method.",
     "needs": ["fruit"]},
    {"name": "{sweetener} and {spice} Roasted {fruit} with {cheese}",
     "dish_type": "Dessert & Sweet",
     "structure": {"sweetener": 1, "spice": 1, "fruit": 1, "cheese": 1},
     "technique": "Halve {fruit}, drizzle with {sweetener}, dust with {spice}. Roast until caramelized. Serve with dollop of {cheese}.",
     "needs": ["fruit"]},

    # ──────────── SNACK & APPETIZER ────────────
    {"name": "{vegetable} Carpaccio with {nut} Pesto and {cheese}",
     "dish_type": "Snack & Appetizer",
     "structure": {"vegetable": 1, "nut": 1, "cheese": 1},
     "technique": "Shave {vegetable} paper-thin. Blend {nut} with herbs into pesto. Drizzle over, shave {cheese}.",
     "needs": ["vegetable", "nut"]},
    {"name": "Crispy {legume} Fritters with {herb} and {citrus} Aioli",
     "dish_type": "Snack & Appetizer",
     "structure": {"legume": 1, "herb": 1, "citrus": 1},
     "technique": "Mash cooked {legume}, fold in {herb}, shape and fry until crisp. Blend {citrus} zest into aioli.",
     "needs": ["legume"]},
    {"name": "{cheese}-Stuffed {vegetable} with {herb} and {spice}",
     "dish_type": "Snack & Appetizer",
     "structure": {"cheese": 1, "vegetable": 1, "herb": 1, "spice": 1},
     "technique": "Hollow {vegetable}. Mix {cheese} with {herb} and {spice}. Stuff. Bake or fry until golden.",
     "needs": ["vegetable"]},
    {"name": "{protein} and {vegetable} Spring Rolls with {fermented} Dip",
     "dish_type": "Snack & Appetizer",
     "structure": {"protein": 1, "vegetable": 1, "fermented": 1},
     "technique": "Julienne {vegetable}, slice {protein}. Roll in rice paper with herbs and vermicelli. Serve with {fermented} dipping sauce.",
     "needs": ["protein", "vegetable"]},
    # ── Wings ──
    {"name": "{cooking_sauce} {protein} Wings with {vegetable} and {herb}",
     "dish_type": "Snack & Appetizer",
     "structure": {"cooking_sauce": 1, "protein": 1, "vegetable": 1, "herb": 1},
     "technique": "Bake or fry {protein} wings until crispy. Toss in {cooking_sauce}. Serve with {vegetable} sticks, {herb}, and ranch or blue cheese.",
     "needs": ["protein"]},
    # ── Nachos ──
    {"name": "Loaded {protein} Nachos with {cheese}, {cooking_sauce}, and {vegetable}",
     "dish_type": "Snack & Appetizer",
     "structure": {"protein": 1, "cheese": 1, "cooking_sauce": 1, "vegetable": 1},
     "technique": "Layer tortilla chips with seasoned {protein}, {cheese}, and {cooking_sauce}. Bake until melty. Top with {vegetable}, sour cream, and cilantro.",
     "needs": ["protein", "vegetable"]},
    # ── Dumplings ──
    {"name": "{protein} and {vegetable} Dumplings with {fermented} Dipping Sauce",
     "dish_type": "Snack & Appetizer",
     "structure": {"protein": 1, "vegetable": 1, "fermented": 1},
     "technique": "Mince {protein} and {vegetable} into filling with ginger and garlic. Wrap in dumpling skins. Steam or pan-fry. Serve with {fermented} dip.",
     "needs": ["protein", "vegetable"]},
    # ── Empanadas ──
    {"name": "{protein} and {vegetable} Empanadas with {spice} and {cheese}",
     "dish_type": "Snack & Appetizer",
     "structure": {"protein": 1, "vegetable": 1, "spice": 1, "cheese": 1},
     "technique": "Cook {protein} with {vegetable} and {spice}. Fill dough circles with mixture and {cheese}. Crimp, brush with egg. Bake until golden.",
     "needs": ["protein", "vegetable"]},
    # ── Loaded Fries ──
    {"name": "Loaded {vegetable} Fries with {protein}, {cheese}, and {cooking_sauce}",
     "dish_type": "Snack & Appetizer",
     "structure": {"vegetable": 1, "protein": 1, "cheese": 1, "cooking_sauce": 1},
     "technique": "Cut {vegetable} into fries, bake or fry until crispy. Top with {protein}, melted {cheese}, and {cooking_sauce}. Garnish.",
     "needs": ["vegetable", "protein"]},

    # ──────────── SAUCE & DIP ────────────
    {"name": "Roasted {vegetable} and {nut} Dip with {spice}",
     "dish_type": "Sauce & Dip",
     "structure": {"vegetable": 1, "nut": 1, "spice": 1},
     "technique": "Roast {vegetable} until soft. Blend with {nut} butter, {spice}, lemon, garlic. Drizzle oil, serve with flatbread.",
     "needs": ["vegetable", "nut"]},
    {"name": "{herb} and {nut} Pesto",
     "dish_type": "Sauce & Dip",
     "structure": {"herb": 1, "nut": 1},
     "technique": "Blend {herb} with toasted {nut}, garlic, parmesan, olive oil. Season. Use on pasta, sandwiches, or as dip.",
     "needs": ["herb", "nut"]},
    {"name": "{fruit} and {spice} Chutney",
     "dish_type": "Sauce & Dip",
     "structure": {"fruit": 1, "spice": 1},
     "technique": "Dice {fruit}, simmer with {spice}, vinegar, sugar, onion until jammy. Cool. Serve with cheese, meat, or flatbread.",
     "needs": ["fruit"]},
]

# ═══════════════════════════════════════════════════════════════════
# PAIRING ENGINE
# ═══════════════════════════════════════════════════════════════════

SLOT_CAT_MAP = {
    "protein": ["protein", "seafood"],
    "vegetable": ["vegetable"],
    "fruit": ["fruit", "citrus"],
    "herb": ["herb"],
    "spice": ["spice"],
    "cheese": ["dairy"],
    "garnish": ["herb", "nut", "spice"],
    "accent": ["spice", "fermented", "sweetener", "citrus"],
    "nut": ["nut"],
    "mushroom": ["mushroom"],
    "grain": ["grain"],
    "fermented": ["fermented"],
    "legume": ["legume"],
    "citrus": ["citrus"],
    "sweetener": ["sweetener"],
    "allium": ["allium"],
    # NOTE: no bare "sauce" slot. Sauce-category ingredients are reached
    # through the broth / cooking_sauce / dressing subtypes below, which
    # is the distinction that matters: a stock is not a pizza sauce is
    # not a vinaigrette. A generic slot mixing all three could put a
    # chicken stock on a pizza. All 24 stay reachable via the subtypes.
    # Used by the stir-fry and salad templates, where WHICH fat you reach for
    # is itself a flavour decision (sesame vs coconut vs olive changes the
    # dish). Everywhere else fat stays an assumed staple that the AI prompt
    # tells the model to add. This slot was declared and used by no template
    # at all through v3.0, which made all three oils unreachable.
    "oil": ["oil/fat"],
    # Grain subtypes — filter to specific grain sets
    "noodle": ["grain"],
    "bread": ["grain"],
    "rice_type": ["grain"],
    # Broth subtype — filter to stock/broth ingredients
    "broth": ["sauce"],
    # Cooking sauce (not stocks) for pizza/pasta/casserole
    "cooking_sauce": ["sauce"],
    # Dressing — fermented condiments suitable for bowls/salads
    "dressing": ["fermented"],
}

# Slot subtypes that come from an explicit ingredient set rather than from a
# category. A stock is not a pizza sauce is not a vinaigrette, and flour is not
# something to serve as the grain.
_SLOT_SUBSETS = {
    "noodle": GRAIN_NOODLES,
    "bread": GRAIN_BREADS,
    "rice_type": GRAIN_RICE,
    "grain": EDIBLE_GRAINS,       # excludes flour and cornstarch on purpose
    "broth": BROTH_TYPES,
    "cooking_sauce": COOKING_SAUCES,
    "dressing": DRESSINGS,
}

_SLOT_CANDIDATES: Dict[str, List[str]] = {}


def _compute_slot_candidates(slot: str) -> List[str]:
    if slot in _SLOT_SUBSETS:
        return sorted(n for n in _SLOT_SUBSETS[slot] if n in INGREDIENTS)
    valid_cats = SLOT_CAT_MAP.get(slot, list(CATEGORIES.keys()))
    return sorted(n for n, i in INGREDIENTS.items() if i.category in valid_cats)


def slot_candidates_cached(slot: str) -> List[str]:
    """Every ingredient a slot can hold, computed once per slot.

    generate_recipe tries 60 templates per call and surprise_me calls it 40
    times, so this was rebuilt roughly 8,700 times per Surprise Me — each a
    full scan of all 303 ingredients, and 57% of the wall time of the whole
    operation. The database is immutable at runtime, so once is enough.
    """
    cached = _SLOT_CANDIDATES.get(slot)
    if cached is None:
        cached = _compute_slot_candidates(slot)
        _SLOT_CANDIDATES[slot] = cached
    return cached


_SLOT_CANDIDATE_SETS: Dict[str, Set[str]] = {}


def slot_candidate_set(slot: str) -> Set[str]:
    """Membership-test form of the above, for "can this slot hold X"."""
    cached = _SLOT_CANDIDATE_SETS.get(slot)
    if cached is None:
        cached = set(slot_candidates_cached(slot))
        _SLOT_CANDIDATE_SETS[slot] = cached
    return cached


def get_slot_candidates(slot: str, exclude: set = None) -> List[str]:
    """Valid ingredient keys for a template slot, handling subtypes."""
    candidates = slot_candidates_cached(slot)
    if not exclude:
        return list(candidates)
    return [n for n in candidates if n not in exclude]


class FlavorEngine:
    """Core engine for computing flavor pairings and generating recipes."""

    def __init__(self):
        self.ingredients = INGREDIENTS
        self.compounds = COMPOUNDS

        # Pre-compute compound frequency for weighted_similarity (big perf win)
        self._compound_freq = defaultdict(int)
        for ing in self.ingredients.values():
            for c in ing.compounds:
                self._compound_freq[c] += 1
        self._total_ings = len(self.ingredients)

        # Pre-compute boring compounds for prompt generation
        self._boring_compounds = {
            c for c, count in self._compound_freq.items()
            if count > self._total_ings * 0.30
        }

        # Per-compound weights, computed once. See _compound_weight.
        self._weight = {c: self._compound_weight(c) for c in self._compound_freq}
        self._max_weight = max(self._weight.values()) if self._weight else 1.0

    def _compound_weight(self, compound: str) -> float:
        """How much a shared compound is worth, by how rare it is.

        Inverse document frequency, log(N / freq), which is the standard answer
        to "this term appears everywhere, so its presence tells me nothing".

        The previous formula was ``0.5 + 0.5 * (1 - freq/N)``. Monotonic, and
        so superficially correct, but the constant floor dominated the rarity
        term: hexanal, present in 63% of the database, scored 0.68 against a
        ceiling of 1.0 — 70% of what a compound found in a single ingredient
        was worth. Sharing a near-universal green note counted almost as much
        as sharing geosmin.

        What that cost, measured before the change: of the 31,387 ingredient
        pairs the app reported as connected, 16,501 — 52.6% — shared nothing
        but hexanal, linalool or nonanal. Over half of every "pairing" in the
        app was three compounds that are in almost everything.

        Under IDF hexanal falls to about 8% of geosmin's weight and those pairs
        drop out of the rankings on their own, without a hand-tuned exclusion
        list. The README's claim — "sharing a common compound like hexanal
        scores low" — is now true of the code.
        """
        freq = self._compound_freq.get(compound, 0)
        if freq <= 0:
            return 0.0
        return math.log(self._total_ings / freq)

    def jaccard_similarity(self, set_a: Set[str], set_b: Set[str]) -> float:
        """Plain Jaccard: |A n B| / |A u B|, every compound counted equally.

        Kept because it is the honest baseline the weighted score is measured
        against, and the Graph tab offers it as "unweighted". It is NOT what
        drives pairings — the README used to call the scoring "rarity-weighted
        Jaccard similarity", which it never was: weighted_similarity normalises
        by average set size, not by the union.
        """
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    def weighted_similarity(self, name_a: str, name_b: str) -> Tuple[float, Set[str]]:
        """Rarity-weighted Jaccard: W(A n B) / W(A u B).

        The weighted generalisation of the Jaccard index — swap "count the
        compounds" for "add up what they are worth" and the definition is
        otherwise unchanged. Identical profiles score 1.0, disjoint ones 0.0,
        and everything sits properly on that scale.

        This is also the measure the README has always claimed. The previous
        implementation divided by the average profile size rather than by the
        union, which is a Dice-style denominator, not Jaccard; and the earlier
        attempt at this fix divided by the rarest-possible compound weight,
        which is bounded but compresses every real score below 0.44 and would
        have quietly broken the Graph tab's threshold slider and the
        high/medium/low score colouring, both of which assume a full 0..1
        spread.
        """
        ing_a = self.ingredients.get(name_a)
        ing_b = self.ingredients.get(name_b)
        if not ing_a or not ing_b:
            return 0.0, set()
        shared = ing_a.compounds & ing_b.compounds
        if not shared:
            return 0.0, set()

        union_weight = sum(self._weight.get(c, 0.0)
                           for c in (ing_a.compounds | ing_b.compounds))
        if union_weight <= 0:
            return 0.0, shared
        shared_weight = sum(self._weight.get(c, 0.0) for c in shared)
        return min(shared_weight / union_weight, 1.0), shared

    def get_pairings(self, ingredient_name: str, top_n: int = 20) -> List[dict]:
        if ingredient_name not in self.ingredients:
            return []
        results = []
        for other_name in self.ingredients:
            if other_name == ingredient_name:
                continue
            score, shared = self.weighted_similarity(ingredient_name, other_name)
            # A match resting entirely on compounds present in >30% of the
            # database is not a pairing, it is a coincidence -- hexanal alone
            # links 63% of everything here. Scoring already pushes these down;
            # this keeps them off the list altogether, so an ingredient with
            # few distinctive compounds returns a short honest list rather
            # than 25 rows of noise. `shared` itself is untouched, so the
            # score stays a pure function of the chemistry.
            if shared and shared <= self._boring_compounds:
                continue
            if score > 0:
                results.append({
                    "ingredient": other_name,
                    "score": score,
                    "shared_compounds": shared,
                    "category": self.ingredients[other_name].category,
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

    def find_bridge(self, name_a: str, name_b: str) -> List[dict]:
        """Find ingredients that connect two others through shared compounds.

        Scored with the same rarity weighting as weighted_similarity. It used
        raw compound COUNTS, which meant the app held two different ideas of
        what "connected" means: a pairing was rarity-weighted, a bridge was
        not. Because the old score also divided by the bridge's own profile
        size, an ingredient with very few compounds that happened to share
        hexanal with both ends floated to the top — "zucchini bridges pork and
        apple" was a real result, on nothing but a near-universal green note.

        The weakest of the two links decides the score, not the average. A
        bridge is only as good as its weaker end: something strongly tied to
        the pork and barely to the apple is not bridging anything.
        """
        if name_a not in self.ingredients or name_b not in self.ingredients:
            return []
        ing_a = self.ingredients[name_a]
        ing_b = self.ingredients[name_b]
        bridges = []
        for bridge_name, bridge_ing in self.ingredients.items():
            if bridge_name in (name_a, name_b):
                continue
            shared_with_a = ing_a.compounds & bridge_ing.compounds
            shared_with_b = ing_b.compounds & bridge_ing.compounds
            if not (shared_with_a and shared_with_b):
                continue
            # A "bridge" whose only link to either side is a near-universal
            # compound is not bridging anything. This is what produced
            # "zucchini bridges pork and apple" on nothing but hexanal.
            if (shared_with_a <= self._boring_compounds
                    or shared_with_b <= self._boring_compounds):
                continue
            size = len(bridge_ing.compounds)
            if not size:
                continue
            own_weight = sum(self._weight.get(c, 0.0) for c in bridge_ing.compounds)
            if own_weight <= 0:
                continue
            link_a = sum(self._weight.get(c, 0.0) for c in shared_with_a) / own_weight
            link_b = sum(self._weight.get(c, 0.0) for c in shared_with_b) / own_weight
            bridge_score = min(link_a, link_b)
            if bridge_score <= 0.0:
                continue
            bridges.append({
                "ingredient": bridge_name,
                "score": min(bridge_score, 1.0),
                "connects_to_a": shared_with_a,
                "connects_to_b": shared_with_b,
                "category": bridge_ing.category,
            })
        bridges.sort(key=lambda x: x["score"], reverse=True)
        return bridges[:10]

    def substitutes(self, name: str, top_n: int = 10) -> List[dict]:
        """What to reach for when you have no `name`.

        A substitute is not the same question as a pairing, which is why this
        is not just get_pairings under another name. A pairing is something to
        put *with* an ingredient; a substitute has to stand *in* for it, so it
        must be able to do the same job in a dish. That means the same
        category, and — for grains and sauces, where the category is far too
        coarse — the same subtype: a stock cannot stand in for a vinaigrette,
        and orzo cannot stand in for a baguette.
        """
        target = self.ingredients.get(name)
        if not target:
            return []

        pool = {n for n, i in self.ingredients.items()
                if i.category == target.category and n != name}
        # Narrow to the subtype when the ingredient belongs to one.
        for slot, members in _SLOT_SUBSETS.items():
            if name in members:
                pool &= set(members)

        out = []
        for other in pool:
            score, shared = self.weighted_similarity(name, other)
            out.append({
                "ingredient": other,
                "score": score,
                "shared_compounds": shared,
                "category": self.ingredients[other].category,
                # Said plainly, because a substitute with nothing in common is
                # a role-swap, not a flavour match, and the cook should know
                # which one they are being offered.
                "aroma_match": bool(shared - self._boring_compounds),
            })
        out.sort(key=lambda x: (x["aroma_match"], x["score"]), reverse=True)
        return out[:top_n]

    def ingredients_with_compound(self, compound: str) -> List[str]:
        """The inverse index: everything carrying a given aroma compound.

        The database is a mapping and could only ever be read in one direction
        — pick an ingredient, see its compounds. Asking "what else tastes of
        geosmin?" is the more interesting half and there was no way to ask it.
        """
        if compound not in self.compounds:
            return []
        return sorted(n for n, i in self.ingredients.items() if compound in i.compounds)

    def search_compounds(self, text: str) -> List[str]:
        """Compound keys whose name or description matches `text`."""
        needle = text.strip().lower()
        if not needle:
            return []
        return sorted(k for k, c in self.compounds.items()
                      if needle in k.lower()
                      or needle in c.name.lower()
                      or needle in c.description.lower())

    def novelty_score(self, ingredients: List[str]) -> float:
        if len(ingredients) < 2:
            return 0.0
        categories = set(self.ingredients[n].category for n in ingredients if n in self.ingredients)
        cat_diversity = len(categories) / len(ingredients)
        pair_scores = []
        for i in range(len(ingredients)):
            for j in range(i + 1, len(ingredients)):
                if ingredients[i] in self.ingredients and ingredients[j] in self.ingredients:
                    score, _ = self.weighted_similarity(ingredients[i], ingredients[j])
                    pair_scores.append(score)
        avg_sim = sum(pair_scores) / len(pair_scores) if pair_scores else 0
        sim_novelty = 1.0 - abs(avg_sim - 0.35) / 0.65
        return (cat_diversity * 0.4 + max(sim_novelty, 0) * 0.6)

    def generate_recipe(self, seed_ingredient: Optional[str] = None,
                        target_novelty: float = 0.6,
                        dish_type: Optional[str] = None) -> dict:
        if seed_ingredient and seed_ingredient not in self.ingredients:
            seed_ingredient = None

        # Filter templates by dish type
        if dish_type and dish_type != "Any":
            templates = [t for t in DISH_TEMPLATES if t.get("dish_type") == dish_type]
            if not templates:
                templates = DISH_TEMPLATES
        else:
            templates = DISH_TEMPLATES

        # Then, if the user named a seed, keep only templates that have a slot
        # able to hold it. Without this the template is chosen at random and
        # the seed is placed afterwards, so it lands somewhere valid only if it
        # happens to fit — measured at 35% of the time. The other 65% fell
        # through to the "accent" fallback below, which is how asking for a
        # salmon recipe produced a mushroom soup with salmon bolted on beside
        # it. Olive oil failed 30 times out of 30.
        #
        # Dish type wins if the two filters disagree: it is the more explicit
        # request, and the accent fallback still honours the seed.
        if seed_ingredient:
            fitting = [t for t in templates
                       if any(seed_ingredient in slot_candidate_set(s)
                              for s in t["structure"])]
            if fitting:
                templates = fitting

        best_recipe = None
        best_novelty = -1

        for _ in range(60):
            template = random.choice(templates)
            chosen = {}

            if seed_ingredient:
                # Place the user's seed in the first slot that can legitimately
                # hold it: a required slot for preference, then any other.
                #
                # This used to consult two dict literals rebuilt on every one
                # of the 60 iterations, each a partial copy of SLOT_CAT_MAP
                # that had already drifted from it — the primary map had no
                # entry for citrus, and carried a "sauce" slot that no template
                # uses. Worse, neither understood the subtype slots, so a grain
                # seed could be placed in a `noodle` slot and quinoa would be
                # served as the noodle. Asking get_slot_candidates is
                # authoritative by construction and cannot drift.
                placed = False
                ordered = list(template["needs"]) + [
                    s for s in template["structure"] if s not in template["needs"]]
                for slot in ordered:
                    if seed_ingredient in slot_candidate_set(slot):
                        chosen[slot] = seed_ingredient
                        placed = True
                        break
                if not placed:
                    # No slot in this template can hold it. Honour the request
                    # anyway — the user asked for this ingredient — as a
                    # free-floating accent the display still lists.
                    chosen["accent"] = seed_ingredient

            for slot in template["structure"]:
                if slot in chosen:
                    continue
                candidates = get_slot_candidates(slot, exclude=set(chosen.values()))
                if candidates:
                    chosen[slot] = random.choice(candidates)

            ingredient_list = list(chosen.values())
            novelty = self.novelty_score(ingredient_list)

            if novelty > best_novelty:
                best_novelty = novelty
                best_recipe = {
                    "template": template,
                    "ingredients": chosen,
                    "novelty": novelty,
                    "all_ingredients": ingredient_list,
                }

        if not best_recipe:
            return {"error": "Could not generate recipe"}

        recipe = best_recipe
        slot_display = {}
        for slot, ing_name in recipe["ingredients"].items():
            display = self.ingredients[ing_name].name if ing_name in self.ingredients else ing_name
            slot_display[slot] = display

        aliases = {"veg": "vegetable", "cheese": "dairy"}

        name = recipe["template"]["name"]
        technique = recipe["template"]["technique"]

        for slot, display in slot_display.items():
            name = name.replace(f"{{{slot}}}", display.title())
            technique = technique.replace(f"{{{slot}}}", display)
        for alias, real_slot in aliases.items():
            if real_slot in slot_display:
                name = name.replace(f"{{{alias}}}", slot_display[real_slot].title())
                technique = technique.replace(f"{{{alias}}}", slot_display[real_slot])

        connections = []
        ings = recipe["all_ingredients"]
        for i in range(len(ings)):
            for j in range(i + 1, len(ings)):
                if ings[i] in self.ingredients and ings[j] in self.ingredients:
                    _, shared = self.weighted_similarity(ings[i], ings[j])
                    if shared:
                        connections.append({
                            "pair": (ings[i], ings[j]),
                            "shared": shared,
                        })

        return {
            "name": name,
            "technique": technique,
            "ingredients": recipe["ingredients"],
            "novelty": recipe["novelty"],
            "connections": connections,
            "dish_type": recipe["template"].get("dish_type", ""),
        }

    def surprise_me(self, dish_type: Optional[str] = None) -> dict:
        candidates = []
        for _ in range(40):
            recipe = self.generate_recipe(target_novelty=0.8, dish_type=dish_type)
            if "error" not in recipe and len(recipe["connections"]) >= 2:
                candidates.append(recipe)
        if not candidates:
            return self.generate_recipe(dish_type=dish_type)
        candidates.sort(key=lambda r: r["novelty"], reverse=True)
        top = candidates[:min(12, len(candidates))]
        return random.choice(top)

    def recipe_to_ai_prompt(self, recipe: dict) -> str:
        """Convert a generated recipe concept into a detailed, high-quality AI prompt."""

        # ── Compute compound rarity ──
        boring_compounds = self._boring_compounds

        # ── Build rich ingredient profiles ──
        ingredient_profiles = []
        all_ingredient_names = []
        all_keys = []
        for slot, ing_name in recipe["ingredients"].items():
            if ing_name not in self.ingredients:
                continue
            ing = self.ingredients[ing_name]
            all_ingredient_names.append(ing.name)
            all_keys.append(ing_name)

            distinctive = []
            for c in ing.compounds:
                if c in self.compounds and c not in boring_compounds:
                    rarity_pct = 100 - (self._compound_freq[c] / self._total_ings * 100)
                    distinctive.append((rarity_pct, self.compounds[c].name, self.compounds[c].description))
            distinctive.sort(reverse=True)
            aroma_notes = [f"{name} ({desc})" for _, name, desc in distinctive[:4]]

            textures = get_textures(ing_name)
            taste = get_taste_profile(ing_name)
            taste_str = ", ".join(f"{k} ({v:.0%})" for k, v in sorted(taste.items(), key=lambda x: -x[1])[:3]) if taste else "neutral"

            ingredient_profiles.append({
                "name": ing.name, "role": slot, "category": ing.category,
                "flavor": ing.flavor_notes, "aromas": aroma_notes,
                "methods": ing.cooking_methods[:4], "textures": textures,
                "taste": taste_str,
            })

        # ── Filter connections ──
        interesting_connections = []
        contrast_pairs = []

        for conn in recipe.get("connections", []):
            a, b = conn["pair"]
            a_name = self.ingredients[a].name if a in self.ingredients else a
            b_name = self.ingredients[b].name if b in self.ingredients else b
            interesting_shared = [c for c in conn["shared"] if c in self.compounds and c not in boring_compounds]

            if interesting_shared:
                shared_info = [f"{self.compounds[c].name} ({self.compounds[c].description})" for c in interesting_shared[:3]]
                interesting_connections.append(f"{a_name} + {b_name}: share {', '.join(shared_info)}")
            else:
                contrast_pairs.append((a_name, b_name))

        # Find zero-connection pairs
        ings = list(recipe["ingredients"].values())
        connected_pairs = {frozenset(c["pair"]) for c in recipe.get("connections", [])}
        for i in range(len(ings)):
            for j in range(i + 1, len(ings)):
                if ings[i] in self.ingredients and ings[j] in self.ingredients:
                    if frozenset([ings[i], ings[j]]) not in connected_pairs:
                        contrast_pairs.append((self.ingredients[ings[i]].name, self.ingredients[ings[j]].name))

        # ── Balance analysis ──
        balance = analyze_balance(all_keys) if all_keys else None

        # ── Cuisine and dish type ──
        dish_type = recipe.get("dish_type", "")
        cuisine_hints = {
            "Curry & Stew": "Indian, Thai, Caribbean, or Japanese curry",
            "Stir-Fry & Wok": "Chinese, Thai, Korean, or Japanese wok cooking",
            "Tacos & Wraps": "Mexican, Korean-fusion, Middle Eastern, or Tex-Mex",
            "Pasta & Noodles": "Italian, Japanese, Thai, Chinese, or fusion",
            "Bowl": "Hawaiian poke, Korean bibimbap, Japanese donburi, or grain bowl",
            "Soup": "French, Vietnamese, Japanese, Mexican, or rustic farmhouse",
            "Pizza & Flatbread": "Neapolitan, New York, Middle Eastern, or Indian naan",
            "One-Pot": "French, Spanish, West African, or American comfort",
            "Casserole & Bake": "French gratin, American comfort, Italian, or Tex-Mex",
            "Grilled & Seared": "American steakhouse, Argentine, Japanese, or Mediterranean",
            "Breakfast & Brunch": "American, Middle Eastern, French, or Mexican",
            "Dessert & Sweet": "French, American rustic, Japanese, or Middle Eastern",
            "Sandwich": "American deli, Vietnamese, Italian, Cuban, or fusion",
            "Salad & Slaw": "French composed, Thai, Mexican, or farm-to-table",
            "Snack & Appetizer": "Spanish tapas, Chinese dim sum, Mexican, or Japanese izakaya",
            "Sauce & Dip": "Mediterranean, Mexican, Asian, or Indian",
        }

        # ── Dietary tags ──
        categories_used = set(self.ingredients[k].category for k in all_keys if k in self.ingredients)
        dietary = []
        if not (categories_used & {"protein", "seafood"}):
            dietary.append("vegetarian")
        if not (categories_used & {"protein", "seafood", "dairy"}):
            dietary.append("vegan candidate (verify)")
        if "seafood" in categories_used and "protein" not in categories_used:
            dietary.append("pescatarian")

        # ── Build the prompt ──
        lines = []

        lines.append("You are a professional chef creating a new recipe. You have deep knowledge of")
        lines.append("flavor science, texture pairing, seasoning balance, and global cuisines.")
        lines.append("Your recipes are creative but practical — a skilled home cook should be able")
        lines.append("to make this on a weeknight with a well-stocked kitchen.\n")

        lines.append(f"DISH: {recipe['name']}")
        if dish_type:
            lines.append(f"TYPE: {dish_type}")
        lines.append(f"CUISINE DIRECTION: Pick the best from: {cuisine_hints.get(dish_type, 'any cuisine')}")
        if dietary:
            lines.append(f"DIETARY: {', '.join(dietary)}")
        lines.append("")

        # Ingredient details
        lines.append("THE INGREDIENTS AND WHAT TO DO WITH THEM:")
        for p in ingredient_profiles:
            lines.append(f"  {p['name']} [{p['category']}] — {p['flavor']}")
            lines.append(f"    Role: {p['role']}  |  Textures: {', '.join(p['textures'])}  |  Taste: {p['taste']}")
            if p['aromas']:
                lines.append(f"    Distinctive aromas: {', '.join(p['aromas'])}")
            lines.append(f"    Best cooking methods: {', '.join(p['methods'])}")
        lines.append("")

        # Molecular connections
        if interesting_connections:
            lines.append("WHY THESE PAIR (molecular flavor science):")
            for conn in interesting_connections:
                lines.append(f"  • {conn}")
            lines.append("")

        if contrast_pairs:
            lines.append("CONTRAST PAIRINGS (use these for texture/temperature/flavor contrast):")
            for a, b in contrast_pairs[:4]:
                lines.append(f"  • {a} + {b}: different flavor worlds — use contrast creatively")
            lines.append("")

        # Novelty
        novelty = recipe.get("novelty", 0)
        if novelty > 0.7:
            lines.append("CREATIVITY LEVEL: High — this is an unconventional combo. Make it surprising but delicious.\n")
        elif novelty > 0.4:
            lines.append("CREATIVITY LEVEL: Medium — some familiar, some unexpected. Balance comfort with discovery.\n")
        else:
            lines.append("CREATIVITY LEVEL: Classic — execute perfectly with one or two clever twists.\n")

        # Balance
        if balance:
            balance_issues = balance["texture_suggestions"] + balance["taste_suggestions"]
            if balance_issues:
                lines.append("⚠ BALANCE ISSUES TO FIX IN YOUR RECIPE:")
                for tip in balance_issues:
                    lines.append(f"  • {tip}")
                lines.append("Add salt, acid (citrus/vinegar), fat (butter/oil), or crunch (nuts/breadcrumbs)")
                lines.append("as needed even though they aren't in the main ingredients above.\n")
            else:
                lines.append("BALANCE: Good texture variety and taste balance. Maintain it.\n")

        # Output format
        lines.append("Write the complete recipe in this format:\n")
        lines.append("DISH NAME: [Creative name that sounds appetizing]\n")
        lines.append("OVERVIEW: [2 sentences: what this dish is, what makes it special]\n")
        lines.append("SERVES: 2-4  |  PREP: [X min]  |  COOK: [X min]  |  TOTAL: [X min]\n")
        lines.append("INGREDIENTS:")
        lines.append("[Precise quantities. Include salt, pepper, oil, and supporting ingredients")
        lines.append("not listed above. Group into sections if multi-component.]\n")
        lines.append("INSTRUCTIONS:")
        lines.append("[Numbered steps. Include temperatures (°F), times, and sensory cues")
        lines.append("('until golden', 'until fragrant, ~30 seconds'). Be specific and opinionated.]\n")
        lines.append("THE SCIENCE:")
        lines.append("[2-3 sentences on why these flavors work together. Reference specific")
        lines.append("compounds by name. Explain what the contrast ingredients bring.]\n")
        lines.append("DRINK PAIRING: [One specific recommendation with brief reason]\n")
        lines.append("TIPS & SWAPS:")
        lines.append("[3 practical notes: easier substitutions, make-ahead options, leftovers]")

        return "\n".join(lines)

    # ─── PANTRY MODE ────────────────────────────────────────────

    def pantry_recipes(self, pantry: Set[str], dish_type: Optional[str] = None,
                       top_n: int = 15) -> List[dict]:
        """
        Generate recipes using ONLY ingredients from the pantry.
        Returns recipes ranked by flavor score and completeness.
        """
        templates = DISH_TEMPLATES
        if dish_type and dish_type != "Any":
            templates = [t for t in templates if t.get("dish_type") == dish_type]
        if not templates:
            templates = DISH_TEMPLATES

        results = []

        for template in templates:
            slots = list(template["structure"].keys())

            def fill_slots(slot_idx, chosen):
                if slot_idx >= len(slots):
                    ingredient_list = list(chosen.values())
                    if len(set(ingredient_list)) < len(ingredient_list):
                        return

                    total_score = 0
                    connections = 0
                    for i in range(len(ingredient_list)):
                        for j in range(i + 1, len(ingredient_list)):
                            s, shared = self.weighted_similarity(ingredient_list[i], ingredient_list[j])
                            if shared:
                                total_score += s
                                connections += 1

                    if connections > 0:
                        results.append({
                            "template": template,
                            "ingredients": dict(chosen),
                            "score": total_score / connections,
                            "connections": connections,
                            "all_ingredients": ingredient_list,
                        })
                    return

                slot = slots[slot_idx]
                # Use get_slot_candidates intersected with pantry
                valid_for_slot = set(get_slot_candidates(slot, exclude=set(chosen.values())))
                candidates = [n for n in pantry if n in valid_for_slot]
                random.shuffle(candidates)

                # Limit branching to keep it fast
                for candidate in candidates[:5]:
                    chosen[slot] = candidate
                    fill_slots(slot_idx + 1, chosen)
                    del chosen[slot]

            fill_slots(0, {})

        # Deduplicate by ingredient set, limit per template for variety
        seen = set()
        template_counts = defaultdict(int)
        unique_results = []
        # Sort by score first, then pick diverse set
        results.sort(key=lambda r: (r["connections"], r["score"]), reverse=True)
        for r in results:
            key = frozenset(r["all_ingredients"])
            tname = r["template"]["name"]
            if key not in seen and template_counts[tname] < 2:
                seen.add(key)
                template_counts[tname] += 1
                unique_results.append(r)

        unique_results.sort(key=lambda r: (r["connections"], r["score"]), reverse=True)

        # Build full recipe objects for top results
        final = []
        for r in unique_results[:top_n]:
            slot_display = {}
            for slot, ing_name in r["ingredients"].items():
                display = self.ingredients[ing_name].name if ing_name in self.ingredients else ing_name
                slot_display[slot] = display

            aliases = {"veg": "vegetable", "cheese": "dairy"}
            name = r["template"]["name"]
            technique = r["template"]["technique"]

            for slot, display in slot_display.items():
                name = name.replace(f"{{{slot}}}", display.title())
                technique = technique.replace(f"{{{slot}}}", display)
            for alias, real_slot in aliases.items():
                if real_slot in slot_display:
                    name = name.replace(f"{{{alias}}}", slot_display[real_slot].title())
                    technique = technique.replace(f"{{{alias}}}", slot_display[real_slot])

            # Build connections list
            connections = []
            for i in range(len(r["all_ingredients"])):
                for j in range(i + 1, len(r["all_ingredients"])):
                    a, b = r["all_ingredients"][i], r["all_ingredients"][j]
                    if a in self.ingredients and b in self.ingredients:
                        _, shared = self.weighted_similarity(a, b)
                        if shared:
                            connections.append({"pair": (a, b), "shared": shared})

            final.append({
                "name": name,
                "technique": technique,
                "ingredients": r["ingredients"],
                "novelty": self.novelty_score(r["all_ingredients"]),
                "connections": connections,
                "score": r["score"],
                "dish_type": r["template"].get("dish_type", ""),
            })

        return final

    def almost_there(self, pantry: Set[str], dish_type: Optional[str] = None,
                     top_n: int = 10) -> List[dict]:
        """Find recipes where you're exactly 1 ingredient short."""
        templates = DISH_TEMPLATES
        if dish_type and dish_type != "Any":
            templates = [t for t in templates if t.get("dish_type") == dish_type]
        if not templates:
            templates = DISH_TEMPLATES

        results = []

        for template in templates:
            slots = list(template["structure"].keys())
            if len(slots) < 2:
                continue

            for skip_idx in range(len(slots)):
                skip_slot = slots[skip_idx]
                other_slots = [s for i, s in enumerate(slots) if i != skip_idx]

                def fill_partial(slot_idx, chosen):
                    if slot_idx >= len(other_slots):
                        # Find best non-pantry ingredient for the skipped slot
                        valid_for_skip = get_slot_candidates(skip_slot, exclude=set(chosen.values()) | pantry)
                        best_missing = None
                        best_score = -1

                        for cand_name in valid_for_skip:
                            pair_score = sum(
                                self.weighted_similarity(cand_name, fn)[0]
                                for fn in chosen.values()
                            )
                            if pair_score > best_score:
                                best_score = pair_score
                                best_missing = cand_name

                        if best_missing and best_score > 0:
                            full_chosen = dict(chosen)
                            full_chosen[skip_slot] = best_missing
                            results.append({
                                "template": template,
                                "ingredients": full_chosen,
                                "score": best_score,
                                "missing": best_missing,
                                "missing_slot": skip_slot,
                                "all_ingredients": list(full_chosen.values()),
                            })
                        return

                    slot = other_slots[slot_idx]
                    valid_for_slot = set(get_slot_candidates(slot, exclude=set(chosen.values())))
                    candidates = [n for n in pantry if n in valid_for_slot]
                    random.shuffle(candidates)

                    for candidate in candidates[:4]:
                        chosen[slot] = candidate
                        fill_partial(slot_idx + 1, chosen)
                        del chosen[slot]

                fill_partial(0, {})

        # Deduplicate: limit to 1 per missing ingredient for variety
        seen_missing = defaultdict(int)
        seen_combos = set()

        # Deduplicate and sort
        seen = set()
        unique = []
        results.sort(key=lambda r: r["score"], reverse=True)
        for r in results:
            key = frozenset(r["all_ingredients"])
            if key not in seen_combos and seen_missing[r["missing"]] < 2:
                seen_combos.add(key)
                seen_missing[r["missing"]] += 1
                unique.append(r)

        # Build display objects
        final = []
        for r in unique[:top_n]:
            slot_display = {}
            for slot, ing_name in r["ingredients"].items():
                display = self.ingredients[ing_name].name if ing_name in self.ingredients else ing_name
                slot_display[slot] = display

            aliases = {"veg": "vegetable", "cheese": "dairy"}
            name = r["template"]["name"]
            technique = r["template"]["technique"]

            for slot, display in slot_display.items():
                name = name.replace(f"{{{slot}}}", display.title())
                technique = technique.replace(f"{{{slot}}}", display)
            for alias, real_slot in aliases.items():
                if real_slot in slot_display:
                    name = name.replace(f"{{{alias}}}", slot_display[real_slot].title())
                    technique = technique.replace(f"{{{alias}}}", slot_display[real_slot])

            missing_display = self.ingredients[r["missing"]].name if r["missing"] in self.ingredients else r["missing"]

            connections = []
            for i in range(len(r["all_ingredients"])):
                for j in range(i + 1, len(r["all_ingredients"])):
                    a, b = r["all_ingredients"][i], r["all_ingredients"][j]
                    if a in self.ingredients and b in self.ingredients:
                        _, shared = self.weighted_similarity(a, b)
                        if shared:
                            connections.append({"pair": (a, b), "shared": shared})

            final.append({
                "name": name,
                "technique": technique,
                "ingredients": r["ingredients"],
                "connections": connections,
                "missing_ingredient": r["missing"],
                "missing_display": missing_display,
                "missing_slot": r["missing_slot"],
                "dish_type": r["template"].get("dish_type", ""),
                "score": r["score"],
            })

        return final


# ═══════════════════════════════════════════════════════════════════
# AI CHEF - Ollama / Claude API integration
# ═══════════════════════════════════════════════════════════════════

# Claude models the AI Chef offers, newest first. A hard-coded default went
# three model generations stale between 3.0 and 3.1 with nothing to catch it,
# so the roster lives here as data and the AI tab renders it as a dropdown:
# picking a current model is a choice the user can make without editing source.
# (label, model id, note)
CLAUDE_MODELS = [
    ("Claude Opus 5", "claude-opus-5", "most capable — best recipes, highest cost"),
    ("Claude Sonnet 5", "claude-sonnet-5", "strong and cheaper — a good default"),
    ("Claude Haiku 4.5", "claude-haiku-4-5", "fastest and cheapest"),
]
DEFAULT_CLAUDE_MODEL = CLAUDE_MODELS[0][1]

# A full recipe in the requested format — overview, ingredients, numbered
# instructions, the science, a drink pairing and three tips — runs well past
# 4096 tokens once the model is being genuinely specific. Streaming means a
# large ceiling costs nothing in latency.
CLAUDE_MAX_TOKENS = 16000


def _write_json_atomic(path: str, data, secret: bool = False) -> bool:
    """Write JSON via a temp file and an atomic replace. Never raises.

    open(path, "w") truncates before it writes, so an interruption between the
    two leaves an empty file. For a pantry that is a mild annoyance; for the
    saved-recipe list it is somebody's collection; for the config it is the API
    key. os.replace is atomic on POSIX and on Windows, so a reader sees either
    the old file or the new one and never a half-written one.
    """
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=list)
        if secret:
            _restrict_permissions(tmp)
        os.replace(tmp, path)
        return True
    except (OSError, TypeError, ValueError) as exc:
        # TypeError / ValueError: json.dump on something it cannot encode.
        print(f"Save error ({os.path.basename(path)}): {exc}")
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False


def _restrict_permissions(path: str) -> None:
    """Best-effort owner-only permissions on a file holding a secret.

    The config carries the Anthropic API key in clear text. On POSIX a default
    umask leaves it world-readable, which for a key that can spend money is
    worth one chmod. Windows inherits the user's ACL from the home directory
    and has no mode bits to set, so this is a no-op there — and it stays
    best-effort either way, because failing to tighten permissions is not a
    reason to fail to save.
    """
    try:
        os.chmod(path, 0o600)
    except (OSError, NotImplementedError, AttributeError):
        pass


class AIChef:
    """Handles communication with Ollama or the Claude API."""

    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.ollama_model = "qwen2.5:14b"
        self.anthropic_key = ""
        self.anthropic_model = DEFAULT_CLAUDE_MODEL
        self.provider = "ollama"  # or "anthropic"
        self._load_config()

    def _config_path(self):
        return os.path.join(os.path.expanduser("~"), ".flavorforge_config.json")

    def _load_config(self):
        try:
            with open(self._config_path(), "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
                if not isinstance(cfg, dict):
                    raise ValueError("config is not a JSON object")
                self.ollama_url = cfg.get("ollama_url", self.ollama_url)
                self.ollama_model = cfg.get("ollama_model", self.ollama_model)
                self.anthropic_key = cfg.get("anthropic_key", self.anthropic_key)
                self.anthropic_model = cfg.get("anthropic_model", self.anthropic_model)
                self.provider = cfg.get("provider", self.provider)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            # A missing config is the normal first-run case. An unreadable or
            # malformed one is not a reason to fail to start — the defaults
            # above are all still in place.
            pass
        # A cfg that is not an object would have raised AttributeError on the
        # first .get above rather than falling through to here, so the shape is
        # checked before it is used.

        # A model id saved by an older version may no longer exist. Rather
        # than let the first generation fail with a 404 from the API, move it
        # forward and say nothing -- the dropdown shows what is now selected.
        if self.anthropic_model not in {m[1] for m in CLAUDE_MODELS}:
            self.retired_model = self.anthropic_model
            self.anthropic_model = DEFAULT_CLAUDE_MODEL
        else:
            self.retired_model = ""

    def save_config(self):
        cfg = {
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "anthropic_key": self.anthropic_key,
            "anthropic_model": self.anthropic_model,
            "provider": self.provider,
        }
        return _write_json_atomic(self._config_path(), cfg, secret=True)

    def generate(self, prompt: str, callback=None, error_callback=None):
        """Generate response in a background thread. Calls callback with chunks."""
        if self.provider == "ollama":
            thread = threading.Thread(target=self._ollama_generate,
                                       args=(prompt, callback, error_callback), daemon=True)
        else:
            thread = threading.Thread(target=self._anthropic_generate,
                                       args=(prompt, callback, error_callback), daemon=True)
        thread.start()

    def _ollama_generate(self, prompt, callback, error_callback):
        try:
            url = f"{self.ollama_url}/api/generate"
            payload = json.dumps({
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": True,
            }).encode("utf-8")

            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "response" in data:
                            if callback:
                                callback(data["response"])
                        if data.get("done", False):
                            if callback:
                                callback(None)  # Signal done
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            if error_callback:
                error_callback(str(e))

    def _anthropic_generate(self, prompt, callback, error_callback):
        """Stream a completion from the Claude API over the raw HTTP endpoint.

        Streaming rather than a single blocking read, for three reasons: it
        matches what the Ollama path already does, so the tab behaves the same
        whichever provider is selected; the user sees the recipe arrive instead
        of watching a spinner for half a minute; and a long generation cannot
        hit an HTTP read timeout part-way through and lose everything.

        urllib rather than the anthropic SDK on purpose. FlavorForge is one
        file you can run against a stock Python install, and an SDK dependency
        would end that. The trade is real — no automatic retries, no typed
        errors — and the cost is this method being longer than it would
        otherwise need to be.
        """
        try:
            if not self.anthropic_key:
                if error_callback:
                    error_callback("No Anthropic API key configured. Add it in the AI Chef settings.")
                return

            payload = json.dumps({
                "model": self.anthropic_model,
                "max_tokens": CLAUDE_MAX_TOKENS,
                "stream": True,
                "messages": [{"role": "user", "content": prompt}],
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", data=payload, headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                })

            stop_reason = None
            with urllib.request.urlopen(req, timeout=180) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    # Server-sent events: "event:" lines carry the type and
                    # "data:" lines the JSON. The data payload repeats its own
                    # type, so the event line can be ignored entirely.
                    if not line.startswith("data:"):
                        continue
                    body = line[5:].strip()
                    if not body or body == "[DONE]":
                        continue
                    try:
                        evt = json.loads(body)
                    except json.JSONDecodeError:
                        continue

                    kind = evt.get("type")
                    if kind == "content_block_delta":
                        delta = evt.get("delta") or {}
                        if delta.get("type") == "text_delta" and callback:
                            callback(delta.get("text", ""))
                    elif kind == "message_delta":
                        stop_reason = (evt.get("delta") or {}).get("stop_reason", stop_reason)
                    elif kind == "error":
                        err = evt.get("error") or {}
                        if error_callback:
                            error_callback(f"{err.get('type', 'error')}: {err.get('message', body[:200])}")
                        return

            # A recipe cut off at the token ceiling used to look finished: the
            # text simply stopped, mid-step, with nothing to say why.
            if stop_reason == "max_tokens" and callback:
                callback(
                    "\n\n[!] Response hit the "
                    f"{CLAUDE_MAX_TOKENS}-token limit and was cut off. "
                    "Try a simpler dish, or raise CLAUDE_MAX_TOKENS.\n")
            elif stop_reason == "refusal" and error_callback:
                error_callback("The model declined this request.")
                return

            if callback:
                callback(None)   # signal done

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            hint = ""
            if e.code == 401:
                hint = " — check the API key in AI Chef settings."
            elif e.code == 404:
                hint = (f" — model {self.anthropic_model!r} was not found. It may have been "
                        f"retired; pick another from the dropdown.")
            elif e.code == 429:
                hint = " — rate limited. Wait a moment and try again."
            if error_callback:
                error_callback(f"HTTP {e.code}{hint}\n{body[:300]}")
        except Exception as e:
            if error_callback:
                error_callback(str(e))

    def test_connection(self) -> Tuple[bool, str]:
        """Test if the configured provider is reachable."""
        try:
            if self.provider == "ollama":
                url = f"{self.ollama_url}/api/tags"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m["name"] for m in data.get("models", [])]
                    if self.ollama_model in models or any(self.ollama_model in m for m in models):
                        return True, f"Connected. Model '{self.ollama_model}' available."
                    else:
                        return True, f"Connected but '{self.ollama_model}' not found. Available: {', '.join(models[:5])}"
            else:
                if not self.anthropic_key:
                    return False, "No API key configured."
                return True, f"Anthropic API key set. Model: {self.anthropic_model}"
        except Exception as e:
            return False, f"Connection failed: {e}"


# ═══════════════════════════════════════════════════════════════════
# TKINTER GUI
# ═══════════════════════════════════════════════════════════════════

class FlavorForgeGUI:
    def __init__(self):
        if not HAVE_TK:
            raise RuntimeError(
                "tkinter is not available, so the GUI cannot start.\n"
                "On Debian/Ubuntu: sudo apt install python3-tk\n"
                "Or use the command line instead: flavorforge --help")
        self.engine = FlavorEngine()
        self.ai_chef = AIChef()
        self.root = tk.Tk()
        self.root.title("FlavorForge — Procedural Cooking Engine v3.0")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1a1a2e")

        self.colors = {
            "bg": "#1a1a2e", "panel": "#16213e", "accent": "#0f3460",
            "highlight": "#e94560", "text": "#eee", "text_dim": "#888",
            "text_bright": "#fff", "success": "#4CAF50", "warning": "#FF9800",
        }

        self.selected_ingredient = None
        self.graph_nodes = {}
        self.graph_layout_dirty = True
        self.current_recipe = None  # Store last generated recipe for AI
        self.pantry = set()  # Ingredients the user has on hand
        self._load_pantry()

        self.setup_styles()
        self.build_ui()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TFrame", background=self.colors["bg"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("Dark.TLabel", background=self.colors["bg"],
                        foreground=self.colors["text"], font=("Consolas", 10))
        style.configure("Title.TLabel", background=self.colors["bg"],
                        foreground=self.colors["highlight"], font=("Consolas", 16, "bold"))
        style.configure("Dark.TButton", background=self.colors["accent"],
                        foreground=self.colors["text"], font=("Consolas", 10))
        style.configure("Dark.TNotebook", background=self.colors["bg"])
        style.configure("Dark.TNotebook.Tab", background=self.colors["panel"],
                        foreground=self.colors["text"], font=("Consolas", 10), padding=[12, 6])
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", self.colors["accent"])],
                  foreground=[("selected", self.colors["text_bright"])])

    def build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=self.colors["bg"], height=50)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        header.pack_propagate(False)

        tk.Label(header, text="⚗ FLAVORFORGE v3", font=("Consolas", 20, "bold"),
                 bg=self.colors["bg"], fg=self.colors["highlight"]).pack(side=tk.LEFT)
        tk.Label(header, text="Molecular Flavor Pairing + AI Chef",
                 font=("Consolas", 10), bg=self.colors["bg"],
                 fg=self.colors["text_dim"]).pack(side=tk.LEFT, padx=20)

        n_ing = len(INGREDIENTS)
        n_comp = len(COMPOUNDS)
        total_links = sum(len(i.compounds) for i in INGREDIENTS.values())
        tk.Label(header, text=f"{n_ing} ingredients  |  {n_comp} compounds  |  {total_links} flavor links",
                 font=("Consolas", 9), bg=self.colors["bg"],
                 fg=self.colors["text_dim"]).pack(side=tk.RIGHT)

        # Notebook
        notebook = ttk.Notebook(self.root, style="Dark.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Pairing Explorer
        self.tab_pair = tk.Frame(notebook, bg=self.colors["bg"])
        notebook.add(self.tab_pair, text="  Pairing Explorer  ")
        self.build_pairing_tab()

        # Tab 2: Flavor Graph
        self.tab_graph = tk.Frame(notebook, bg=self.colors["bg"])
        notebook.add(self.tab_graph, text="  Flavor Graph  ")
        self.build_graph_tab()

        # Tab 3: Recipe Generator
        self.tab_recipe = tk.Frame(notebook, bg=self.colors["bg"])
        notebook.add(self.tab_recipe, text="  Recipe Generator  ")
        self.build_recipe_tab()

        # Tab 4: Build a Dish
        self.tab_build = tk.Frame(notebook, bg=self.colors["bg"])
        notebook.add(self.tab_build, text="  🍕 Build a Dish  ")
        self.build_dish_tab()

        # Tab 5: Bridge Finder
        self.tab_bridge = tk.Frame(notebook, bg=self.colors["bg"])
        notebook.add(self.tab_bridge, text="  Bridge Finder  ")
        self.build_bridge_tab()

        # Tab 5: My Pantry
        self.tab_pantry = tk.Frame(notebook, bg=self.colors["bg"])
        notebook.add(self.tab_pantry, text="  🧊 My Pantry  ")
        self.build_pantry_tab()

        # Tab 6: AI Chef
        self.tab_ai = tk.Frame(notebook, bg=self.colors["bg"])
        notebook.add(self.tab_ai, text="  🤖 AI Chef  ")
        self.build_ai_tab()

    # ─── PAIRING EXPLORER TAB ───────────────────────────────────

    def build_pairing_tab(self):
        left = tk.Frame(self.tab_pair, bg=self.colors["panel"], width=300)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left.pack_propagate(False)

        tk.Label(left, text="Select Ingredient", font=("Consolas", 12, "bold"),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(pady=(10, 5))

        search_frame = tk.Frame(left, bg=self.colors["panel"])
        search_frame.pack(fill=tk.X, padx=10)
        tk.Label(search_frame, text="Search:", bg=self.colors["panel"],
                 fg=self.colors["text_dim"], font=("Consolas", 9)).pack(side=tk.LEFT)
        self.pair_search_var = tk.StringVar()
        self.pair_search_var.trace_add("write", self._filter_pair_list)
        self.pair_search = tk.Entry(search_frame, textvariable=self.pair_search_var,
                                     bg=self.colors["accent"], fg=self.colors["text"],
                                     insertbackground=self.colors["text"],
                                     font=("Consolas", 10), relief=tk.FLAT)
        self.pair_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        cat_frame = tk.Frame(left, bg=self.colors["panel"])
        cat_frame.pack(fill=tk.X, padx=10, pady=5)
        self.pair_cat_var = tk.StringVar(value="All")
        cats = ["All"] + sorted(set(i.category for i in INGREDIENTS.values()))
        cat_menu = ttk.Combobox(cat_frame, textvariable=self.pair_cat_var,
                                values=cats, state="readonly", width=20)
        cat_menu.pack(fill=tk.X)
        cat_menu.bind("<<ComboboxSelected>>", lambda e: self._filter_pair_list())

        self.pair_listbox = tk.Listbox(left, bg=self.colors["accent"],
                                        fg=self.colors["text"], font=("Consolas", 10),
                                        selectbackground=self.colors["highlight"],
                                        relief=tk.FLAT, borderwidth=0)
        self.pair_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.pair_listbox.bind("<<ListboxSelect>>", self._on_pair_select)
        self._populate_pair_list()

        right = tk.Frame(self.tab_pair, bg=self.colors["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pair_info = tk.Frame(right, bg=self.colors["panel"], height=100)
        self.pair_info.pack(fill=tk.X, pady=(0, 5))
        self.pair_info.pack_propagate(False)

        self.pair_info_label = tk.Label(self.pair_info,
                                         text="← Select an ingredient to explore its flavor pairings",
                                         font=("Consolas", 11), bg=self.colors["panel"],
                                         fg=self.colors["text_dim"], justify=tk.LEFT, anchor="w")
        self.pair_info_label.pack(fill=tk.X, padx=15, pady=10)

        self.pair_compounds_label = tk.Label(self.pair_info, text="",
                                              font=("Consolas", 9), bg=self.colors["panel"],
                                              fg=self.colors["text_dim"], justify=tk.LEFT,
                                              anchor="w", wraplength=900)
        self.pair_compounds_label.pack(fill=tk.X, padx=15)

        tk.Label(right, text="Top Flavor Pairings (by shared aroma compounds)",
                 font=("Consolas", 11, "bold"), bg=self.colors["bg"],
                 fg=self.colors["text"]).pack(anchor="w", padx=5, pady=(5, 2))

        self.pair_results = tk.Text(right, bg=self.colors["panel"], fg=self.colors["text"],
                                     font=("Consolas", 10), relief=tk.FLAT, wrap=tk.WORD,
                                     padx=15, pady=10)
        self.pair_results.pack(fill=tk.BOTH, expand=True)
        self.pair_results.tag_config("header", foreground=self.colors["highlight"],
                                      font=("Consolas", 11, "bold"))
        self.pair_results.tag_config("score_high", foreground="#4CAF50")
        self.pair_results.tag_config("score_med", foreground="#FF9800")
        self.pair_results.tag_config("score_low", foreground="#888")
        self.pair_results.tag_config("compound", foreground="#2196F3")
        self.pair_results.tag_config("category", foreground="#9C27B0")
        self.pair_results.config(state=tk.DISABLED)

    def _populate_pair_list(self, filter_text="", filter_cat="All"):
        self.pair_listbox.delete(0, tk.END)
        for name in sorted(INGREDIENTS.keys()):
            ing = INGREDIENTS[name]
            if filter_cat != "All" and ing.category != filter_cat:
                continue
            if filter_text and filter_text.lower() not in name.lower() and filter_text.lower() not in ing.name.lower() and filter_text.lower() not in ing.flavor_notes.lower():
                continue
            display = f"{ing.name} — {ing.flavor_notes}  [{ing.category}]"
            self.pair_listbox.insert(tk.END, display)

    def _filter_pair_list(self, *args):
        self._populate_pair_list(self.pair_search_var.get(), self.pair_cat_var.get())

    def _on_pair_select(self, event):
        sel = self.pair_listbox.curselection()
        if not sel:
            return
        display = self.pair_listbox.get(sel[0])
        name = display.split(" — ")[0].strip()
        ing_key = None
        for k, v in INGREDIENTS.items():
            if v.name == name:
                ing_key = k
                break
        if not ing_key:
            return

        self.selected_ingredient = ing_key
        ing = INGREDIENTS[ing_key]
        self.pair_info_label.config(
            text=f"⚗ {ing.name.upper()}  |  {ing.category}  |  {ing.flavor_notes}",
            fg=self.colors["text_bright"])

        compound_descs = [f"{COMPOUNDS[c].name} ({COMPOUNDS[c].description})"
                         for c in ing.compounds if c in COMPOUNDS]
        self.pair_compounds_label.config(text=f"Compounds: {', '.join(compound_descs)}")

        pairings = self.engine.get_pairings(ing_key, top_n=25)
        self.pair_results.config(state=tk.NORMAL)
        self.pair_results.delete("1.0", tk.END)

        for i, p in enumerate(pairings):
            ing_p = INGREDIENTS[p["ingredient"]]
            score = p["score"]
            shared = p["shared_compounds"]
            if score > 0.5:
                tag = "score_high"
            elif score > 0.3:
                tag = "score_med"
            else:
                tag = "score_low"
            bar = "█" * max(int(score * 20), 1)

            self.pair_results.insert(tk.END, f"\n  #{i+1}  ", "header")
            self.pair_results.insert(tk.END, f"{ing_p.name}", "header")
            self.pair_results.insert(tk.END, f"  [{ing_p.category}]", "category")
            self.pair_results.insert(tk.END, f"\n       Score: ")
            self.pair_results.insert(tk.END, f"{bar} {score:.2f}", tag)
            shared_names = [COMPOUNDS[c].name for c in shared if c in COMPOUNDS]
            self.pair_results.insert(tk.END, f"\n       Shared: ")
            self.pair_results.insert(tk.END, f"{', '.join(shared_names)}", "compound")
            self.pair_results.insert(tk.END, f"\n       Notes: {ing_p.flavor_notes}\n")

        # ── Substitutes ──
        # A different question from the list above: a pairing goes WITH the
        # ingredient, a substitute stands IN for it. Same category, and the
        # same subtype where there is one, so a stock is never offered in
        # place of a vinaigrette.
        subs = self.engine.substitutes(ing_key, 6)
        if subs:
            self.pair_results.insert(
                tk.END, f"\n\n  NO {ing.name.upper()}? USE INSTEAD\n", "header")
            for s in subs:
                sub_ing = INGREDIENTS[s["ingredient"]]
                self.pair_results.insert(tk.END, f"    • {sub_ing.name}")
                if s["aroma_match"]:
                    distinctive = sorted(
                        s["shared_compounds"] - self.engine._boring_compounds,
                        key=lambda c: -self.engine._weight.get(c, 0))
                    names = [COMPOUNDS[c].name for c in distinctive[:3] if c in COMPOUNDS]
                    self.pair_results.insert(tk.END, f"  ({s['score']:.2f}) ", "score_high")
                    self.pair_results.insert(tk.END, f"shares {', '.join(names)}\n",
                                             "compound")
                else:
                    self.pair_results.insert(
                        tk.END, "  same role, different flavour — swap with care\n",
                        "score_low")

        self.pair_results.config(state=tk.DISABLED)

    # ─── FLAVOR GRAPH TAB ───────────────────────────────────────

    def build_graph_tab(self):
        controls = tk.Frame(self.tab_graph, bg=self.colors["panel"], height=45)
        controls.pack(fill=tk.X, pady=(0, 5))
        controls.pack_propagate(False)

        tk.Label(controls, text="Min Similarity:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5))

        self.graph_threshold = tk.DoubleVar(value=0.35)
        thresh_scale = tk.Scale(controls, from_=0.1, to=0.8, resolution=0.05,
                                orient=tk.HORIZONTAL, variable=self.graph_threshold,
                                bg=self.colors["panel"], fg=self.colors["text"],
                                highlightthickness=0, troughcolor=self.colors["accent"],
                                length=200, command=lambda v: self.draw_graph())
        thresh_scale.pack(side=tk.LEFT, padx=5)

        tk.Label(controls, text="Category:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(20, 5))

        self.graph_cat_var = tk.StringVar(value="All")
        cats = ["All"] + sorted(set(i.category for i in INGREDIENTS.values()))
        cat_menu = ttk.Combobox(controls, textvariable=self.graph_cat_var,
                                values=cats, state="readonly", width=12)
        cat_menu.pack(side=tk.LEFT, padx=5)
        cat_menu.bind("<<ComboboxSelected>>", lambda e: self.invalidate_graph())

        tk.Button(controls, text="⟳ Redraw", command=self.invalidate_graph,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 10), relief=tk.FLAT).pack(side=tk.LEFT, padx=20)

        self.graph_info = tk.Label(controls, text="", font=("Consolas", 9),
                                    bg=self.colors["panel"], fg=self.colors["text_dim"])
        self.graph_info.pack(side=tk.RIGHT, padx=10)

        self.graph_canvas = tk.Canvas(self.tab_graph, bg="#0d1117", highlightthickness=0)
        self.graph_canvas.pack(fill=tk.BOTH, expand=True)
        self.graph_canvas.bind("<Configure>", lambda e: self.draw_graph())
        self.graph_canvas.bind("<Button-1>", self._on_graph_click)
        self.graph_tooltip = None

    def invalidate_graph(self):
        self.graph_layout_dirty = True
        self.draw_graph()

    def draw_graph(self):
        canvas = self.graph_canvas
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 50 or h < 50:
            return

        threshold = self.graph_threshold.get()
        cat_filter = self.graph_cat_var.get()

        if cat_filter == "All":
            ing_names = list(INGREDIENTS.keys())
        else:
            ing_names = [n for n, i in INGREDIENTS.items() if i.category == cat_filter]

        if not ing_names:
            return

        if self.graph_layout_dirty or not self.graph_nodes:
            self.graph_nodes = {}
            cx, cy = w / 2, h / 2
            radius = min(w, h) * 0.38
            by_cat = defaultdict(list)
            for name in ing_names:
                by_cat[INGREDIENTS[name].category].append(name)
            angle = 0
            for cat, names in by_cat.items():
                cat_arc = 2 * math.pi * len(names) / len(ing_names)
                for i, name in enumerate(names):
                    a = angle + (i / len(names)) * cat_arc
                    r = radius * (0.7 + random.random() * 0.3)
                    x = cx + r * math.cos(a)
                    y = cy + r * math.sin(a)
                    self.graph_nodes[name] = (x, y)
                angle += cat_arc
            self.graph_layout_dirty = False

        edges = []
        for i in range(len(ing_names)):
            for j in range(i + 1, len(ing_names)):
                score, shared = self.engine.weighted_similarity(ing_names[i], ing_names[j])
                if score >= threshold:
                    edges.append((ing_names[i], ing_names[j], score, shared))

        self.graph_info.config(
            text=f"{len(ing_names)} nodes  |  {len(edges)} edges  |  threshold {threshold:.2f}")

        for n1, n2, score, shared in edges:
            if n1 in self.graph_nodes and n2 in self.graph_nodes:
                x1, y1 = self.graph_nodes[n1]
                x2, y2 = self.graph_nodes[n2]
                alpha = min(int(score * 255), 255)
                color = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
                canvas.create_line(x1, y1, x2, y2, fill=color, width=1 + score * 3)

        for name in ing_names:
            if name not in self.graph_nodes:
                continue
            x, y = self.graph_nodes[name]
            ing = INGREDIENTS[name]
            color = CATEGORIES.get(ing.category, "#555")
            r = 5 + len(ing.compounds) * 1.2
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="#fff", width=1)
            canvas.create_text(x, y + r + 8, text=ing.name, fill="#aaa", font=("Consolas", 7))

        lx, ly = 15, 15
        for cat, color in sorted(CATEGORIES.items()):
            count = sum(1 for n in ing_names if INGREDIENTS[n].category == cat)
            if count == 0:
                continue
            canvas.create_oval(lx, ly, lx + 10, ly + 10, fill=color, outline="")
            canvas.create_text(lx + 15, ly + 5, text=f"{cat} ({count})",
                              fill="#aaa", font=("Consolas", 8), anchor="w")
            ly += 16

    def _on_graph_click(self, event):
        closest = None
        closest_dist = float("inf")
        for name, (x, y) in self.graph_nodes.items():
            dist = math.sqrt((event.x - x) ** 2 + (event.y - y) ** 2)
            if dist < 20 and dist < closest_dist:
                closest = name
                closest_dist = dist

        if closest:
            self.selected_ingredient = closest
            self.draw_graph()
            x, y = self.graph_nodes[closest]
            ing = INGREDIENTS[closest]
            r = 5 + len(ing.compounds) * 1.2
            self.graph_canvas.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3,
                                          outline=self.colors["highlight"], width=3)
            compound_names = [COMPOUNDS[c].name for c in ing.compounds if c in COMPOUNDS]
            tip = f"{ing.name} [{ing.category}]\n{', '.join(compound_names)}"
            if self.graph_tooltip:
                self.graph_canvas.delete(self.graph_tooltip)
            self.graph_tooltip = self.graph_canvas.create_text(
                x, y - r - 12, text=tip, fill=self.colors["text_bright"],
                font=("Consolas", 9), anchor="s")

    # ─── RECIPE GENERATOR TAB ──────────────────────────────────

    def build_recipe_tab(self):
        top = tk.Frame(self.tab_recipe, bg=self.colors["panel"], height=60)
        top.pack(fill=tk.X, pady=(0, 5))
        top.pack_propagate(False)

        tk.Label(top, text="Seed:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5), pady=15)

        self.recipe_seed_var = tk.StringVar(value="(random)")
        seed_names = ["(random)"] + sorted(INGREDIENTS.keys())
        seed_menu = ttk.Combobox(top, textvariable=self.recipe_seed_var,
                                  values=seed_names, state="readonly", width=18)
        seed_menu.pack(side=tk.LEFT, padx=5, pady=15)

        tk.Label(top, text="Dish Type:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5))

        self.recipe_type_var = tk.StringVar(value="Any")
        type_menu = ttk.Combobox(top, textvariable=self.recipe_type_var,
                                  values=DISH_TYPES, state="readonly", width=18)
        type_menu.pack(side=tk.LEFT, padx=5, pady=15)

        tk.Button(top, text="⚗ Generate", command=self._generate_recipe,
                  bg=self.colors["highlight"], fg=self.colors["text_bright"],
                  font=("Consolas", 11, "bold"), relief=tk.FLAT, padx=15,
                  cursor="hand2").pack(side=tk.LEFT, padx=10, pady=15)

        tk.Button(top, text="🎲 Surprise!", command=self._surprise_recipe,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 11), relief=tk.FLAT, padx=12,
                  cursor="hand2").pack(side=tk.LEFT, padx=5, pady=15)

        tk.Button(top, text="🤖 Send to AI Chef →", command=self._send_to_ai,
                  bg="#1a5276", fg=self.colors["text"],
                  font=("Consolas", 10, "bold"), relief=tk.FLAT, padx=12,
                  cursor="hand2").pack(side=tk.LEFT, padx=15, pady=15)

        tk.Button(top, text="💾 Save", command=self._save_current_recipe,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 10), relief=tk.FLAT, padx=10,
                  cursor="hand2").pack(side=tk.LEFT, padx=5, pady=15)

        # Saved recipes bar
        saved_bar = tk.Frame(self.tab_recipe, bg=self.colors["panel"], height=38)
        saved_bar.pack(fill=tk.X, pady=(0, 3))
        saved_bar.pack_propagate(False)

        tk.Label(saved_bar, text="📖 Saved:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5), pady=5)

        self.saved_recipe_var = tk.StringVar(value="")
        self.saved_recipe_menu = ttk.Combobox(saved_bar, textvariable=self.saved_recipe_var,
                                               values=[], state="readonly", width=55)
        self.saved_recipe_menu.pack(side=tk.LEFT, padx=5, pady=5)

        tk.Button(saved_bar, text="Load", command=self._load_saved_recipe,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 9), relief=tk.FLAT, padx=8,
                  cursor="hand2").pack(side=tk.LEFT, padx=3, pady=5)

        tk.Button(saved_bar, text="Delete", command=self._delete_saved_recipe,
                  bg="#5c1a1a", fg=self.colors["text"],
                  font=("Consolas", 9), relief=tk.FLAT, padx=8,
                  cursor="hand2").pack(side=tk.LEFT, padx=3, pady=5)

        self.save_status = tk.Label(saved_bar, text="", font=("Consolas", 9),
                                     bg=self.colors["panel"], fg=self.colors["success"])
        self.save_status.pack(side=tk.LEFT, padx=10)

        self._refresh_saved_list()

        self.recipe_output = tk.Text(self.tab_recipe, bg=self.colors["panel"],
                                      fg=self.colors["text"], font=("Consolas", 11),
                                      relief=tk.FLAT, wrap=tk.WORD, padx=20, pady=15)
        self.recipe_output.pack(fill=tk.BOTH, expand=True)
        self.recipe_output.tag_config("title", foreground=self.colors["highlight"],
                                       font=("Consolas", 16, "bold"))
        self.recipe_output.tag_config("section", foreground=self.colors["warning"],
                                       font=("Consolas", 12, "bold"))
        self.recipe_output.tag_config("compound", foreground="#2196F3")
        self.recipe_output.tag_config("novelty_high", foreground="#4CAF50",
                                       font=("Consolas", 12, "bold"))
        self.recipe_output.tag_config("novelty_med", foreground="#FF9800",
                                       font=("Consolas", 12, "bold"))
        self.recipe_output.tag_config("novelty_low", foreground="#888", font=("Consolas", 12))
        self.recipe_output.tag_config("technique", foreground="#E0E0E0", font=("Consolas", 11))
        self.recipe_output.config(state=tk.DISABLED)

        self._show_recipe_welcome()

    def _show_recipe_welcome(self):
        self.recipe_output.config(state=tk.NORMAL)
        self.recipe_output.delete("1.0", tk.END)
        self.recipe_output.insert(tk.END, "\n\n")
        self.recipe_output.insert(tk.END, "  ⚗  FlavorForge Recipe Generator\n\n", "title")
        self.recipe_output.insert(tk.END, "  Pick a seed ingredient or hit 'Surprise Me!' to discover\n")
        self.recipe_output.insert(tk.END, "  scientifically novel flavor combinations.\n\n")
        self.recipe_output.insert(tk.END, "  Every pairing is backed by shared aroma compounds —\n")
        self.recipe_output.insert(tk.END, "  real molecular connections, not vibes.\n\n")
        self.recipe_output.insert(tk.END, "  Use '🤖 Send to AI Chef' to get a full recipe\n")
        self.recipe_output.insert(tk.END, "  with quantities and step-by-step instructions.\n")
        self.recipe_output.config(state=tk.DISABLED)

    def _display_recipe(self, recipe):
        self.current_recipe = recipe
        self.recipe_output.config(state=tk.NORMAL)
        self.recipe_output.delete("1.0", tk.END)

        if "error" in recipe:
            self.recipe_output.insert(tk.END, f"\n  Error: {recipe['error']}")
            self.recipe_output.config(state=tk.DISABLED)
            return

        self.recipe_output.insert(tk.END, "\n")
        self.recipe_output.insert(tk.END, f"  {recipe['name']}\n", "title")
        dtype = recipe.get("dish_type", "")
        if dtype:
            self.recipe_output.insert(tk.END, f"  [{dtype}]\n\n", "novelty_low")
        else:
            self.recipe_output.insert(tk.END, "\n")

        # ── Dish summary ──
        all_keys = [v for v in recipe["ingredients"].values() if v in INGREDIENTS]
        all_names = [INGREDIENTS[k].name for k in all_keys]
        self.recipe_output.insert(tk.END, "  WHAT THIS IS\n", "section")

        # Show each ingredient with its category, description, and role
        role_labels = {
            "protein": "the protein", "sauce": "the sauce base", "vegetable": "the vegetable",
            "cheese": "richness/cheese", "spice": "seasoning", "herb": "the herb",
            "fruit": "brightness/fruit", "grain": "the starch", "nut": "crunch/nut",
            "mushroom": "umami depth", "fermented": "complexity/fermented",
            "sweetener": "sweetness", "citrus": "acid", "legume": "heartiness",
            "allium": "aromatic base", "garnish": "garnish", "accent": "accent flavor",
            "oil": "the cooking fat", "noodle": "the noodle", "bread": "the bread",
            "rice_type": "the rice", "broth": "the broth", "seafood": "the seafood",
            "cooking_sauce": "the sauce", "dressing": "the dressing",
        }

        for slot, ing_name in recipe["ingredients"].items():
            if ing_name in INGREDIENTS:
                ing = INGREDIENTS[ing_name]
                role = role_labels.get(slot, slot)
                self.recipe_output.insert(tk.END, f"    • ")
                self.recipe_output.insert(tk.END, f"{ing.name}", "novelty_high")
                self.recipe_output.insert(tk.END, f"  [{ing.category}]", "compound")
                self.recipe_output.insert(tk.END, f" — {ing.flavor_notes}")
                self.recipe_output.insert(tk.END, f"\n      Role: {role}\n", "novelty_low")

        # Identify the star ingredient (most connections)
        conn_counts = defaultdict(int)
        for conn in recipe.get("connections", []):
            for p in conn["pair"]:
                conn_counts[p] += 1
        star = max(conn_counts, key=conn_counts.get) if conn_counts else (all_keys[0] if all_keys else None)

        # Novelty bar
        novelty = recipe["novelty"]
        if novelty > 0.6:
            tag, label = "novelty_high", "HIGHLY NOVEL"
        elif novelty > 0.4:
            tag, label = "novelty_med", "MODERATELY NOVEL"
        else:
            tag, label = "novelty_low", "CLASSIC PAIRING"

        bar = "█" * int(novelty * 30) + "░" * (30 - int(novelty * 30))
        self.recipe_output.insert(tk.END, f"    Novelty: [{bar}] ", tag)
        self.recipe_output.insert(tk.END, f"{novelty:.0%} — {label}\n", tag)

        # ── Why these ingredients pair ──
        self.recipe_output.insert(tk.END, "\n  WHY IT WORKS\n", "section")

        # Compute compound rarity for filtering
        boring = self.engine._boring_compounds

        if recipe.get("connections"):
            for conn in recipe["connections"]:
                a, b = conn["pair"]
                a_name = INGREDIENTS[a].name if a in INGREDIENTS else a
                b_name = INGREDIENTS[b].name if b in INGREDIENTS else b

                # Filter to interesting shared compounds
                interesting = [c for c in conn["shared"] if c in COMPOUNDS and c not in boring]
                boring_shared = [c for c in conn["shared"] if c in COMPOUNDS and c in boring]

                if interesting:
                    descs = [COMPOUNDS[c].description for c in interesting[:3]]
                    self.recipe_output.insert(tk.END, f"    {a_name} + {b_name}: ")
                    self.recipe_output.insert(tk.END, f"share {', '.join(descs)} notes\n", "compound")
                elif boring_shared:
                    self.recipe_output.insert(tk.END, f"    {a_name} + {b_name}: ")
                    self.recipe_output.insert(tk.END, "subtle background harmony\n", "novelty_low")

            # Note any contrast pairings
            all_pairs = set()
            for conn in recipe["connections"]:
                all_pairs.add(frozenset(conn["pair"]))
            for i in range(len(all_keys)):
                for j in range(i + 1, len(all_keys)):
                    pair = frozenset([all_keys[i], all_keys[j]])
                    if pair not in all_pairs:
                        a_name = INGREDIENTS[all_keys[i]].name
                        b_name = INGREDIENTS[all_keys[j]].name
                        self.recipe_output.insert(tk.END,
                            f"    {a_name} + {b_name}: ", "novelty_low")
                        self.recipe_output.insert(tk.END,
                            "contrast pairing — different flavors that balance\n", "novelty_low")
        else:
            self.recipe_output.insert(tk.END,
                "    Pure contrast dish — the tension between different\n"
                "    flavor profiles is the point.\n")

        # ── Texture & taste balance ──
        if all_keys:
            balance = analyze_balance(all_keys)

            self.recipe_output.insert(tk.END, "\n  BALANCE CHECK\n", "section")
            self.recipe_output.insert(tk.END,
                f"    Textures: {', '.join(balance['textures'])}\n", "novelty_low")

            if balance["taste_strong"]:
                self.recipe_output.insert(tk.END,
                    f"    Strong in: {', '.join(balance['taste_strong'])}\n", "novelty_high")

            all_tips = balance["texture_suggestions"] + balance["taste_suggestions"]
            if all_tips:
                for tip in all_tips:
                    self.recipe_output.insert(tk.END, f"    💡 {tip}\n", "compound")
            else:
                self.recipe_output.insert(tk.END, "    ✓ Well balanced!\n", "novelty_high")

        # ── Technique ──
        self.recipe_output.insert(tk.END, "\n  ROUGH OUTLINE\n", "section")
        self.recipe_output.insert(tk.END, f"    {recipe['technique']}\n", "technique")
        self.recipe_output.insert(tk.END,
            "    (Send to AI Chef for a proper recipe with quantities & steps)\n", "novelty_low")

        self.recipe_output.insert(tk.END, "\n\n  ─── Hit 🤖 Send to AI Chef for the full recipe ───\n")
        self.recipe_output.config(state=tk.DISABLED)

    def _generate_recipe(self):
        seed = self.recipe_seed_var.get()
        if seed == "(random)" or not seed:
            seed = None
        dish_type = self.recipe_type_var.get()
        recipe = self.engine.generate_recipe(seed_ingredient=seed, dish_type=dish_type)
        self._display_recipe(recipe)

    def _surprise_recipe(self):
        dish_type = self.recipe_type_var.get()
        recipe = self.engine.surprise_me(dish_type=dish_type)
        self._display_recipe(recipe)

    def _send_to_ai(self):
        """Send current recipe to AI Chef tab."""
        if not self.current_recipe or "error" in self.current_recipe:
            messagebox.showinfo("No Recipe", "Generate a recipe first, then send it to AI Chef.")
            return
        notebook = self.tab_ai.master
        notebook.select(self.tab_ai)
        self._ai_generate_from_recipe(self.current_recipe)

    # ─── SAVED RECIPES ─────────────────────────────────────────

    def _recipes_path(self):
        return os.path.join(os.path.expanduser("~"), ".flavorforge_saved_recipes.json")

    def _load_all_saved(self) -> List:
        try:
            # utf-8-sig: these files are hand-editable, and Notepad writes a
            # BOM that plain utf-8 rejects outright.
            with open(self._recipes_path(), "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []
        # A file of the wrong shape would otherwise fail much later, in the
        # middle of rendering the list.
        return data if isinstance(data, list) else []

    def _save_all(self, recipes: List) -> bool:
        return _write_json_atomic(self._recipes_path(), recipes)

    def _refresh_saved_list(self):
        saved = self._load_all_saved()
        names = [f"{r.get('name', 'Untitled')}  [{r.get('dish_type', '')}]" for r in saved]
        self.saved_recipe_menu.config(values=names)
        if names:
            self.saved_recipe_var.set(names[0])
        else:
            self.saved_recipe_var.set("")

    def _save_current_recipe(self):
        if not self.current_recipe or "error" in self.current_recipe:
            messagebox.showinfo("No Recipe", "Generate a recipe first!")
            return

        saved = self._load_all_saved()

        # Convert sets to lists for JSON serialization
        recipe_data = {}
        for k, v in self.current_recipe.items():
            if k == "connections":
                serialized_conns = []
                for conn in v:
                    serialized_conns.append({
                        "pair": list(conn["pair"]),
                        "shared": list(conn["shared"]),
                    })
                recipe_data[k] = serialized_conns
            elif k == "ingredients":
                recipe_data[k] = dict(v)
            else:
                recipe_data[k] = v

        import datetime
        recipe_data["saved_at"] = datetime.datetime.now().isoformat()

        # Check for duplicates by name
        existing_names = [r.get("name") for r in saved]
        if recipe_data.get("name") in existing_names:
            # Update existing
            for i, r in enumerate(saved):
                if r.get("name") == recipe_data.get("name"):
                    saved[i] = recipe_data
                    break
            self.save_status.config(text="Updated!", fg=self.colors["warning"])
        else:
            saved.insert(0, recipe_data)  # Newest first
            self.save_status.config(text="Saved!", fg=self.colors["success"])

        self._save_all(saved)
        self._refresh_saved_list()
        self.root.after(3000, lambda: self.save_status.config(text=""))

    def _load_saved_recipe(self):
        saved = self._load_all_saved()
        if not saved:
            messagebox.showinfo("Empty", "No saved recipes yet!")
            return

        idx = self.saved_recipe_menu.current()
        if idx < 0 or idx >= len(saved):
            return

        recipe = saved[idx]

        # Reconvert lists back to sets for connections
        if "connections" in recipe:
            for conn in recipe["connections"]:
                conn["pair"] = tuple(conn["pair"])
                conn["shared"] = set(conn["shared"])

        self._display_recipe(recipe)
        self.save_status.config(text="Loaded", fg=self.colors["text_dim"])
        self.root.after(2000, lambda: self.save_status.config(text=""))

    def _delete_saved_recipe(self):
        saved = self._load_all_saved()
        if not saved:
            return

        idx = self.saved_recipe_menu.current()
        if idx < 0 or idx >= len(saved):
            return

        name = saved[idx].get("name", "this recipe")
        if messagebox.askyesno("Delete Recipe", f"Delete '{name}'?"):
            saved.pop(idx)
            self._save_all(saved)
            self._refresh_saved_list()
            self.save_status.config(text="Deleted", fg=self.colors["highlight"])
            self.root.after(2000, lambda: self.save_status.config(text=""))

    # ─── BUILD A DISH TAB ───────────────────────────────────────

    def build_dish_tab(self):
        # ── Top: dish type + template picker ──
        top = tk.Frame(self.tab_build, bg=self.colors["panel"], height=55)
        top.pack(fill=tk.X, pady=(0, 3))
        top.pack_propagate(False)

        tk.Label(top, text="I want to make:", font=("Consolas", 12, "bold"),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5), pady=10)

        self.build_type_var = tk.StringVar(value="Any")
        type_menu = ttk.Combobox(top, textvariable=self.build_type_var,
                                  values=DISH_TYPES, state="readonly", width=20)
        type_menu.pack(side=tk.LEFT, padx=5, pady=10)
        type_menu.bind("<<ComboboxSelected>>", self._on_build_type_change)

        tk.Label(top, text="Template:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(20, 5))

        self.build_template_var = tk.StringVar(value="")
        self.build_template_menu = ttk.Combobox(top, textvariable=self.build_template_var,
                                                 values=[], state="readonly", width=50)
        self.build_template_menu.pack(side=tk.LEFT, padx=5, pady=10)
        self.build_template_menu.bind("<<ComboboxSelected>>", self._on_build_template_change)

        # ── Middle: slot fillers ──
        mid = tk.Frame(self.tab_build, bg=self.colors["bg"])
        mid.pack(fill=tk.BOTH, expand=True)

        # Left: slot selection panel
        self.build_slots_frame = tk.Frame(mid, bg=self.colors["panel"], width=620)
        self.build_slots_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        self.build_slots_frame.pack_propagate(False)

        self.build_slots_header = tk.Label(self.build_slots_frame,
            text="← Pick a dish type and template to start",
            font=("Consolas", 11), bg=self.colors["panel"],
            fg=self.colors["text_dim"], wraplength=380, justify=tk.LEFT)
        self.build_slots_header.pack(pady=15, padx=15)

        self.build_slot_widgets = []  # List of (slot_name, combobox) tuples
        self.build_slot_vars = {}     # slot_name -> StringVar

        # Bottom buttons in slot panel
        self.build_btn_frame = tk.Frame(self.build_slots_frame, bg=self.colors["panel"])
        self.build_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        tk.Button(self.build_btn_frame, text="⚗ Build Recipe",
                  command=self._build_dish_generate,
                  bg=self.colors["highlight"], fg=self.colors["text_bright"],
                  font=("Consolas", 11, "bold"), relief=tk.FLAT, padx=15,
                  cursor="hand2").pack(side=tk.LEFT, padx=5)

        tk.Button(self.build_btn_frame, text="🤖 → AI Chef",
                  command=self._build_dish_to_ai,
                  bg="#1a5276", fg=self.colors["text"],
                  font=("Consolas", 10), relief=tk.FLAT, padx=10,
                  cursor="hand2").pack(side=tk.LEFT, padx=10)

        tk.Button(self.build_btn_frame, text="🎲 Auto-Fill Best",
                  command=self._build_dish_autofill,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 9), relief=tk.FLAT, padx=8,
                  cursor="hand2").pack(side=tk.RIGHT, padx=5)

        tk.Button(self.build_btn_frame, text="💾 Save",
                  command=self._save_current_recipe,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 9), relief=tk.FLAT, padx=8,
                  cursor="hand2").pack(side=tk.RIGHT, padx=5)

        # Right: live preview + pairing info
        self.build_output = tk.Text(mid, bg=self.colors["panel"], fg=self.colors["text"],
                                     font=("Consolas", 10), relief=tk.FLAT, wrap=tk.WORD,
                                     padx=20, pady=15)
        self.build_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.build_output.tag_config("title", foreground=self.colors["highlight"],
                                      font=("Consolas", 14, "bold"))
        self.build_output.tag_config("section", foreground=self.colors["warning"],
                                      font=("Consolas", 11, "bold"))
        self.build_output.tag_config("compound", foreground="#2196F3")
        self.build_output.tag_config("good", foreground="#4CAF50",
                                      font=("Consolas", 10, "bold"))
        self.build_output.tag_config("suggest", foreground="#4CAF50")
        self.build_output.tag_config("dim", foreground="#666")
        self.build_output.tag_config("technique", foreground="#bbb", font=("Consolas", 10))
        self.build_output.config(state=tk.DISABLED)

        self._build_show_welcome()
        self._on_build_type_change()  # Populate initial template list

        # Store state
        self.build_current_template = None
        self.build_current_recipe = None

    def _build_show_welcome(self):
        self.build_output.config(state=tk.NORMAL)
        self.build_output.delete("1.0", tk.END)
        self.build_output.insert(tk.END, "\n")
        self.build_output.insert(tk.END, "  🍕  Build a Dish\n\n", "title")
        self.build_output.insert(tk.END, "  1. Pick what kind of dish you want\n")
        self.build_output.insert(tk.END, "  2. Choose a template\n")
        self.build_output.insert(tk.END, "  3. Fill in each ingredient slot\n")
        self.build_output.insert(tk.END, "     (suggestions ranked by molecular pairing)\n\n")
        self.build_output.insert(tk.END, "  Or hit 'Auto-Fill Best' to let FlavorForge\n")
        self.build_output.insert(tk.END, "  pick the strongest pairings for you.\n")
        self.build_output.config(state=tk.DISABLED)

    def _on_build_type_change(self, event=None):
        dtype = self.build_type_var.get()
        if dtype == "Any":
            templates = DISH_TEMPLATES
        else:
            templates = [t for t in DISH_TEMPLATES if t.get("dish_type") == dtype]

        names = [t["name"] for t in templates]
        self.build_template_menu.config(values=names)
        if names:
            self.build_template_var.set(names[0])
            self._on_build_template_change()

    def _on_build_template_change(self, event=None):
        tname = self.build_template_var.get()
        template = None
        for t in DISH_TEMPLATES:
            if t["name"] == tname:
                template = t
                break
        if not template:
            return

        self.build_current_template = template

        # Clear old slot widgets
        for w in self.build_slot_widgets:
            w.destroy()
        self.build_slot_widgets = []
        self.build_slot_vars = {}

        self.build_slots_header.config(
            text=f"Fill in the ingredients for:\n{tname}",
            fg=self.colors["text_bright"])

        for slot in template["structure"]:
            frame = tk.Frame(self.build_slots_frame, bg=self.colors["panel"])
            frame.pack(fill=tk.X, padx=15, pady=2)
            self.build_slot_widgets.append(frame)

            cand_keys = get_slot_candidates(slot)
            candidates = sorted([
                (f"{INGREDIENTS[n].name} — {INGREDIENTS[n].flavor_notes}", n)
                for n in cand_keys if n in INGREDIENTS
            ])

            display_names = ["(choose)"] + [c[0] for c in candidates]

            # Row 1: label + dropdown
            row1 = tk.Frame(frame, bg=self.colors["panel"])
            row1.pack(fill=tk.X)

            tk.Label(row1, text=f"{slot.upper()}:",
                     font=("Consolas", 10, "bold"),
                     bg=self.colors["panel"], fg=self.colors["warning"],
                     width=12, anchor="e").pack(side=tk.LEFT, padx=(0, 5))

            var = tk.StringVar(value="(choose)")
            self.build_slot_vars[slot] = (var, candidates)

            combo = ttk.Combobox(row1, textvariable=var,
                                  values=display_names, state="readonly", width=45)
            combo.pack(side=tk.LEFT, padx=5)
            combo.bind("<<ComboboxSelected>>",
                       lambda e, s=slot: self._on_build_slot_change(s))

            # Row 2: suggestion line
            suggest_label = tk.Label(frame, text="",
                                      font=("Consolas", 9),
                                      bg=self.colors["panel"],
                                      fg=self.colors["success"],
                                      anchor="w")
            suggest_label.pack(fill=tk.X, padx=(105, 5))

            frame._suggest_label = suggest_label
            frame._slot_name = slot

        self._build_update_suggestions()
        self._build_update_preview()

    def _on_build_slot_change(self, slot):
        self._build_update_suggestions()
        self._build_update_preview()

    def _get_build_chosen(self) -> dict:
        """Get currently chosen ingredients as {slot: ingredient_key}."""
        chosen = {}
        for slot, (var, candidates) in self.build_slot_vars.items():
            display = var.get()
            if display and display != "(choose)":
                for cand_display, cand_key in candidates:
                    if cand_display == display:
                        chosen[slot] = cand_key
                        break
        return chosen

    def _build_update_suggestions(self):
        """Update suggestion labels with compound, texture, and taste-aware picks."""
        chosen = self._get_build_chosen()
        chosen_keys = set(chosen.values())
        chosen_list = list(chosen_keys)

        # Get current balance state
        balance = analyze_balance(chosen_list) if chosen_list else None

        for frame in self.build_slot_widgets:
            if not hasattr(frame, '_slot_name'):
                continue
            slot = frame._slot_name
            label = frame._suggest_label

            if slot in chosen:
                textures = get_textures(chosen[slot])
                label.config(text=f"  ✓ {', '.join(textures)}", fg=self.colors["text_dim"])
                continue

            if not chosen_keys:
                label.config(text="  pick anything to start", fg=self.colors["text_dim"])
                continue

            var, candidates = self.build_slot_vars[slot]

            # Score each candidate by: compound pairing + texture bonus + taste bonus
            scored = []
            for cand_display, cand_key in candidates:
                if cand_key in chosen_keys:
                    continue

                # Compound score
                compound_score = sum(
                    self.engine.weighted_similarity(cand_key, ck)[0]
                    for ck in chosen_keys
                )

                # Texture bonus: reward adding missing textures
                texture_bonus = 0
                if balance and not balance["has_crunch"]:
                    cand_tex = get_textures(cand_key)
                    if any(t in cand_tex for t in ["crunchy", "crispy", "crisp", "crusty", "snappy"]):
                        texture_bonus += 0.3

                # Taste bonus: reward filling gaps
                taste_bonus = 0
                if balance:
                    cand_taste = get_taste_profile(cand_key)
                    for weak_dim in balance["taste_weak"]:
                        dim_map = {"acid/sour": "sour", "fat": "fatty", "umami": "umami", "salt": "salty"}
                        dim_key = dim_map.get(weak_dim, weak_dim)
                        if cand_taste.get(dim_key, 0) > 0.3:
                            taste_bonus += 0.25

                total = compound_score + texture_bonus + taste_bonus
                scored.append((total, cand_display, cand_key, compound_score, texture_bonus, taste_bonus))

            scored.sort(reverse=True)

            if scored and scored[0][0] > 0:
                best = scored[0]
                # Build reason text
                reasons = []
                if best[3] > 0.1:
                    reasons.append("flavor match")
                if best[4] > 0:
                    reasons.append("adds crunch")
                if best[5] > 0:
                    reasons.append("fills taste gap")

                reason_str = f" ({', '.join(reasons)})" if reasons else ""
                top3 = [s[1] for s in scored[:3]]
                label.config(
                    text=f"  ★ {top3[0]}{reason_str}  |  also: {', '.join(top3[1:3])}",
                    fg=self.colors["success"])
            else:
                label.config(text="", fg=self.colors["text_dim"])

    def _build_update_preview(self):
        """Update the right-side preview with current selections."""
        chosen = self._get_build_chosen()

        self.build_output.config(state=tk.NORMAL)
        self.build_output.delete("1.0", tk.END)

        if not self.build_current_template:
            self._build_show_welcome()
            return

        template = self.build_current_template
        total_slots = len(template["structure"])
        filled_slots = len(chosen)

        self.build_output.insert(tk.END, "\n")
        self.build_output.insert(tk.END, f"  {template['name']}\n", "title")
        dtype = template.get("dish_type", "")
        self.build_output.insert(tk.END, f"  [{dtype}]  ", "dim")
        self.build_output.insert(tk.END,
            f"{filled_slots}/{total_slots} slots filled\n\n", "dim")

        if filled_slots == 0:
            self.build_output.insert(tk.END,
                "  Pick ingredients for each slot on the left.\n")
            self.build_output.insert(tk.END,
                "  Watch for ★ suggestions — those are the\n")
            self.build_output.insert(tk.END,
                "  strongest molecular pairings with your picks.\n")
            self.build_output.config(state=tk.DISABLED)
            return

        # Show chosen ingredients and their connections
        self.build_output.insert(tk.END, "  YOUR PICKS\n", "section")
        for slot, key in chosen.items():
            ing = INGREDIENTS[key]
            compounds = [COMPOUNDS[c].description for c in ing.compounds if c in COMPOUNDS][:4]
            self.build_output.insert(tk.END, f"    {slot}: ")
            self.build_output.insert(tk.END, f"{ing.name}", "good")
            self.build_output.insert(tk.END, f"  — {', '.join(compounds)}\n", "dim")

        # Show pairwise connections
        keys = list(chosen.values())
        if len(keys) >= 2:
            self.build_output.insert(tk.END, "\n  FLAVOR CONNECTIONS\n", "section")
            total_score = 0
            total_conns = 0
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    score, shared = self.engine.weighted_similarity(keys[i], keys[j])
                    if shared:
                        total_score += score
                        total_conns += 1
                        a_name = INGREDIENTS[keys[i]].name
                        b_name = INGREDIENTS[keys[j]].name
                        shared_names = [COMPOUNDS[c].name for c in shared if c in COMPOUNDS][:4]
                        self.build_output.insert(tk.END, f"    {a_name} ↔ {b_name}: ")
                        self.build_output.insert(tk.END,
                            f"{', '.join(shared_names)}\n", "compound")
                    else:
                        a_name = INGREDIENTS[keys[i]].name
                        b_name = INGREDIENTS[keys[j]].name
                        self.build_output.insert(tk.END,
                            f"    {a_name} ↔ {b_name}: ", "dim")
                        self.build_output.insert(tk.END, "no shared compounds\n", "dim")

            if total_conns > 0:
                avg = total_score / total_conns
                bar = "█" * int(avg * 20)
                tag = "good" if avg > 0.3 else "dim"
                self.build_output.insert(tk.END, f"\n  Overall flavor score: ")
                self.build_output.insert(tk.END, f"{bar} {avg:.2f}\n", tag)

        # Balance analysis
        if len(keys) >= 2:
            balance = analyze_balance(keys)

            self.build_output.insert(tk.END, "\n  TEXTURE\n", "section")
            self.build_output.insert(tk.END, f"    {', '.join(balance['textures'])}\n", "dim")
            for tip in balance["texture_suggestions"]:
                self.build_output.insert(tk.END, f"    💡 {tip}\n", "suggest")

            self.build_output.insert(tk.END, "\n  TASTE BALANCE\n", "section")
            if balance["taste_strong"]:
                self.build_output.insert(tk.END,
                    f"    Strong in: {', '.join(balance['taste_strong'])}\n", "good")
            if balance["taste_weak"]:
                self.build_output.insert(tk.END,
                    f"    Missing: {', '.join(balance['taste_weak'])}\n", "dim")
            for tip in balance["taste_suggestions"]:
                self.build_output.insert(tk.END, f"    💡 {tip}\n", "suggest")

            if not balance["taste_suggestions"] and not balance["texture_suggestions"]:
                self.build_output.insert(tk.END, "    ✓ Well balanced!\n", "good")

        # Show technique preview if all slots filled
        if filled_slots == total_slots:
            self.build_output.insert(tk.END, "\n  TECHNIQUE\n", "section")
            technique = template["technique"]
            for slot, key in chosen.items():
                technique = technique.replace(f"{{{slot}}}", INGREDIENTS[key].name)
            self.build_output.insert(tk.END, f"    {technique}\n", "technique")
            self.build_output.insert(tk.END,
                "\n  ✓ All slots filled! Hit 'Build Recipe' or '→ AI Chef'\n", "good")

        self.build_output.config(state=tk.DISABLED)

    def _build_dish_autofill(self):
        """Auto-fill all empty slots with best molecular pairings."""
        if not self.build_current_template:
            return

        chosen = self._get_build_chosen()
        chosen_keys = set(chosen.values())

        for slot in self.build_current_template["structure"]:
            if slot in chosen:
                continue

            var, candidates = self.build_slot_vars[slot]

            best_key = None
            best_score = -1

            for cand_display, cand_key in candidates:
                if cand_key in chosen_keys:
                    continue

                if chosen_keys:
                    total = sum(
                        self.engine.weighted_similarity(cand_key, ck)[0]
                        for ck in chosen_keys
                    )
                else:
                    # First slot: pick something interesting (random)
                    total = random.random()

                if total > best_score:
                    best_score = total
                    best_key = cand_key
                    best_display = cand_display

            if best_key:
                var.set(best_display)
                chosen[slot] = best_key
                chosen_keys.add(best_key)

        self._build_update_suggestions()
        self._build_update_preview()

    def _build_dish_generate(self):
        """Generate the final recipe from user's picks."""
        chosen = self._get_build_chosen()
        if not chosen or not self.build_current_template:
            messagebox.showinfo("Incomplete", "Pick a template and fill in at least some slots!")
            return

        # Auto-fill any remaining empty slots
        self._build_dish_autofill()
        chosen = self._get_build_chosen()

        template = self.build_current_template

        # Build name
        slot_display = {s: INGREDIENTS[k].name for s, k in chosen.items() if k in INGREDIENTS}
        aliases = {"veg": "vegetable", "cheese": "dairy"}
        name = template["name"]
        technique = template["technique"]
        for slot, display in slot_display.items():
            name = name.replace(f"{{{slot}}}", display.title())
            technique = technique.replace(f"{{{slot}}}", display)
        for alias, real_slot in aliases.items():
            if real_slot in slot_display:
                name = name.replace(f"{{{alias}}}", slot_display[real_slot].title())
                technique = technique.replace(f"{{{alias}}}", slot_display[real_slot])

        # Build connections
        keys = list(chosen.values())
        connections = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                _, shared = self.engine.weighted_similarity(keys[i], keys[j])
                if shared:
                    connections.append({"pair": (keys[i], keys[j]), "shared": shared})

        self.build_current_recipe = {
            "name": name,
            "technique": technique,
            "ingredients": chosen,
            "novelty": self.engine.novelty_score(keys),
            "connections": connections,
            "dish_type": template.get("dish_type", ""),
        }

        # Show in recipe generator tab format
        self.current_recipe = self.build_current_recipe
        self._display_recipe(self.build_current_recipe)

        # Switch to recipe tab to show result
        notebook = self.tab_recipe.master
        notebook.select(self.tab_recipe)

    def _build_dish_to_ai(self):
        """Send the built dish to AI Chef."""
        self._build_dish_generate()
        if self.current_recipe and "error" not in self.current_recipe:
            notebook = self.tab_ai.master
            notebook.select(self.tab_ai)
            self._ai_generate_from_recipe(self.current_recipe)

    # ─── BRIDGE FINDER TAB ──────────────────────────────────────

    def build_bridge_tab(self):
        top = tk.Frame(self.tab_bridge, bg=self.colors["panel"], height=60)
        top.pack(fill=tk.X, pady=(0, 5))
        top.pack_propagate(False)

        tk.Label(top, text="Ingredient A:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5), pady=15)

        self.bridge_a_var = tk.StringVar(value="chocolate")
        a_menu = ttk.Combobox(top, textvariable=self.bridge_a_var,
                               values=sorted(INGREDIENTS.keys()), state="readonly", width=15)
        a_menu.pack(side=tk.LEFT, padx=5, pady=15)

        tk.Label(top, text="↔", font=("Consolas", 14, "bold"),
                 bg=self.colors["panel"], fg=self.colors["highlight"]).pack(side=tk.LEFT, padx=10)

        tk.Label(top, text="Ingredient B:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(0, 5), pady=15)

        self.bridge_b_var = tk.StringVar(value="salmon")
        b_menu = ttk.Combobox(top, textvariable=self.bridge_b_var,
                               values=sorted(INGREDIENTS.keys()), state="readonly", width=15)
        b_menu.pack(side=tk.LEFT, padx=5, pady=15)

        tk.Button(top, text="🌉 Find Bridges", command=self._find_bridges,
                  bg=self.colors["highlight"], fg=self.colors["text_bright"],
                  font=("Consolas", 11, "bold"), relief=tk.FLAT, padx=15,
                  cursor="hand2").pack(side=tk.LEFT, padx=20, pady=15)

        self.bridge_output = tk.Text(self.tab_bridge, bg=self.colors["panel"],
                                      fg=self.colors["text"], font=("Consolas", 10),
                                      relief=tk.FLAT, wrap=tk.WORD, padx=20, pady=15)
        self.bridge_output.pack(fill=tk.BOTH, expand=True)
        self.bridge_output.tag_config("title", foreground=self.colors["highlight"],
                                       font=("Consolas", 14, "bold"))
        self.bridge_output.tag_config("section", foreground=self.colors["warning"],
                                       font=("Consolas", 11, "bold"))
        self.bridge_output.tag_config("compound", foreground="#2196F3")
        self.bridge_output.tag_config("bridge", foreground="#4CAF50",
                                       font=("Consolas", 11, "bold"))
        self.bridge_output.config(state=tk.DISABLED)

        self.bridge_output.config(state=tk.NORMAL)
        self.bridge_output.insert(tk.END, "\n\n")
        self.bridge_output.insert(tk.END, "  🌉  Bridge Finder\n\n", "title")
        self.bridge_output.insert(tk.END, "  Pick two ingredients that seem incompatible.\n")
        self.bridge_output.insert(tk.END, "  FlavorForge will find a third ingredient that\n")
        self.bridge_output.insert(tk.END, "  shares compounds with BOTH — bridging the gap.\n")
        self.bridge_output.config(state=tk.DISABLED)

    def _find_bridges(self):
        a = self.bridge_a_var.get()
        b = self.bridge_b_var.get()
        if a == b:
            messagebox.showinfo("Same ingredient", "Pick two different ingredients!")
            return

        bridges = self.engine.find_bridge(a, b)
        direct_score, direct_shared = self.engine.weighted_similarity(a, b)

        self.bridge_output.config(state=tk.NORMAL)
        self.bridge_output.delete("1.0", tk.END)

        a_name = INGREDIENTS[a].name
        b_name = INGREDIENTS[b].name

        self.bridge_output.insert(tk.END, f"\n  {a_name} ↔ {b_name}\n\n", "title")
        self.bridge_output.insert(tk.END, "  DIRECT CONNECTION\n", "section")
        if direct_shared:
            shared_names = [COMPOUNDS[c].name for c in direct_shared if c in COMPOUNDS]
            self.bridge_output.insert(tk.END, f"    Similarity: {direct_score:.2f}\n")
            self.bridge_output.insert(tk.END, f"    Shared: ")
            self.bridge_output.insert(tk.END, f"{', '.join(shared_names)}\n\n", "compound")
        else:
            self.bridge_output.insert(tk.END, "    No shared compounds! These need a bridge.\n\n")

        self.bridge_output.insert(tk.END, "  BRIDGE INGREDIENTS\n", "section")
        if bridges:
            for i, br in enumerate(bridges):
                br_name = INGREDIENTS[br["ingredient"]].name
                self.bridge_output.insert(tk.END, f"\n    #{i+1}  ", "bridge")
                self.bridge_output.insert(tk.END, f"{br_name}", "bridge")
                self.bridge_output.insert(tk.END, f"  [{br['category']}]  score: {br['score']:.2f}\n")
                conn_a = [COMPOUNDS[c].name for c in br["connects_to_a"] if c in COMPOUNDS]
                conn_b = [COMPOUNDS[c].name for c in br["connects_to_b"] if c in COMPOUNDS]
                self.bridge_output.insert(tk.END, f"      → {a_name}: ")
                self.bridge_output.insert(tk.END, f"{', '.join(conn_a)}\n", "compound")
                self.bridge_output.insert(tk.END, f"      → {b_name}: ")
                self.bridge_output.insert(tk.END, f"{', '.join(conn_b)}\n", "compound")
        else:
            self.bridge_output.insert(tk.END, "    No bridges found!\n")
        self.bridge_output.config(state=tk.DISABLED)

    # ─── PANTRY PERSISTENCE ────────────────────────────────────

    def _pantry_path(self):
        return os.path.join(os.path.expanduser("~"), ".flavorforge_pantry.json")

    def _load_pantry(self):
        self.pantry = set()
        try:
            with open(self._pantry_path(), "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return
        if isinstance(data, dict):
            self.pantry = {n for n in data.get("pantry", []) if isinstance(n, str)}

    def _save_pantry(self) -> bool:
        return _write_json_atomic(self._pantry_path(), {"pantry": sorted(self.pantry)})

    # ─── MY PANTRY TAB ─────────────────────────────────────────

    def build_pantry_tab(self):
        # ── Left panel: ingredient selector ──
        left = tk.Frame(self.tab_pantry, bg=self.colors["panel"], width=320)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left.pack_propagate(False)

        tk.Label(left, text="What's In Your Kitchen?", font=("Consolas", 12, "bold"),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(pady=(10, 5))

        # Search
        search_frame = tk.Frame(left, bg=self.colors["panel"])
        search_frame.pack(fill=tk.X, padx=10)
        tk.Label(search_frame, text="Search:", bg=self.colors["panel"],
                 fg=self.colors["text_dim"], font=("Consolas", 9)).pack(side=tk.LEFT)
        self.pantry_search_var = tk.StringVar()
        self.pantry_search_var.trace_add("write", self._filter_pantry_list)
        tk.Entry(search_frame, textvariable=self.pantry_search_var,
                 bg=self.colors["accent"], fg=self.colors["text"],
                 insertbackground=self.colors["text"],
                 font=("Consolas", 10), relief=tk.FLAT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Category filter
        cat_frame = tk.Frame(left, bg=self.colors["panel"])
        cat_frame.pack(fill=tk.X, padx=10, pady=5)
        self.pantry_cat_var = tk.StringVar(value="All")
        cats = ["All"] + sorted(set(i.category for i in INGREDIENTS.values()))
        ttk.Combobox(cat_frame, textvariable=self.pantry_cat_var,
                     values=cats, state="readonly", width=20).pack(fill=tk.X)
        self.pantry_cat_var.trace_add("write", lambda *a: self._filter_pantry_list())

        # Quick-add buttons
        quick_frame = tk.Frame(left, bg=self.colors["panel"])
        quick_frame.pack(fill=tk.X, padx=10, pady=3)
        tk.Button(quick_frame, text="+ Common Staples", command=self._add_staples,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 8), relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        tk.Button(quick_frame, text="Clear All", command=self._clear_pantry,
                  bg="#5c1a1a", fg=self.colors["text"],
                  font=("Consolas", 8), relief=tk.FLAT).pack(side=tk.RIGHT, padx=2)

        # Ingredient checkboxes (in a scrollable frame)
        list_frame = tk.Frame(left, bg=self.colors["accent"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(list_frame, bg=self.colors["accent"], highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.pantry_inner = tk.Frame(canvas, bg=self.colors["accent"])

        self.pantry_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.pantry_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")

        self.pantry_vars = {}  # ingredient_name -> BooleanVar
        self._populate_pantry_checkboxes()

        # Pantry count
        self.pantry_count_label = tk.Label(left, text="",
                                            font=("Consolas", 10, "bold"),
                                            bg=self.colors["panel"],
                                            fg=self.colors["highlight"])
        self.pantry_count_label.pack(pady=(5, 10))
        self._update_pantry_count()

        # ── Right panel: recipes ──
        right = tk.Frame(self.tab_pantry, bg=self.colors["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Controls
        controls = tk.Frame(right, bg=self.colors["panel"], height=55)
        controls.pack(fill=tk.X, pady=(0, 5))
        controls.pack_propagate(False)

        tk.Button(controls, text="🍳 What Can I Make?", command=self._pantry_search_recipes,
                  bg=self.colors["highlight"], fg=self.colors["text_bright"],
                  font=("Consolas", 12, "bold"), relief=tk.FLAT, padx=15,
                  cursor="hand2").pack(side=tk.LEFT, padx=10, pady=10)

        tk.Label(controls, text="Style:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(15, 5))

        self.pantry_type_var = tk.StringVar(value="Any")
        ttk.Combobox(controls, textvariable=self.pantry_type_var,
                     values=DISH_TYPES, state="readonly", width=18).pack(side=tk.LEFT, padx=5, pady=10)

        tk.Button(controls, text="🛒 Almost There", command=self._pantry_almost_there,
                  bg="#1a5276", fg=self.colors["text"],
                  font=("Consolas", 10, "bold"), relief=tk.FLAT, padx=12,
                  cursor="hand2").pack(side=tk.LEFT, padx=15, pady=10)

        tk.Button(controls, text="🤖 → AI Chef", command=self._pantry_send_to_ai,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 10), relief=tk.FLAT, padx=10,
                  cursor="hand2").pack(side=tk.LEFT, padx=5, pady=10)

        # Results
        self.pantry_output = tk.Text(right, bg=self.colors["panel"], fg=self.colors["text"],
                                      font=("Consolas", 10), relief=tk.FLAT, wrap=tk.WORD,
                                      padx=20, pady=15)
        self.pantry_output.pack(fill=tk.BOTH, expand=True)
        self.pantry_output.tag_config("title", foreground=self.colors["highlight"],
                                       font=("Consolas", 14, "bold"))
        self.pantry_output.tag_config("recipe_name", foreground=self.colors["highlight"],
                                       font=("Consolas", 12, "bold"))
        self.pantry_output.tag_config("section", foreground=self.colors["warning"],
                                       font=("Consolas", 11, "bold"))
        self.pantry_output.tag_config("compound", foreground="#2196F3")
        self.pantry_output.tag_config("score_high", foreground="#4CAF50",
                                       font=("Consolas", 10, "bold"))
        self.pantry_output.tag_config("score_med", foreground="#FF9800")
        self.pantry_output.tag_config("missing", foreground="#e74c3c",
                                       font=("Consolas", 10, "bold"))
        self.pantry_output.tag_config("dish_type", foreground="#9C27B0",
                                       font=("Consolas", 9))
        self.pantry_output.tag_config("technique", foreground="#bbb",
                                       font=("Consolas", 10))
        self.pantry_output.tag_config("dim", foreground="#666")
        self.pantry_output.config(state=tk.DISABLED)

        self._show_pantry_welcome()

    def _populate_pantry_checkboxes(self, filter_text="", filter_cat="All"):
        for widget in self.pantry_inner.winfo_children():
            widget.destroy()

        for name in sorted(INGREDIENTS.keys()):
            ing = INGREDIENTS[name]
            if filter_cat != "All" and ing.category != filter_cat:
                continue
            if filter_text and filter_text.lower() not in name.lower() and filter_text.lower() not in ing.name.lower() and filter_text.lower() not in ing.flavor_notes.lower():
                continue

            if name not in self.pantry_vars:
                var = tk.BooleanVar(value=(name in self.pantry))
                self.pantry_vars[name] = var
            else:
                var = self.pantry_vars[name]

            color = CATEGORIES.get(ing.category, "#555")
            cb = tk.Checkbutton(self.pantry_inner,
                                text=f" {ing.name} — {ing.flavor_notes}  [{ing.category}]",
                                variable=var,
                                command=lambda n=name: self._toggle_pantry(n),
                                bg=self.colors["accent"],
                                fg=self.colors["text"],
                                selectcolor=self.colors["panel"],
                                activebackground=self.colors["accent"],
                                activeforeground=self.colors["text"],
                                font=("Consolas", 9),
                                anchor="w")
            cb.pack(fill=tk.X, padx=5, pady=1)

    def _filter_pantry_list(self, *args):
        self._populate_pantry_checkboxes(
            self.pantry_search_var.get(),
            self.pantry_cat_var.get()
        )

    def _toggle_pantry(self, name):
        if self.pantry_vars[name].get():
            self.pantry.add(name)
        else:
            self.pantry.discard(name)
        self._update_pantry_count()
        self._save_pantry()

    def _update_pantry_count(self):
        n = len(self.pantry)
        cats = set(INGREDIENTS[n].category for n in self.pantry if n in INGREDIENTS)
        self.pantry_count_label.config(
            text=f"🧊 {n} ingredients across {len(cats)} categories")

    def _add_staples(self):
        staples = {
            "olive_oil", "butter", "garlic", "onion", "salt", "black_pepper",
            "egg", "lemon", "rice", "bread", "chicken", "tomato",
            "parmesan", "cream", "soy_sauce", "vinegar", "honey",
            "ginger", "cumin", "paprika", "oregano", "thyme",
            "garlic_powder", "onion_powder", "red_pepper_flakes",
            "chili_powder", "italian_seasoning", "flour", "white_sugar",
            "hot_sauce", "mayo", "ketchup", "sesame_seeds",
            "tomato_sauce", "marinara", "sour_cream", "mustard",
        }
        for s in staples:
            if s in INGREDIENTS:
                self.pantry.add(s)
                if s in self.pantry_vars:
                    self.pantry_vars[s].set(True)
        self._update_pantry_count()
        self._save_pantry()
        self._filter_pantry_list()

    def _clear_pantry(self):
        self.pantry.clear()
        for var in self.pantry_vars.values():
            var.set(False)
        self._update_pantry_count()
        self._save_pantry()

    def _show_pantry_welcome(self):
        self.pantry_output.config(state=tk.NORMAL)
        self.pantry_output.delete("1.0", tk.END)
        self.pantry_output.insert(tk.END, "\n")
        self.pantry_output.insert(tk.END, "  🧊  My Pantry\n\n", "title")
        self.pantry_output.insert(tk.END, "  Check off the ingredients you have on hand,\n")
        self.pantry_output.insert(tk.END, "  then hit 'What Can I Make?' to find recipes\n")
        self.pantry_output.insert(tk.END, "  using only what's in your kitchen.\n\n")
        self.pantry_output.insert(tk.END, "  🛒 'Almost There' shows recipes where you're\n")
        self.pantry_output.insert(tk.END, "  just ONE ingredient short — your shopping list.\n\n")
        self.pantry_output.insert(tk.END, "  Tip: Hit '+ Common Staples' for a quick start.\n")
        self.pantry_output.insert(tk.END, "  Your pantry saves between sessions.\n")
        self.pantry_output.config(state=tk.DISABLED)

    def _pantry_search_recipes(self):
        if len(self.pantry) < 2:
            messagebox.showinfo("Need Ingredients",
                "Check off at least 2-3 ingredients from your pantry first!")
            return

        dish_type = self.pantry_type_var.get()
        dt = dish_type if dish_type != "Any" else None

        self.pantry_output.config(state=tk.NORMAL)
        self.pantry_output.delete("1.0", tk.END)
        self.pantry_output.insert(tk.END, "\n  Searching...\n", "dim")
        self.pantry_output.config(state=tk.DISABLED)
        self.root.update_idletasks()

        recipes = self.engine.pantry_recipes(self.pantry, dish_type=dt, top_n=15)

        self.pantry_output.config(state=tk.NORMAL)
        self.pantry_output.delete("1.0", tk.END)

        pantry_display = ", ".join(sorted(INGREDIENTS[n].name for n in self.pantry if n in INGREDIENTS))
        self.pantry_output.insert(tk.END, f"\n  Your pantry: ", "section")
        self.pantry_output.insert(tk.END, f"{pantry_display}\n", "dim")

        if not recipes:
            self.pantry_output.insert(tk.END, "\n  No recipes found with your current pantry.\n")
            self.pantry_output.insert(tk.END, "  Try adding more ingredients or changing the dish style.\n")
            self.pantry_output.insert(tk.END, "  Hit '🛒 Almost There' to see what you're close to making!\n")
            self.pantry_output.config(state=tk.DISABLED)
            return

        self.pantry_output.insert(tk.END, f"\n  Found {len(recipes)} recipes from your pantry!\n\n", "title")

        self.pantry_recipes_list = recipes  # Store for AI send
        for i, recipe in enumerate(recipes):
            self.pantry_output.insert(tk.END, f"  #{i+1}  ", "recipe_name")
            self.pantry_output.insert(tk.END, f"{recipe['name']}\n", "recipe_name")
            self.pantry_output.insert(tk.END, f"      ", "dish_type")
            self.pantry_output.insert(tk.END, f"[{recipe['dish_type']}]  ", "dish_type")

            score = recipe["score"]
            tag = "score_high" if score > 0.4 else "score_med"
            bar = "█" * max(int(score * 15), 1)
            self.pantry_output.insert(tk.END, f"Flavor match: {bar} {score:.2f}\n", tag)

            # Show ingredients
            for slot, ing_name in recipe["ingredients"].items():
                if ing_name in INGREDIENTS:
                    display = INGREDIENTS[ing_name].name
                    self.pantry_output.insert(tk.END, f"      • {display} ({slot})\n")

            # Show technique
            self.pantry_output.insert(tk.END, f"      → {recipe['technique']}\n", "technique")

            # Show key molecular connections
            if recipe["connections"]:
                best = sorted(recipe["connections"],
                             key=lambda c: len(c["shared"]), reverse=True)[:2]
                for conn in best:
                    a, b = conn["pair"]
                    shared = [COMPOUNDS[c].name for c in conn["shared"] if c in COMPOUNDS][:3]
                    a_name = INGREDIENTS[a].name if a in INGREDIENTS else a
                    b_name = INGREDIENTS[b].name if b in INGREDIENTS else b
                    self.pantry_output.insert(tk.END, f"      ⚗ {a_name} + {b_name}: ")
                    self.pantry_output.insert(tk.END, f"{', '.join(shared)}\n", "compound")

            self.pantry_output.insert(tk.END, "\n")

        self.pantry_output.config(state=tk.DISABLED)

    def _pantry_almost_there(self):
        if len(self.pantry) < 1:
            messagebox.showinfo("Need Ingredients",
                "Check off at least a couple ingredients first!")
            return

        dish_type = self.pantry_type_var.get()
        dt = dish_type if dish_type != "Any" else None

        self.pantry_output.config(state=tk.NORMAL)
        self.pantry_output.delete("1.0", tk.END)
        self.pantry_output.insert(tk.END, "\n  Searching for near-matches...\n", "dim")
        self.pantry_output.config(state=tk.DISABLED)
        self.root.update_idletasks()

        almost = self.engine.almost_there(self.pantry, dish_type=dt, top_n=12)

        self.pantry_output.config(state=tk.NORMAL)
        self.pantry_output.delete("1.0", tk.END)

        if not almost:
            self.pantry_output.insert(tk.END, "\n  No near-matches found.\n")
            self.pantry_output.insert(tk.END, "  Try adding a few more pantry ingredients.\n")
            self.pantry_output.config(state=tk.DISABLED)
            return

        self.pantry_output.insert(tk.END, f"\n  🛒 You're ONE ingredient away from these recipes!\n\n", "title")

        self.pantry_recipes_list = almost
        for i, recipe in enumerate(almost):
            self.pantry_output.insert(tk.END, f"  #{i+1}  ", "recipe_name")
            self.pantry_output.insert(tk.END, f"{recipe['name']}\n", "recipe_name")
            self.pantry_output.insert(tk.END, f"      [{recipe['dish_type']}]\n", "dish_type")

            # Show what's missing
            self.pantry_output.insert(tk.END, f"      🛒 You need: ")
            self.pantry_output.insert(tk.END,
                f"{recipe['missing_display']} ({recipe['missing_slot']})\n", "missing")

            # Show ingredients you DO have
            have_names = [INGREDIENTS[n].name for s, n in recipe["ingredients"].items()
                         if n != recipe["missing_ingredient"] and n in INGREDIENTS]
            self.pantry_output.insert(tk.END, f"      ✓ You have: {', '.join(have_names)}\n")

            self.pantry_output.insert(tk.END, f"      → {recipe['technique']}\n", "technique")
            self.pantry_output.insert(tk.END, "\n")

        self.pantry_output.config(state=tk.DISABLED)

    def _pantry_send_to_ai(self):
        """Send the first pantry recipe to AI Chef."""
        if not hasattr(self, 'pantry_recipes_list') or not self.pantry_recipes_list:
            messagebox.showinfo("No Recipes", "Search for pantry recipes first!")
            return
        recipe = self.pantry_recipes_list[0]
        self.current_recipe = recipe
        notebook = self.tab_ai.master
        notebook.select(self.tab_ai)
        self._ai_generate_from_recipe(recipe)

    # ─── AI CHEF TAB ───────────────────────────────────────────

    def build_ai_tab(self):
        # Settings bar
        settings = tk.Frame(self.tab_ai, bg=self.colors["panel"], height=50)
        settings.pack(fill=tk.X, pady=(0, 5))
        settings.pack_propagate(False)

        tk.Label(settings, text="Provider:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5), pady=10)

        self.ai_provider_var = tk.StringVar(value=self.ai_chef.provider)
        prov_menu = ttk.Combobox(settings, textvariable=self.ai_provider_var,
                                  values=["ollama", "anthropic"], state="readonly", width=10)
        prov_menu.pack(side=tk.LEFT, padx=5, pady=10)
        prov_menu.bind("<<ComboboxSelected>>", self._on_provider_change)

        tk.Label(settings, text="URL/Model:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(15, 5))

        self.ai_url_var = tk.StringVar(value=self.ai_chef.ollama_url)
        self.ai_url_entry = tk.Entry(settings, textvariable=self.ai_url_var,
                                      bg=self.colors["accent"], fg=self.colors["text"],
                                      insertbackground=self.colors["text"],
                                      font=("Consolas", 9), relief=tk.FLAT, width=30)
        self.ai_url_entry.pack(side=tk.LEFT, padx=5, pady=10)

        tk.Label(settings, text="Model:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5))

        # A Combobox rather than a plain Entry so the Claude side can offer the
        # current models by name. Ollama keeps free text — its model names are
        # whatever the user has pulled locally, so a fixed list would be wrong.
        # The v3.0 default was pinned in source and went three model
        # generations stale with nothing to catch it; a dropdown means the
        # choice does not require editing the file.
        self.ai_model_var = tk.StringVar(value=self.ai_chef.ollama_model)
        self.ai_model_entry = ttk.Combobox(settings, textvariable=self.ai_model_var,
                                           font=("Consolas", 9), width=22)
        self.ai_model_entry.pack(side=tk.LEFT, padx=5, pady=10)
        self.ai_model_hint = tk.Label(settings, text="", font=("Consolas", 8),
                                      bg=self.colors["panel"], fg=self.colors["text_dim"])
        self.ai_model_hint.pack(side=tk.LEFT, padx=(2, 0))
        self.ai_model_entry.bind("<<ComboboxSelected>>", self._update_model_hint)

        tk.Button(settings, text="Test", command=self._test_ai_connection,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 9), relief=tk.FLAT).pack(side=tk.LEFT, padx=5, pady=10)

        tk.Button(settings, text="Save", command=self._save_ai_settings,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 9), relief=tk.FLAT).pack(side=tk.LEFT, padx=5, pady=10)

        self.ai_status = tk.Label(settings, text="", font=("Consolas", 9),
                                   bg=self.colors["panel"], fg=self.colors["text_dim"])
        self.ai_status.pack(side=tk.RIGHT, padx=10)

        # API key row (for Anthropic)
        self.api_key_frame = tk.Frame(self.tab_ai, bg=self.colors["panel"], height=35)
        self.api_key_frame.pack(fill=tk.X, pady=(0, 5))
        self.api_key_frame.pack_propagate(False)

        tk.Label(self.api_key_frame, text="API Key:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(10, 5))

        self.ai_key_var = tk.StringVar(value=self.ai_chef.anthropic_key)
        self.ai_key_entry = tk.Entry(self.api_key_frame, textvariable=self.ai_key_var,
                                      bg=self.colors["accent"], fg=self.colors["text"],
                                      insertbackground=self.colors["text"],
                                      font=("Consolas", 9), relief=tk.FLAT, width=50, show="•")
        self.ai_key_entry.pack(side=tk.LEFT, padx=5)

        self.show_key_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.api_key_frame, text="Show", variable=self.show_key_var,
                       command=self._toggle_key_visibility,
                       bg=self.colors["panel"], fg=self.colors["text"],
                       selectcolor=self.colors["accent"],
                       font=("Consolas", 9)).pack(side=tk.LEFT, padx=5)

        # Toggle API key visibility based on provider
        self._on_provider_change()

        # Action buttons
        action_bar = tk.Frame(self.tab_ai, bg=self.colors["panel"], height=50)
        action_bar.pack(fill=tk.X, pady=(0, 5))
        action_bar.pack_propagate(False)

        tk.Button(action_bar, text="⚗ Generate Recipe + Ask AI Chef",
                  command=self._ai_generate_new,
                  bg=self.colors["highlight"], fg=self.colors["text_bright"],
                  font=("Consolas", 11, "bold"), relief=tk.FLAT, padx=15,
                  cursor="hand2").pack(side=tk.LEFT, padx=10, pady=10)

        tk.Label(action_bar, text="Seed:", font=("Consolas", 10),
                 bg=self.colors["panel"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(20, 5))

        self.ai_seed_var = tk.StringVar(value="(random)")
        ai_seed_menu = ttk.Combobox(action_bar, textvariable=self.ai_seed_var,
                                     values=["(random)"] + sorted(INGREDIENTS.keys()),
                                     state="readonly", width=18)
        ai_seed_menu.pack(side=tk.LEFT, padx=5, pady=10)

        self.ai_spinner = tk.Label(action_bar, text="", font=("Consolas", 11),
                                    bg=self.colors["panel"], fg=self.colors["highlight"])
        self.ai_spinner.pack(side=tk.LEFT, padx=15)

        tk.Button(action_bar, text="💾 Save AI Recipe", command=self._save_ai_recipe,
                  bg=self.colors["accent"], fg=self.colors["text"],
                  font=("Consolas", 10), relief=tk.FLAT, padx=10,
                  cursor="hand2").pack(side=tk.RIGHT, padx=10, pady=10)

        self.ai_save_status = tk.Label(action_bar, text="", font=("Consolas", 9),
                                        bg=self.colors["panel"], fg=self.colors["success"])
        self.ai_save_status.pack(side=tk.RIGHT, padx=5)

        # Track the AI response text
        self.ai_response_text = ""
        self.ai_recipe_name = ""

        # Output
        self.ai_output = tk.Text(self.tab_ai, bg="#0d1117", fg=self.colors["text"],
                                  font=("Consolas", 11), relief=tk.FLAT, wrap=tk.WORD,
                                  padx=20, pady=15)
        self.ai_output.pack(fill=tk.BOTH, expand=True)
        self.ai_output.tag_config("header", foreground=self.colors["highlight"],
                                   font=("Consolas", 14, "bold"))
        self.ai_output.tag_config("status", foreground=self.colors["warning"],
                                   font=("Consolas", 10, "italic"))
        self.ai_output.tag_config("error", foreground="#e74c3c", font=("Consolas", 11))
        self.ai_output.config(state=tk.DISABLED)

        self._show_ai_welcome()

    def _show_ai_welcome(self):
        self.ai_output.config(state=tk.NORMAL)
        self.ai_output.delete("1.0", tk.END)
        self.ai_output.insert(tk.END, "\n")
        self.ai_output.insert(tk.END, "  🤖  AI Chef\n\n", "header")
        self.ai_output.insert(tk.END, "  FlavorForge generates a molecular pairing concept,\n")
        self.ai_output.insert(tk.END, "  then sends it to your AI (Ollama or Claude API)\n")
        self.ai_output.insert(tk.END, "  for a full recipe with quantities and instructions.\n\n")
        self.ai_output.insert(tk.END, f"  Current provider: {self.ai_chef.provider}\n")
        if self.ai_chef.provider == "ollama":
            self.ai_output.insert(tk.END, f"  Ollama URL: {self.ai_chef.ollama_url}\n")
            self.ai_output.insert(tk.END, f"  Model: {self.ai_chef.ollama_model}\n")
        else:
            self.ai_output.insert(tk.END, f"  Model: {self.ai_chef.anthropic_model}\n")
            key_status = "Set" if self.ai_chef.anthropic_key else "Not set"
            self.ai_output.insert(tk.END, f"  API Key: {key_status}\n")
        self.ai_output.insert(tk.END, "\n  Generate a recipe on the Recipe tab then hit '🤖 Send to AI Chef',\n")
        self.ai_output.insert(tk.END, "  or use the button above to do both in one step.\n")
        self.ai_output.config(state=tk.DISABLED)

    def _on_provider_change(self, event=None):
        provider = self.ai_provider_var.get()
        if provider == "ollama":
            self.ai_url_var.set(self.ai_chef.ollama_url)
            self.ai_model_var.set(self.ai_chef.ollama_model)
            # Free text: the available models are whatever has been pulled.
            self.ai_model_entry.config(values=(), state="normal")
            self.ai_model_hint.config(text="")
            self.api_key_frame.pack_forget()
        else:
            self.ai_url_var.set("https://api.anthropic.com")
            self.ai_model_entry.config(values=[m[1] for m in CLAUDE_MODELS],
                                       state="readonly")
            self.ai_model_var.set(self.ai_chef.anthropic_model)
            self._update_model_hint()
            self.api_key_frame.pack(fill=tk.X, pady=(0, 5), after=self.api_key_frame.master.winfo_children()[0])

    def _update_model_hint(self, event=None):
        note = next((m[2] for m in CLAUDE_MODELS if m[1] == self.ai_model_var.get()), "")
        retired = getattr(self.ai_chef, "retired_model", "")
        if retired:
            note = f"{retired} was retired — switched to this one"
        self.ai_model_hint.config(text=f"  {note}" if note else "")

    def _toggle_key_visibility(self):
        self.ai_key_entry.config(show="" if self.show_key_var.get() else "•")

    def _save_ai_settings(self):
        self.ai_chef.provider = self.ai_provider_var.get()
        if self.ai_chef.provider == "ollama":
            self.ai_chef.ollama_url = self.ai_url_var.get()
            self.ai_chef.ollama_model = self.ai_model_var.get()
        else:
            self.ai_chef.anthropic_key = self.ai_key_var.get()
            self.ai_chef.anthropic_model = self.ai_model_var.get()
        self.ai_chef.save_config()
        self.ai_status.config(text="Settings saved!", fg=self.colors["success"])
        self.root.after(3000, lambda: self.ai_status.config(text=""))

    def _test_ai_connection(self):
        self._save_ai_settings()
        ok, msg = self.ai_chef.test_connection()
        color = self.colors["success"] if ok else "#e74c3c"
        self.ai_status.config(text=msg, fg=color)

    def _ai_generate_new(self):
        """Generate a recipe concept and immediately send to AI."""
        seed = self.ai_seed_var.get()
        if seed == "(random)" or not seed:
            seed = None
        recipe = self.engine.generate_recipe(seed_ingredient=seed)
        self.current_recipe = recipe
        self._ai_generate_from_recipe(recipe)

    def _ai_generate_from_recipe(self, recipe):
        """Send a recipe concept to the AI for detailed generation."""
        if "error" in recipe:
            return

        self._save_ai_settings()
        prompt = self.engine.recipe_to_ai_prompt(recipe)

        # Reset tracking
        self.ai_response_text = ""
        self.ai_recipe_name = recipe.get("name", "Untitled Recipe")

        self.ai_output.config(state=tk.NORMAL)
        self.ai_output.delete("1.0", tk.END)
        self.ai_output.insert(tk.END, f"\n  Concept: {recipe['name']}\n\n", "header")
        self.ai_output.insert(tk.END, f"  Sending to {self.ai_chef.provider}...\n\n", "status")
        self.ai_output.config(state=tk.DISABLED)

        self.ai_spinner.config(text="⏳ Generating...")
        self.ai_save_status.config(text="")

        def on_chunk(text):
            if text is None:
                self.root.after(0, lambda: self.ai_spinner.config(text="✅ Done — hit Save to keep"))
                return
            self.root.after(0, lambda t=text: self._append_ai_text(t))

        def on_error(msg):
            self.root.after(0, lambda m=msg: self._show_ai_error(m))

        self.ai_chef.generate(prompt, callback=on_chunk, error_callback=on_error)

    def _append_ai_text(self, text):
        self.ai_response_text += text  # Track full response
        self.ai_output.config(state=tk.NORMAL)
        self.ai_output.insert(tk.END, text)
        self.ai_output.see(tk.END)
        self.ai_output.config(state=tk.DISABLED)

    def _show_ai_error(self, msg):
        self.ai_spinner.config(text="❌ Error")
        self.ai_output.config(state=tk.NORMAL)
        self.ai_output.insert(tk.END, f"\n\n  ERROR: {msg}\n", "error")
        self.ai_output.config(state=tk.DISABLED)

    def _save_ai_recipe(self):
        """Save the AI-generated recipe to a file."""
        if not self.ai_response_text:
            messagebox.showinfo("Nothing to Save", "Generate an AI recipe first!")
            return

        import datetime

        # Save to dedicated recipes folder
        recipes_dir = os.path.join(os.path.expanduser("~"), "FlavorForge_Recipes")
        os.makedirs(recipes_dir, exist_ok=True)

        # Clean filename from recipe name
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in self.ai_recipe_name)
        safe_name = safe_name.strip()[:60] or "recipe"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.txt"
        filepath = os.path.join(recipes_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"FlavorForge AI Recipe\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write(f"Concept: {self.ai_recipe_name}\n")
                f.write(f"{'=' * 60}\n\n")
                f.write(self.ai_response_text)

            self.ai_save_status.config(text=f"Saved to ~/FlavorForge_Recipes/", fg=self.colors["success"])
            self.root.after(5000, lambda: self.ai_save_status.config(text=""))

            # Also save to the recipes JSON for the dropdown
            if self.current_recipe:
                saved = self._load_all_saved()
                import copy
                recipe_data = {}
                for k, v in self.current_recipe.items():
                    if k == "connections":
                        recipe_data[k] = [{"pair": list(c["pair"]), "shared": list(c["shared"])} for c in v]
                    elif k == "ingredients":
                        recipe_data[k] = dict(v)
                    else:
                        recipe_data[k] = v
                recipe_data["saved_at"] = datetime.datetime.now().isoformat()
                recipe_data["ai_recipe_file"] = filepath
                recipe_data["ai_response"] = self.ai_response_text[:500] + "..." if len(self.ai_response_text) > 500 else self.ai_response_text

                # Check for duplicates
                existing = [r.get("name") for r in saved]
                if recipe_data.get("name") not in existing:
                    saved.insert(0, recipe_data)
                    self._save_all(saved)
                    self._refresh_saved_list()

        except Exception as e:
            self.ai_save_status.config(text=f"Error: {e}", fg="#e74c3c")

    # ─── RUN ────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════════════════════════
# COMMAND LINE
# The engine is the interesting half of this program and it was reachable
# only through 2,000 lines of Tk. This makes it scriptable, usable over
# SSH, and — with the guarded tkinter import at the top — usable on a box
# with no GUI toolkit installed at all.
# ═══════════════════════════════════════════════════════════════════

def _resolve(name: str) -> Optional[str]:
    """Accept a key, a display name, or an unambiguous prefix."""
    raw = name.strip().lower()
    key = raw.replace(" ", "_").replace("-", "_")
    if key in INGREDIENTS:
        return key
    for k, ing in INGREDIENTS.items():
        if ing.name.lower() == raw:
            return k
    hits = [k for k in INGREDIENTS if k.startswith(key)]
    return hits[0] if len(hits) == 1 else None


def _die_unknown(name: str) -> int:
    print("No ingredient matching %r." % name, file=sys.stderr)
    stem = name.strip().lower()[:4]
    near = sorted(k for k in INGREDIENTS if stem and stem in k)[:8]
    if near:
        print("Close: " + ", ".join(near), file=sys.stderr)
    print("Use --list to see everything.", file=sys.stderr)
    return 2


def _fmt_compounds(engine, shared, limit: int = 4) -> str:
    """Name the distinctive shared compounds, skipping the near-universal
    ones — the same rule the Recipe tab applies when it explains a pairing."""
    interesting = sorted(shared - engine._boring_compounds,
                         key=lambda c: -engine._weight.get(c, 0))
    names = [COMPOUNDS[c].name for c in interesting[:limit] if c in COMPOUNDS]
    return ", ".join(names) if names else "background notes only"


def run_cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="flavorforge",
        description="Molecular flavor pairing from the command line. "
                    "With no arguments, starts the GUI.")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--pair", metavar="INGREDIENT",
                   help="top molecular pairings for an ingredient")
    g.add_argument("--substitute", metavar="INGREDIENT",
                   help="what to use when you have none")
    g.add_argument("--bridge", nargs=2, metavar=("A", "B"),
                   help="find ingredients connecting two others")
    g.add_argument("--compound", metavar="NAME",
                   help="everything carrying an aroma compound, or search for one")
    g.add_argument("--recipe", action="store_true", help="generate a recipe concept")
    g.add_argument("--list", action="store_true", help="list every ingredient")
    parser.add_argument("--seed", metavar="INGREDIENT",
                        help="with --recipe: build the dish around this")
    parser.add_argument("--dish-type", metavar="TYPE",
                        help="with --recipe: e.g. 'Soup', 'Pizza & Flatbread'")
    parser.add_argument("--category", metavar="CAT",
                        help="with --list: filter to one category")
    parser.add_argument("-n", type=int, default=15, metavar="N",
                        help="how many results (default 15)")
    parser.add_argument("--version", action="version",
                        version="FlavorForge " + __version__)
    args = parser.parse_args(argv)

    engine = FlavorEngine()

    if args.list:
        names = sorted(INGREDIENTS)
        if args.category:
            names = [n for n in names if INGREDIENTS[n].category == args.category]
            if not names:
                print("No category %r. Known: %s"
                      % (args.category, ", ".join(sorted(CATEGORIES))), file=sys.stderr)
                return 2
        for n in names:
            i = INGREDIENTS[n]
            print("%-24s %-10s %s" % (n, i.category, i.flavor_notes))
        print("\n%d ingredients" % len(names), file=sys.stderr)
        return 0

    if args.compound:
        exact = engine.ingredients_with_compound(args.compound)
        if exact:
            c = COMPOUNDS[args.compound]
            pct = 100.0 * len(exact) / len(INGREDIENTS)
            print("%s  [%s]  %s" % (c.name, c.category, c.description))
            print("in %d of %d ingredients (%.1f%%)\n" % (len(exact), len(INGREDIENTS), pct))
            for n in exact:
                print("  %-24s %s" % (n, INGREDIENTS[n].category))
            return 0
        matches = engine.search_compounds(args.compound)
        if not matches:
            print("No compound matching %r." % args.compound, file=sys.stderr)
            return 2
        print("%d compound(s) matching %r:" % (len(matches), args.compound))
        for k in matches:
            c = COMPOUNDS[k]
            print("  %-22s %-26s %s  [%d ingredients]"
                  % (k, c.name, c.description, engine._compound_freq.get(k, 0)))
        return 0

    if args.pair or args.substitute:
        raw = args.pair or args.substitute
        key = _resolve(raw)
        if not key:
            return _die_unknown(raw)
        ing = INGREDIENTS[key]
        rows = (engine.get_pairings(key, args.n) if args.pair
                else engine.substitutes(key, args.n))
        print("%s  [%s]  %s" % (ing.name, ing.category, ing.flavor_notes))
        own = sorted(COMPOUNDS[c].name for c in ing.compounds if c in COMPOUNDS)
        print("compounds: %s\n" % (", ".join(own) or "none — pure taste, no aroma"))
        if not rows:
            print("Nothing in the database connects to it.")
            return 0
        print("  %-22s %6s  shared aroma" % ("ingredient", "score"))
        for r in rows:
            flag = "" if r.get("aroma_match", True) else "   (role match, not aroma)"
            print("  %-22s %6.3f  %s%s"
                  % (INGREDIENTS[r["ingredient"]].name, r["score"],
                     _fmt_compounds(engine, r["shared_compounds"]), flag))
        return 0

    if args.bridge:
        a = _resolve(args.bridge[0])
        if not a:
            return _die_unknown(args.bridge[0])
        b = _resolve(args.bridge[1])
        if not b:
            return _die_unknown(args.bridge[1])
        bridges = engine.find_bridge(a, b)
        print("Bridging %s and %s:\n" % (INGREDIENTS[a].name, INGREDIENTS[b].name))
        if not bridges:
            print("  Nothing connects them. That is a real answer, not an error —")
            print("  try --pair on each and look for an overlap yourself.")
            return 0
        for br in bridges:
            print("  %-22s %6.3f" % (INGREDIENTS[br["ingredient"]].name, br["score"]))
            print("    to %s: %s" % (INGREDIENTS[a].name,
                                     _fmt_compounds(engine, br["connects_to_a"])))
            print("    to %s: %s" % (INGREDIENTS[b].name,
                                     _fmt_compounds(engine, br["connects_to_b"])))
        return 0

    if args.recipe:
        seed = None
        if args.seed:
            seed = _resolve(args.seed)
            if not seed:
                return _die_unknown(args.seed)
        r = engine.generate_recipe(seed_ingredient=seed, dish_type=args.dish_type)
        if "error" in r:
            print(r["error"], file=sys.stderr)
            return 1
        print(r["name"])
        print("=" * len(r["name"]))
        print("%s   novelty %.0f%%\n" % (r["dish_type"], r["novelty"] * 100))
        for slot, name in r["ingredients"].items():
            print("  %-14s %-22s %s" % (slot, INGREDIENTS[name].name,
                                        INGREDIENTS[name].flavor_notes))
        print("\n%s\n" % r["technique"])
        interesting = [c for c in r["connections"]
                       if c["shared"] - engine._boring_compounds]
        if interesting:
            print("Why it works:")
            for c in interesting[:8]:
                x, y = c["pair"]
                print("  %s + %s: %s" % (INGREDIENTS[x].name, INGREDIENTS[y].name,
                                         _fmt_compounds(engine, c["shared"])))
        return 0

    # No sub-command: start the GUI, which is what double-clicking the file
    # has always done.
    if not HAVE_TK:
        parser.print_help()
        print("\ntkinter is not installed, so the GUI is unavailable.", file=sys.stderr)
        return 1
    FlavorForgeGUI().run()
    return 0


def main() -> None:
    """Entry point for the `flavorforge` console script and for `python -m`."""
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
