"""
parse_ingredients.py
--------------------
Parses raw recipe ingredient strings into structured records.

Each ingredient produces:
    {
        "name":         str          — cleaned ingredient name
        "quantity":     float | None — numeric amount in original units
        "unit":         str | None   — canonical unit; None when absent OR unrecognised
        "qty_per_100g": float | None — quantity per 100 g (None for countable/unknown units)
    }

Public API
----------
    parse_ingredient(raw: str)      -> dict
    parse_ingredients(lines: list)  -> list[dict]
"""

import re
from fractions import Fraction
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# 1. UNIT TABLES
# ══════════════════════════════════════════════════════════════════════════════

# TODO: remove "large", "medium", "small", "whole", "extra-large", "extra large", let COUNTABLE_GRAMS fallback handles
UNIT_TO_GRAMS: dict[str, Optional[float]] = {
    # metric weight
    "gram":          1.0,
    "grams":         1.0,
    "g":             1.0,
    "kilogram":      1000.0,
    "kilograms":     1000.0,
    "kg":            1000.0,
    # imperial weight
    "ounce":         28.3495,
    "ounces":        28.3495,
    "oz":            28.3495,
    "pound":         453.592,
    "pounds":        453.592,
    "lb":            453.592,
    "lbs":           453.592,
    # metric volume (water-density approximation)
    "milliliter":    1.0,
    "milliliters":   1.0,
    "ml":            1.0,
    "liter":         1000.0,
    "liters":        1000.0,
    "l":             1000.0,
    # US volume
    "teaspoon":      4.92892,
    "teaspoons":     4.92892,
    "tsp":           4.92892,
    "tablespoon":    14.7868,
    "tablespoons":   14.7868,
    "tbsp":          14.7868,
    "fluid ounce":   29.5735,
    "fluid ounces":  29.5735,
    "fl oz":         29.5735,
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
    # countable / package — no gram equivalent
    "package":       None,
    "packages":      None,
    "can":           None,
    "cans":          None,
    "jar":           None,
    "jars":          None,
    "bottle":        None,
    "bottles":       None,
    "bag":           None,
    "bags":          None,
    "box":           None,
    "boxes":         None,
    "bunch":         None,
    "bunches":       None,
    "head":          None,
    "heads":         None,
    "clove":         None,
    "cloves":        None,
    "slice":         None,
    "slices":        None,
    "piece":         None,
    "pieces":        None,
    "sprig":         None,
    "sprigs":        None,
    "stalk":         None,
    "stalks":        None,
    "strip":         None,
    "strips":        None,
    "sheet":         None,
    "sheets":        None,
    "loaf":          None,
    "loaves":        None,
    "stick":         None,
    "sticks":        None,
    "scoop":         None,
    "scoops":        None,
    "serving":       None,
    "servings":      None,
    "handful":       None,
    "handfuls":      None,
    "inch":          None,
    "inches":        None,
    "whole":         None,
    "large":         None,
    "medium":        None,
    "small":         None,
    "extra-large":   None,
    "extra large":   None,
    "leaf":          None,
    "leaves":        None,
}

_UNIT_ALIASES: dict[str, str] = {
    "c":    "cup",
    "c.":   "cup",
    "t":    "tsp",
    "t.":   "tsp",
    "ts":   "tsp",
    "tbl":  "tbsp",
    "T":    "tbsp",
    "T.":   "tbsp",
    "pt":   "pint",
    "qt":   "quart",
    "gal":  "gallon",
}


def _canonical_unit(raw: str) -> Optional[str]:
    """Resolve a raw token to its canonical unit name, or None if not in whitelist."""
    key = raw.lower().rstrip(".")
    key = _UNIT_ALIASES.get(key, key)
    return key if key in UNIT_TO_GRAMS else None


# ══════════════════════════════════════════════════════════════════════════════
# 2. PRE-CLEANING PATTERNS
# ══════════════════════════════════════════════════════════════════════════════

