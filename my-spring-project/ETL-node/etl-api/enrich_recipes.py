"""
enrich_recipes.py
-----------------
Converts raw recipe JSON files into a RAG-ready JSONL file with rich metadata.

Usage:
    python enrich_recipes.py

Outputs:
    recipes_rag_enriched.jsonl  — one chunk per recipe, with text + metadata

Metadata fields per chunk:
    title                   str
    meal_type               str   (main_course | dessert | beverage | breakfast |
                                   soup_stew | salad | snack | bread_pastry |
                                   sauce_condiment | side_dish)
    cuisine                 str   (italian | mexican | asian | indian | french |
                                   mediterranean | american | greek | japanese |
                                   thai | chinese | spanish | german | british |
                                   latin_american | middle_eastern | other)
    cooking_method          list  (slow_cooker | baked | grilled | stovetop |
                                   no_cook | fried | steamed | pressure)
    main_protein            str | null
    diet_flags              list  (vegetarian | vegan | gluten_free |
                                   dairy_free | nut_free)
    ingredient_count        int
    estimated_cook_time_min int | null
    has_picture             bool
    parsed_ingredients      list[dict]  (name, quantity, unit, qty_per_100g)
    nutrition_total         dict  (calories, protein, fat, carbs, fiber,
                                   sugar, sodium, sodium_mg)
    nutrition_matched       int   — ingredients successfully looked up
    nutrition_total_ing     int   — total ingredients attempted
    nutrition_coverage      float — fraction matched (0.0–1.0)
"""

import json
import re
import os
import ijson

from parse_ingredients import parse_ingredients
from nutrition_calculator import calculate_recipe_nutrition

# ── Config ─────────────────────────────────────────────────────────────────────

# INPUT_FILES = [
#     "/content/recipes_raw_nosource_ar.json",
#     "/content/recipes_raw_nosource_epi.json",
#     "/content/recipes_raw_nosource_fn.json",
# ]
# OUTPUT_PATH = "recipes_rag_enriched.jsonl"


# ── Utilities ──────────────────────────────────────────────────────────────────

def safe_str(value, default=""):
    """Return a stripped string for any input, including None."""
    if value is None:
        return default
    return str(value).strip()


def clean_ingredients(ingredients):
    """Strip ADVERTISEMENT noise and return clean ingredient strings."""
    if not ingredients:
        return []
    return [
        re.sub(r"\s*ADVERTISEMENT\s*", "", i).strip()
        for i in ingredients
        if isinstance(i, str) and i.strip() not in ("", "ADVERTISEMENT")
    ]


# ── Cooking methods ────────────────────────────────────────────────────────────

COOKING_METHODS = {
    "slow_cooker": ["slow cooker", "crockpot", "crock pot", "crock-pot"],
    "baked":       ["preheat oven", "bake ", "baked ", "roast"],
    "grilled":     ["grill", "grilled", "bbq", "barbecue"],
    "stovetop":    ["skillet", "saucepan", "stir-fry", "sauté", "saute", "pan-fry"],
    "no_cook":     ["no-bake", "no bake", "refrigerate until", "chill until"],
    "fried":       ["deep fry", "deep-fry", "fry in oil"],
    "steamed":     ["steam ", "steamer", "double boiler"],
    "pressure":    ["pressure cooker", "instant pot"],
}

PROTEINS = [
    "chicken", "beef", "pork", "salmon", "shrimp", "turkey", "lamb",
    "tofu", "tuna", "crab", "sausage", "bacon", "duck", "veal",
    "lobster", "scallop", "octopus", "squid",
]


# ── Meal type ──────────────────────────────────────────────────────────────────

_BEVERAGE_TITLE = [
    "cocktail", "smoothie", "lemonade", "punch", "eggnog", "milkshake",
    "hot chocolate", "mocktail", "sangria", "margarita", "martini", "mojito",
    "prosecco", "batida", "agua fresca", "spritzer", "aperitif", "mimosa",
    "bellini", "daiquiri", "negroni", "old fashioned", "whiskey sour",
]
_BEVERAGE_COMBINED = [
    "simple syrup", "shaken over ice", "stir in a cocktail",
    "pour into a glass", "garnish with a slice of lime",
]

