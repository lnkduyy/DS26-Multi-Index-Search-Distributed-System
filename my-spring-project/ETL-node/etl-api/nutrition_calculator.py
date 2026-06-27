"""
nutrition_calculator.py
-----------------------
Calculates total nutrition for a recipe by:
  1. Looking up each parsed ingredient in the Qdrant 'nutrition' collection
  2. Converting the ingredient quantity to grams
  3. Multiplying the per-100g nutrition values by (grams / 100)
  4. Summing across all ingredients

All nutrition values in the Qdrant 'nutrition' collection are per 100g:
    calories  — kcal
    protein   — g
    fat       — g  (null in current dataset; treated as 0 when missing)
    carbs     — g
    fiber     — g
    sugar     — g
    sodium    — g  (stored as grams, NOT milligrams)

Public API
----------
    calculate_recipe_nutrition(
        parsed_ingredients: list[dict],
        qdrant_client,
        collection: str = "nutrition",
    ) -> dict
"""

from __future__ import annotations

import re
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint


# ══════════════════════════════════════════════════════════════════════════════
# 1. UNIT → GRAMS CONVERSION
# ══════════════════════════════════════════════════════════════════════════════

# Weight and volume units with known gram equivalents.
# Volume uses water-density (1 g/ml) as a fallback for ingredients without
# a known density; the lookup below can override with ingredient-specific values.
UNIT_GRAMS: dict[str, float] = {
    # weight — metric
    "g":             1.0,
    "gram":          1.0,
    "grams":         1.0,
    "kg":            1000.0,
    "kilogram":      1000.0,
    "kilograms":     1000.0,
    # weight — imperial
    "oz":            28.3495,
    "ounce":         28.3495,
    "ounces":        28.3495,
    "lb":            453.592,
    "lbs":           453.592,
    "pound":         453.592,
    "pounds":        453.592,
    # volume — metric
    "ml":            1.0,
    "milliliter":    1.0,
    "milliliters":   1.0,
    "l":             1000.0,
    "liter":         1000.0,
    "liters":        1000.0,
    # volume — US
    "tsp":           4.92892,
    "teaspoon":      4.92892,
    "teaspoons":     4.92892,
    "tbsp":          14.7868,
    "tablespoon":    14.7868,
    "tablespoons":   14.7868,
    "fl oz":         29.5735,
    "fluid ounce":   29.5735,
    "fluid ounces":  29.5735,
    "cup":           236.588,
    "cups":          236.588,
    "pint":          473.176,
    "pints":         473.176,
    "quart":         946.353,
    "quarts":        946.353,
    "gallon":        3785.41,
    "gallons":       3785.41,
    # small measures
    "pinch":         0.3,
    "dash":          0.6,
    "drop":          0.05,
    "smidgen":       0.15,
}

# Default gram weights for countable / package units.
# Used when unit is None or a countable like "clove", "egg", "can".
# These are rough culinary medians — good enough for estimation.
COUNTABLE_GRAMS: dict[str, float] = {
    "egg":       50.0,
    "eggs":      50.0,
    # alliums
    "clove":     5.0,       # garlic clove
    "cloves":    5.0,
    "head":      150.0,     # head of garlic / cabbage
    "heads":     150.0,
    # produce
    "onion":     110.0,
    "lemon":     58.0,      # juice of one lemon ≈ 30ml, fruit ≈ 58g edible
    "lime":      44.0,
    "orange":    130.0,
    "tomato":    123.0,
    "potato":    150.0,
    "carrot":    61.0,
    "stalk":     40.0,      # celery stalk
    "stalks":    40.0,
    "sprig":     2.0,       # herb sprig
    "sprigs":    2.0,
    "leaf":      1.0,
    "leaves":    1.0,
    "bunch":     30.0,      # small herb bunch
    "bunches":   30.0,
    # proteins
    "chicken breast": 174.0,
    "breast":    174.0,
    "thigh":     100.0,
    "fillet":    150.0,
    "slice":     28.0,      # deli slice / bread slice
    "slices":    28.0,
    "strip":     20.0,
    "strips":    20.0,
    "piece":     50.0,
    "pieces":    50.0,
    # packages
    "can":       400.0,     # typical 14-15 oz can
    "cans":      400.0,
    "package":   450.0,     # typical 1 lb package
    "packages":  450.0,
    "bag":       450.0,
    "bags":      450.0,
    "box":       400.0,
    "boxes":     400.0,
    "jar":       350.0,
    "jars":      350.0,
    "bottle":    350.0,
    "bottles":   350.0,
    "stick":     113.0,     # stick of butter = 1/2 cup = 113g
    "sticks":    113.0,
    "loaf":      450.0,
    "loaves":    450.0,
    "scoop":     30.0,
    "scoops":    30.0,
    "handful":   30.0,
    "handfuls":  30.0,
    "sheet":     20.0,      # lasagne / filo sheet
    "sheets":    20.0,
    # size descriptors used as units
    "large":     200.0,
    "medium":    130.0,
    "small":     80.0,
    "whole":     150.0,
    "inch":      20.0,      # e.g. "1 inch piece ginger"
    "inches":    20.0,
}