_ADVERTISEMENT_RE = re.compile(r"\s*ADVERTISEMENT\s*", re.IGNORECASE)

# "(optional)" in any form, with optional leading comma/space
_OPTIONAL_RE = re.compile(r",?\s*\(?\s*optional\s*\)?", re.IGNORECASE)

# Trailing qualifier after a comma:
#   ", or to taste"  ", as needed"  ", or more"  ", if desired"  etc.
_OR_QUALIFIER_RE = re.compile(
    r",\s*(?:or\s+)?(?:"
    r"to taste|as needed|as desired|as required|"
    r"to serve|for garnish|for serving|to garnish|"
    r"or more(?: to taste)?|or more as needed|"
    r"more or less|if desired|if needed"
    r")\s*$",
    re.IGNORECASE,
)

# Bare "to taste" / "as needed" with no leading comma (standalone at end of string)
_BARE_QUALIFIER_RE = re.compile(
    r"\s+(?:to taste|as needed|as desired|as required|"
    r"to serve|to garnish|for garnish|for serving)\s*$",
    re.IGNORECASE,
)

# Parenthesised size hints to strip before quantity parsing
# e.g. "(10.75 ounce)", "(1 inch)", "(about 2 cups)"
_PAREN_SIZE_RE = re.compile(
    r"\(\s*(?:about\s+)?[\d/. ]+\s*"
    r"(?:ounce|oz|pound|lb|gram|g|ml|liter|inch|cup|tablespoon|teaspoon)s?\s*\)",
    re.IGNORECASE,
)

# Generic remaining parentheticals (brand names, variety notes, etc.)
_PAREN_GENERIC_RE = re.compile(r"\([^)]*\)")


# ══════════════════════════════════════════════════════════════════════════════
# 3. NUMBER PARSING
# ══════════════════════════════════════════════════════════════════════════════

_UNICODE_FRACTIONS = {
    "½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4",
    "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
    "⅙": "1/6", "⅚": "5/6", "⅕": "1/5", "⅖": "2/5",
    "⅗": "3/5", "⅘": "4/5",
}

_NUM_RE = re.compile(
    r"(?P<mixed>\d+\s+\d+/\d+)"
    r"|(?P<fraction>\d+/\d+)"
    r"|(?P<decimal>\d+(?:\.\d+)?)",
)

_ARTICLE_RE = re.compile(r"^(an?)\s+", re.IGNORECASE)
_RANGE_SEP_RE = re.compile(r"^(?:to|-)\s*", re.IGNORECASE)


def _normalise_unicode(text: str) -> str:
    for uc, asc in _UNICODE_FRACTIONS.items():
        text = text.replace(uc, " " + asc + " ")
    return text.strip()


def _parse_number(text: str) -> tuple[Optional[float], str]:
    """Extract a leading number; return (value, remainder)."""
    text = _normalise_unicode(text)

    m_art = _ARTICLE_RE.match(text)
    if m_art:
        return 1.0, text[m_art.end():]

    m = _NUM_RE.match(text)
    if not m:
        return None, text

    span = m.group(0)
    remainder = text[m.end():].strip()

    if m.group("mixed"):
        whole_s, frac_s = span.split(None, 1)
        value = int(whole_s) + float(Fraction(frac_s))
    elif m.group("fraction"):
        value = float(Fraction(span))
    else:
        value = float(span)

    return value, remainder


def _maybe_lower_range(value: float, remainder: str) -> tuple[float, str]:
    """If remainder opens with a range separator, discard upper bound and advance."""
    m = _RANGE_SEP_RE.match(remainder)
    if not m:
        return value, remainder
    after = remainder[m.end():]
    value2, after2 = _parse_number(after)
    if value2 is not None:
        return value, after2   # keep lower bound already in `value`
    return value, remainder