MEAL_TYPE_RULES = [
    ("beverage",        _BEVERAGE_TITLE, _BEVERAGE_COMBINED),
    ("dessert",         ["cake", "cookie", "brownie", "pie ", "tart ", "pudding",
                         "custard", "ice cream", "sorbet", "gelato", "cheesecake",
                         "fudge", "truffle", "meringue", "mousse", "cobbler",
                         "crisp ", "crumble", "biscotti", "churro", "donut",
                         "doughnut", "macaron", "candy", "blondie", "shortbread",
                         "ganache", "tiramisu", "baklava", "mochi"], []),
    ("breakfast",       ["pancake", "waffle", "french toast", "omelette", "omelet",
                         "frittata", "quiche", "granola", "muffin", "scone",
                         "breakfast", "brunch", "hash brown", "crepe"], []),
    ("soup_stew",       ["soup", "stew", "chili", "chowder", "bisque", "broth",
                         "gazpacho", "minestrone", "bouillabaisse", "gumbo",
                         "posole", "consommé", "consomme"], []),
    ("salad",           ["salad", "slaw", "coleslaw", "tabbouleh", "fattoush"], []),
    ("snack",           ["dip ", "salsa", "hummus", "guacamole", "crostini",
                         "bruschetta", "cracker", "popcorn", "nacho",
                         "spring roll", "egg roll", "slider", "deviled egg",
                         "stuffed mushroom", "wonton"], []),
    ("bread_pastry",    ["bread loaf", "baguette", "focaccia", "brioche",
                         "croissant", "flatbread", "naan", "pita",
                         "pizza dough", "pumpernickel"], []),
    ("sauce_condiment", ["sauce", "gravy", "glaze", "marinade", "dressing",
                         "vinaigrette", "relish", "chutney", "jam ", "jelly",
                         "preserve", "compote", "pesto", "aioli", "mayonnaise",
                         "ketchup", "mustard", "syrup", "coulis"], []),
    ("side_dish",       ["side dish", "pilaf", "risotto", "polenta", "stuffing",
                         "couscous", "casserole", "gratin"], []),
    ("main_course",     [], []),
]


def detect_meal_type(title: str, combined: str, clean_ings: list) -> str:
    title_l    = title.lower()
    combined_l = combined.lower()
    for meal_type, title_kws, combined_kws in MEAL_TYPE_RULES:
        if any(kw in title_l for kw in title_kws):
            return meal_type
        if any(kw in combined_l for kw in combined_kws):
            return meal_type
    return "main_course"


# ── Cuisine ────────────────────────────────────────────────────────────────────