# No-nutrition ingredients to skip entirely (condiments added in trace amounts)
_SKIP_NAMES = frozenset({
    "water", "ice", "ice water", "cold water",
    "cooking spray", "nonstick cooking spray",
    "parchment paper", "plastic wrap",
})


def _to_grams(quantity: Optional[float], unit: Optional[str], name: str) -> Optional[float]:
    """
    Convert a parsed ingredient's quantity + unit into grams.

    Resolution order:
      1. Unit is a known weight/volume → direct conversion
      2. Unit is a known countable     → use COUNTABLE_GRAMS table
      3. Unit is None                  → try to match ingredient name in COUNTABLE_GRAMS
      4. Still nothing                 → return None (ingredient skipped)
    """
    if quantity is None or quantity <= 0:
        return None

    # 1. Known weight/volume unit
    if unit and unit in UNIT_GRAMS:
        return quantity * UNIT_GRAMS[unit]

    # 2. Countable unit (e.g. "clove", "can", "stick")
    if unit and unit in COUNTABLE_GRAMS:
        return quantity * COUNTABLE_GRAMS[unit]

    # 3. No unit — try ingredient name keywords
    name_l = name.lower()
    for keyword, grams in COUNTABLE_GRAMS.items():
        if keyword in name_l:
            return quantity * grams

    # 4. Last resort: assume 1 unit ≈ 100g (so ratio = quantity)
    # This keeps the result in the right ballpark for unnamed items
    #TODO: return None, avoid exponential in total value
    return quantity * 100.0


# ══════════════════════════════════════════════════════════════════════════════
# 2. QDRANT LOOKUP
# ══════════════════════════════════════════════════════════════════════════════

_NUTRITION_FIELDS = ("calories", "protein", "fat", "carbs", "fiber", "sugar", "sodium")

# Normalise ingredient names before searching:
# strip plurals, common descriptors, and preparation adjectives
_STRIP_WORDS = re.compile(
    r"\b(?:fresh|dried|frozen|canned|smoked|ground|whole|raw|cooked|"
    r"boneless|skinless|chopped|diced|minced|sliced|grated|shredded|"
    r"peeled|halved|quartered|crushed|crumbled|melted|softened|"
    r"unsalted|salted|low.fat|fat.free|reduced.fat|light|extra.virgin|"
    r"all.purpose|self.rising|plain)\b",
    re.IGNORECASE,
)
_MULTI_SPACE = re.compile(r"\s{2,}")


def _normalise_query(name: str) -> str:
    """Strip prep/descriptor words to get a cleaner search term."""
    q = _STRIP_WORDS.sub(" ", name)
    q = _MULTI_SPACE.sub(" ", q).strip().strip(",").strip()
    return q if q else name


def _lookup_nutrition(
    name: str,
    qdrant_client: QdrantClient,
    collection: str,
    score_threshold: float = 0.55,
    embed_model = None,
) -> Optional[dict]:
    """
    Search the nutrition collection for the closest matching food.
    Returns the metadata payload of the best match, or None if below threshold.
    """
    query = _normalise_query(name)
    if not query:
        return None

    try:
        if embed_model:
            vector = embed_model.encode(query).tolist()
            results = qdrant_client.query_points(
                collection_name=collection,
                query=vector,
                limit=1,
                score_threshold=score_threshold,
            ).points
        else:
            # Fallback if no model provided
            results, _ = qdrant_client.scroll(
                collection_name=collection,
                scroll_filter={
                    "must": [{"key": "food_name", "match": {"text": query}}]
                },
                limit=1,
                with_payload=True,
            )
    except Exception as e2:
        print(f"Error querying Qdrant for '{query}': {e2}")
        return None

    if not results:
        return None

    payload = results[0].payload
    return payload