# ══════════════════════════════════════════════════════════════════════════════
# 4. UNIT REGEX  (whitelist, longest token first)
# ══════════════════════════════════════════════════════════════════════════════

_all_unit_tokens = sorted(
    list(UNIT_TO_GRAMS.keys()) + list(_UNIT_ALIASES.keys()),
    key=len, reverse=True,
)
_UNIT_RE = re.compile(
    r"^(?P<unit>" + "|".join(re.escape(u) for u in _all_unit_tokens) + r")\.?\b",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════════════
# 5. NAME CLEANING
# ══════════════════════════════════════════════════════════════════════════════

# Prep notes that appear after a comma — stop keeping parts when we see these
_PREP_START_RE = re.compile(
    r"^\s*(?:"
    # adverbs
    r"finely|thinly|roughly|coarsely|freshly|lightly|well|very|"
    # past-participle prep verbs
    r"cut|sliced|diced|chopped|minced|grated|shredded|peeled|halved|"
    r"quartered|julienned|trimmed|rinsed|drained|cooked|cooled|"
    r"softened|melted|sifted|beaten|divided|packed|heaping|"
    r"juiced|zested|squeezed|seeded|deveined|butterflied|"
    r"toasted|roasted|dried|frozen|canned|smoked|crumbled|crushed|"
    # state descriptors
    r"room temperature|at room temperature|"
    # taste/quantity qualifiers (residual — belt-and-suspenders)
    r"or to taste|to taste|or more|or less"
    r")\b",
    re.IGNORECASE,
)

_LEADING_OF_RE = re.compile(r"^of\s+", re.IGNORECASE)
_NOISE_EDGE_RE  = re.compile(r"^\W+|\W+$")


def _clean_name(text: str) -> str:
    """
    Strip prep notes, parentheticals, and edge noise from a name fragment.
    Splits on commas; stops at the first part that looks like a prep instruction.
    """
    text = _LEADING_OF_RE.sub("", text.strip())
    text = _PAREN_GENERIC_RE.sub("", text).strip()

    parts = text.split(",")
    kept = []
    for i, part in enumerate(parts):
        if i > 0 and _PREP_START_RE.match(part):
            break
        kept.append(part)

    text = ", ".join(kept)
    # Strip leading standalone appearance adjectives that precede the noun
    text = re.sub(
        r'^(?:skinless|boneless|(?:boneless\s+)?skinless|(?:skinless\s+)?boneless)[,\s]+',
        '', text, flags=re.IGNORECASE
    ).strip()
    text = _NOISE_EDGE_RE.sub("", text).strip()
    return text.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 6. MAIN PARSERS
# ══════════════════════════════════════════════════════════════════════════════

def parse_ingredient(raw: str) -> dict:
    """
    Parse a single raw ingredient string.

    Returns:
        {
            "name":         str,
            "quantity":     float | None,
            "unit":         str | None,   — None when absent OR unrecognised
            "qty_per_100g": float | None, — None for countable / non-weight units
        }
    """
    # ── Step 1: pre-clean noise ────────────────────────────────────────────────
    text = _ADVERTISEMENT_RE.sub("", raw).strip()
    text = _OPTIONAL_RE.sub("", text).strip()          # remove (optional)
    text = _OR_QUALIFIER_RE.sub("", text).strip()      # remove ", or to taste" etc.
    text = _BARE_QUALIFIER_RE.sub("", text).strip()    # remove bare "to taste" at end
    text = text.rstrip(",").strip()
    text = _PAREN_SIZE_RE.sub("", text).strip()        # remove "(10.75 ounce)" hints

    if not text:
        return {"name": "", "quantity": None, "unit": None, "qty_per_100g": None}

    # ── Step 2: parse leading number ──────────────────────────────────────────
    quantity, after_num = _parse_number(text)

    # ── Step 3: handle range → keep lower bound ───────────────────────────────
    if quantity is not None:
        quantity, after_num = _maybe_lower_range(quantity, after_num)

    # ── Step 4: parse unit ────────────────────────────────────────────────────
    unit: Optional[str] = None
    after_unit = after_num.strip()
    if after_unit:
        m = _UNIT_RE.match(after_unit)
        if m:
            resolved = _canonical_unit(m.group("unit"))
            if resolved is not None:
                unit = resolved
                after_unit = after_unit[m.end():].strip()
            # Unrecognised token → leave as part of the name (unit stays None)

    # ── Step 5: qty_per_100g ──────────────────────────────────────────────────
    qty_per_100g: Optional[float] = None
    if unit is not None and quantity is not None:
        g = UNIT_TO_GRAMS.get(unit)
        if g is not None and g > 0:
            qty_per_100g = round(100.0 / g, 4)

    # ── Step 6: clean ingredient name ────────────────────────────────────────
    name = _clean_name(after_unit)

    return {
        "name":         name,
        "quantity":     quantity,
        "unit":         unit,
        "qty_per_100g": qty_per_100g,
    }


def parse_ingredients(raw_list: list) -> list[dict]:
    """
    Parse a list of raw ingredient strings.

    Skips blank lines, pure ADVERTISEMENT noise, and entries with no
    recoverable name. Returns a list of dicts aligned to valid inputs.
    """
    results = []
    for raw in raw_list:
        if not isinstance(raw, str):
            continue
        if not _ADVERTISEMENT_RE.sub("", raw).strip():
            continue
        parsed = parse_ingredient(raw)
        if parsed["name"]:
            results.append(parsed)
    return results


# ══════════════════════════════════════════════════════════════════════════════
# 7. SMOKE TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    SAMPLES = [
        # Basic
        "4 skinless, boneless chicken breast halves ADVERTISEMENT",
        "2 tablespoons butter ADVERTISEMENT",
        "1 1/2 cups all-purpose flour",
        "3/4 pound Stilton, crumbled and softened",
        "2 (10.75 ounce) cans condensed cream of chicken soup ADVERTISEMENT",
        "1 onion, finely diced ADVERTISEMENT",
        "½ teaspoon ground cinnamon",
        "8 ounces whole wheat rotini pasta ADVERTISEMENT",
        "12 egg whites",
        "a pinch of salt",
        "an egg",
        # Previously broken: or-to-taste / optional
        "1/4 cup medium-dry Sherry, or to taste",
        "1 cup brown sugar, or to taste",
        "2 tablespoons butter, or as needed",
        "1 tablespoon white sugar, or to taste (optional)",
        "1 pinch cayenne pepper, or to taste",
        "1/2 cup chopped walnuts (optional)",
        "1 (8 ounce) package shredded Cheddar cheese (optional)",
        "sour cream (optional)",
        "3 tablespoons pecans (optional)",
        "2 teaspoons minced garlic (optional)",
        # Bare unquantifiable
        "Salt",
        "Freshly ground black pepper",
        "ground black pepper to taste",
        # Range
        "2-3 cloves garlic, minced",
        "2 to 3 tablespoons drained green peppercorns",
        # No unit (countable)
        "3 eggs",
        "1 lemon, juiced",
        "2 pounds skinless, boneless chicken breast halves, cut into thin strips",
        # Unicode fraction
        "⅓ cup olive oil",
    ]

    print(f"{'RAW':<58} {'NAME':<34} {'QTY':>6}  {'UNIT':<14} {'PER100g':>8}")
    print("─" * 128)
    for raw in SAMPLES:
        p = parse_ingredient(raw)
        qty  = f"{p['quantity']:.3f}"    if p["quantity"]   is not None else "—"
        unit = p["unit"]                 if p["unit"]        is not None else "—"
        p100 = f"{p['qty_per_100g']:.4f}" if p["qty_per_100g"] is not None else "—"
        print(f"{raw[:57]:<58} {p['name'][:33]:<34} {qty:>6}  {unit:<14} {p100:>8}")