CUISINE_RULES = [
    ("italian",         ["pasta", "risotto", "pizza", "gnocchi", "polenta",
                         "tiramisu", "parmesan", "mozzarella", "prosciutto",
                         "pancetta", "amatriciana", "carbonara", "bolognese",
                         "osso buco", "bruschetta", "focaccia", "cannoli",
                         "panzanella", "arancini", "minestrone"]),
    ("mexican",         ["taco", "burrito", "enchilada", "quesadilla", "tamale",
                         "guacamole", "jalapeño", "chipotle", "mole ",
                         "pozole", "chile relleno", "carnitas", "cotija"]),
    ("vietnamese",      ["pho", "phở", "banh mi", "bánh mì", "banh xeo", "bánh xèo", "nuoc mam", "nước mắm", "nước chấm", "fish sauce", "rice paper", "lemongrass", "banh trang", "bánh tráng", "bun bo", "bún bò", "com tam", "cơm tấm", "vietnamese"]),
    ("asian",           ["soy sauce", "ginger", "sesame", "bok choy", "tofu",
                         "hoisin", "miso", "dashi", "edamame",
                         "wonton", "dim sum", "ramen", "udon", "soba",
                         "tempura", "teriyaki", "pad thai",
                         "kimchi", "bibimbap", "bulgogi"]),
    ("indian",          ["curry", "garam masala", "turmeric", "cumin",
                         "coriander", "cardamom", "naan ", "basmati", "paneer",
                         "tikka", "masala", "dhal", "dal ", "biryani",
                         "samosa", "tandoori", "raita", "ghee"]),
    ("french",          ["beurre blanc", "béchamel", "coq au vin", "bouillabaisse",
                         "ratatouille", "crème brûlée", "croissant", "brioche",
                         "quiche", "crêpe", "niçoise", "dijon", "gratin",
                         "béarnaise", "tarte tatin", "soufflé"]),
    ("mediterranean",   ["feta", "olive ", "pita ", "hummus", "tahini",
                         "za'atar", "sumac", "harissa", "ras el hanout",
                         "preserved lemon", "couscous", "kebab", "kofta",
                         "shakshuka", "tabbouleh", "fattoush", "baba ganoush",
                         "moussaka", "spanakopita"]),
    ("american",        ["mac and cheese", "cornbread", "pot roast", "meatloaf",
                         "coleslaw", "buffalo chicken", "clam chowder",
                         "new england", "southern fried", "tex-mex", "cajun",
                         "creole", "gumbo", "jambalaya"]),
    ("greek",           ["greek ", "tzatziki", "spanakopita", "gyro", "souvlaki",
                         "moussaka", "kalamata", "dolma", "baklava"]),
    ("middle_eastern",  ["shawarma", "falafel", "kibbeh", "za'atar", "sumac ",
                         "pomegranate molasses"]),
    ("japanese",        ["sushi", "sashimi", "tempura", "ramen", "udon",
                         "miso ", "teriyaki", "katsu", "yakitori", "onigiri",
                         "mochi", "matcha"]),
    ("thai",            ["thai ", "pad thai", "lemongrass", "galangal",
                         "kaffir lime", "thai basil"]),
    ("chinese",         ["chinese ", "hoisin", "five spice", "bok choy",
                         "sesame oil", "rice wine", "kung pao", "lo mein",
                         "chow mein", "mapo tofu"]),
    ("spanish",         ["paella", "chorizo", "manchego", "gazpacho",
                         "patatas bravas", "jamón", "romesco"]),
    ("german",          ["schnitzel", "bratwurst", "sauerkraut", "pretzel ",
                         "strudel", "pumpernickel", "lebkuchen", "sauerbraten"]),
    ("british",         ["shepherd's pie", "bangers and mash", "scone ",
                         "crumpet", "clotted cream", "stilton", "yorkshire"]),
    ("latin_american",  ["chimichurri", "achiote", "plantain", "yuca",
                         "empanada", "ceviche", "peruvian", "colombian",
                         "cuban ", "brazilian", "arroz con"]),
]


def detect_cuisine(title: str, combined: str, clean_ings: list) -> str:
    text = (title + " " + combined + " " + " ".join(clean_ings)).lower()
    scores = {}
    for cuisine, keywords in CUISINE_RULES:
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[cuisine] = hits
    return max(scores, key=scores.get) if scores else "other"


# ── Diet flags ─────────────────────────────────────────────────────────────────

_MEAT    = {"chicken","beef","pork","lamb","turkey","bacon","sausage","ham",
            "veal","duck","venison","bison","prosciutto","pancetta","salami",
            "pepperoni","anchovies","anchovy"}
_SEAFOOD = {"salmon","shrimp","tuna","crab","lobster","scallop","clam",
            "mussel","oyster","fish","cod","tilapia","halibut","squid",
            "octopus","mahi","bass","trout"}
_DAIRY   = {"milk","cream","butter","cheese","yogurt","sour cream",
            "cream cheese","parmesan","mozzarella","cheddar","brie",
            "ghee","custard","heavy cream","half-and-half"}
_GLUTEN  = {"flour","bread","pasta","wheat","barley","rye","semolina",
            "breadcrumb","soy sauce","biscuit","crouton","noodle","couscous"}
_NUTS    = {"almond","walnut","pecan","cashew","pistachio","hazelnut",
            "macadamia","pine nut","chestnut"}


def detect_diet_flags(clean_ings: list) -> list:
    text = " ".join(clean_ings).lower()
    has_meat    = any(w in text for w in _MEAT)
    has_seafood = any(w in text for w in _SEAFOOD)
    has_dairy   = any(w in text for w in _DAIRY)
    has_gluten  = any(w in text for w in _GLUTEN)
    has_nuts    = any(w in text for w in _NUTS)
    flags = []
    if not has_meat and not has_seafood: flags.append("vegetarian")
    if not has_meat and not has_seafood and not has_dairy: flags.append("vegan")
    if not has_gluten: flags.append("gluten_free")
    if not has_dairy:  flags.append("dairy_free")
    if not has_nuts:   flags.append("nut_free")
    return flags


# ── Cook time ──────────────────────────────────────────────────────────────────