# ══════════════════════════════════════════════════════════════════════════════
# 3. PER-INGREDIENT NUTRITION
# ══════════════════════════════════════════════════════════════════════════════

def _scale_nutrition(payload: dict, grams: float) -> dict:
    """
    Scale per-100g nutrition values to the actual gram amount used.
    Returns a dict with the same keys, values scaled to `grams`.
    """
    ratio = grams / 100.0
    scaled = {}
    for field in _NUTRITION_FIELDS:
        val = payload.get(field)
        if val is None:
            scaled[field] = None
        else:
            scaled[field] = round(val * ratio, 4)
    return scaled


# ══════════════════════════════════════════════════════════════════════════════
# 4. RECIPE-LEVEL AGGREGATION
# ══════════════════════════════════════════════════════════════════════════════

def _sum_nutrition(per_ingredient: list[dict]) -> dict:
    """Sum nutrition dicts across all ingredients. None values are treated as 0."""
    totals = {f: 0.0 for f in _NUTRITION_FIELDS}
    for ing_nutrition in per_ingredient:
        for field in _NUTRITION_FIELDS:
            val = ing_nutrition.get(field)
            if val is not None:
                totals[field] += val
    # Round final totals
    return {f: round(v, 3) for f, v in totals.items()}


# ══════════════════════════════════════════════════════════════════════════════
# 5. PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def calculate_recipe_nutrition(
    parsed_ingredients: list[dict],
    qdrant_client: QdrantClient,
    collection: str = "nutrition",
    score_threshold: float = 0.55,
    embed_model = None,
) -> dict:
    """
    Calculate total nutrition for a recipe from its parsed ingredients.

    Parameters
    ----------
    parsed_ingredients : list[dict]
        Output of parse_ingredients() — each dict has keys:
        name, quantity, unit, qty_per_100g
    qdrant_client : QdrantClient
        Connected Qdrant client.
    collection : str
        Name of the Qdrant nutrition collection.
    score_threshold : float
        Minimum similarity score to accept a nutrition match.

    Returns
    -------
    dict with keys:
        nutrition_total     — summed nutrition across all matched ingredients
            calories        (kcal)
            protein         (g)
            fat             (g)
            carbs           (g)
            fiber           (g)
            sugar           (g)
            sodium          (g)   ← stored as grams in the dataset
            sodium_mg       (mg)  ← convenience field: sodium * 1000
        nutrition_matched   — number of ingredients successfully looked up
        nutrition_total_ing — total ingredient count attempted
        nutrition_coverage  — fraction matched (0.0–1.0)
    """
    per_ingredient_nutrition = []
    matched = 0
    attempted = 0

    for ing in parsed_ingredients:
        name = ing.get("name", "")
        if not name or name in _SKIP_NAMES:
            continue

        attempted += 1

        # Convert quantity → grams
        grams = _to_grams(ing.get("quantity"), ing.get("unit"), name)
        if grams is None:
            # No quantity at all (e.g. "salt, to taste") — skip contribution
            # but still count as attempted so coverage reflects reality
            continue

        # Qdrant lookup
        payload = _lookup_nutrition(name, qdrant_client, collection, score_threshold, embed_model)
        if payload is None:
            continue

        matched += 1
        scaled = _scale_nutrition(payload, grams)
        per_ingredient_nutrition.append(scaled)

    totals = _sum_nutrition(per_ingredient_nutrition)

    # Add sodium_mg convenience field
    totals["sodium_mg"] = round(totals["sodium"] * 1000, 1)

    coverage = round(matched / attempted, 3) if attempted > 0 else 0.0

    return {
        "nutrition_total":     totals,
        "nutrition_matched":   matched,
        "nutrition_total_ing": attempted,
        "nutrition_coverage":  coverage,
    }