_TIME_PATTERNS = [
    (r"(\d+)\s*to\s*(\d+)\s*hours?",   lambda m: int(m.group(2)) * 60),
    (r"(\d+)\s*hours?",                 lambda m: int(m.group(1)) * 60),
    (r"(\d+)\s*to\s*(\d+)\s*minutes?", lambda m: int(m.group(2))),
    (r"(\d+)\s*minutes?",               lambda m: int(m.group(1))),
]


def detect_cook_time(instructions: str):
    for pat, extractor in _TIME_PATTERNS:
        m = re.search(pat, instructions, re.IGNORECASE)
        if m:
            return extractor(m)
    return None


# ── Core chunk builder ─────────────────────────────────────────────────────────

def derive_metadata(key: str, rec: dict, clean_ings: list,
                    parsed: list, nutrition_meta: dict) -> dict:
    title        = safe_str(rec.get("title"))
    instructions = safe_str(rec.get("instructions"))
    combined     = title + " " + instructions
    return {
        "title":                   title,
        "meal_type":               detect_meal_type(title, combined, clean_ings),
        "cuisine":                 detect_cuisine(title, combined, clean_ings),
        "cooking_method":          [m for m, kws in COOKING_METHODS.items()
                                    if any(k in combined.lower() for k in kws)],
        "main_protein":            next(
                                       (p for p in PROTEINS
                                        if p in " ".join(clean_ings).lower()
                                        or p in title.lower()),
                                       None,
                                   ),
        "diet_flags":              detect_diet_flags(clean_ings),
        "ingredient_count":        len(clean_ings),
        "estimated_cook_time_min": detect_cook_time(instructions),
        "has_picture":             bool(safe_str(rec.get("picture_link"))),
        "parsed_ingredients":      parsed,
        # nutrition fields spread flat for Qdrant payload indexing
        **nutrition_meta,
    }


def to_rag_chunk(key: str, rec: dict,
                 qdrant_client=None,
                 nutrition_collection: str = "nutrition",
                 embed_model=None) -> dict:
    clean_ings = clean_ingredients(rec.get("ingredients") or [])
    parsed     = parse_ingredients(clean_ings)

    nutrition_meta = {}
    if qdrant_client is not None:
        nutrition_meta = calculate_recipe_nutrition(
            parsed_ingredients=parsed,
            qdrant_client=qdrant_client,
            collection=nutrition_collection,
            embed_model=embed_model,
        )

    ing_text = "\n".join(f"- {i}" for i in clean_ings)
    text = (
        f"Recipe: {safe_str(rec.get('title'))}\n\n"
        f"Ingredients:\n{ing_text}\n\n"
        f"Instructions:\n{safe_str(rec.get('instructions'))}"
    )
    return {
        "id":       key,
        "text":     text,
        "metadata": derive_metadata(key, rec, clean_ings, parsed, nutrition_meta),
    }


# ── File loading (ijson streaming to handle truncated files) ───────────────────

def load_recipes_safe(path: str):
    """Stream a recipe JSON file, yielding (key, record) pairs.
    Recovers gracefully if the file is truncated mid-record."""
    with open(path, "rb") as f:
        try:
            for key, rec in ijson.kvitems(f, ""):
                yield key, rec
        except ijson.JSONError as e:
            print(f"  ⚠  Truncated at: {e} — partial file recovered above this point")


# ── Main ───────────────────────────────────────────────────────────────────────

def process(input_files: list, output_path: str,
            qdrant_client=None,
            nutrition_collection: str = "nutrition"):
    total_written = total_skipped = 0

    with open(output_path, "w", encoding="utf-8") as outfile:
        for path in input_files:
            written = skipped = 0
            for key, rec in load_recipes_safe(path):
                if not isinstance(rec, dict) or not safe_str(rec.get("title")):
                    skipped += 1
                    continue
                chunk = to_rag_chunk(key, rec, qdrant_client, nutrition_collection)
                outfile.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                written += 1

            print(f"{os.path.basename(path)}: written={written}, skipped={skipped}")
            total_written += written
            total_skipped += skipped

    size_mb = os.path.getsize(output_path) / 1_000_000
    print(f"\nTotal written : {total_written}")
    print(f"Total skipped : {total_skipped}")
    print(f"Output        : {output_path}  ({size_mb:.1f} MB)")