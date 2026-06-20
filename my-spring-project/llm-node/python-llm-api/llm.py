"""
food_rag_pipeline.py
────────────────────
Two-collection RAG pipeline for a food assistant.

Collections:
  recipes   — dish names, ingredients, cooking instructions
  nutrition — per-100g macros for individual food items

Flow:
  user query
    → decompose_routing()     (Gemini: parse intent + filters)
    → retrieve()              (Qdrant: vector search + metadata filters)
    → generate_answer()       (Gemini: format final response)
"""

import os
import json
from dataclasses import dataclass, field
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser


from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Document

# ── Environment ────────────────────────────────────────────────────────────────

load_dotenv()

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["GOOGLE_API_KEY"]    = os.getenv("GOOGLE_API_KEY", "")
os.environ["QDRANT_API_KEY"]    = os.getenv("QDRANT_API_KEY", "")

# ── Clients (singletons — created once, reused everywhere) ────────────────────

gemini_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", max_retries=0)

qdrant_client = QdrantClient(
    url="https://cf19a9b2-fef9-49a9-96b2-003c18348045.eu-central-1-0.aws.cloud.qdrant.io:6333",
    api_key=os.environ.get("QDRANT_API_KEY"),
    cloud_inference=True,
)

EMBED_MODEL      = "sentence-transformers/all-minilm-l6-v2"
RECIPES_COL      = "recipes"
NUTRITION_COL    = "nutrition"

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — DECOMPOSE & ROUTE
# ══════════════════════════════════════════════════════════════════════════════

_DECOMPOSE_PROMPT = """You are a query parser for a food assistant. Your job is to parse the user's natural language query into a structured JSON that drives recipe retrieval.

The system uses a single collection — **recipes_nutrition** — which contains recipe instructions, ingredients, and full nutritional information per dish.

═══════════════════════════════════════════════════════════
WHAT THIS COLLECTION SUPPORTS
═══════════════════════════════════════════════════════════

You can answer queries about:
  → What to cook, recipe ideas, cooking methods, dish names
  → Meal type, cuisine, ingredients on hand
  → Calories, protein, fat, carbs, fiber, sugar, sodium per dish
  → Diet constraints (keto, vegan, gluten-free, etc.)
  → "Is X healthy", "high protein meals", "low sodium dinner ideas"

═══════════════════════════════════════════════════════════
FILTER FIELDS
═══════════════════════════════════════════════════════════

── Recipe ───────────────────────────────────────────────
mealType         : main_course | side_dish | dessert | snack | breakfast |
                   soup_stew | salad | beverage | bread_pastry | sauce_condiment
cuisine          : american | italian | asian | mexican | mediterranean |
                   french | indian | japanese | thai | chinese | spanish |
                   greek | german | british | latin_american | middle_eastern | vietnamese | other
cookingMethod    : baked | grilled | slow_cooker | stovetop | fried |
                   steamed | no_cook | pressure  (list — can have multiple)
mainProtein      : chicken | beef | pork | salmon | shrimp | turkey | lamb |
                   tofu | tuna | crab | sausage | bacon | duck | veal | other
dietFlags        : vegetarian | vegan | gluten_free | dairy_free | nut_free
                   (list — can have multiple)
maxIngredients   : integer  (max number of ingredients)
maxCookTime      : integer in minutes
hasPicture       : boolean  (true = must have photo | false = exclude photos | null = no preference)

── Nutrition (all values are per whole dish / per serving) ──
maxCalories      : number  — kcal
minProtein       : number  — grams
maxFat           : number  — grams
maxCarbs         : number  — grams
minFiber         : number  — grams
maxSugar         : number  — grams
maxSodium        : number  — milligrams (always use mg; do NOT convert to grams)
isHighProtein    : boolean  (true = high protein dishes only | null = no preference)
isLowCarb        : boolean  (true = low carb / keto only | null = no preference)
isLowCalorie     : boolean  (true = low calorie / diet-friendly only | null = no preference)

── Ingredients on hand ──────────────────────────────────
ingredientsList      : [string] | null
                       Lowercase ingredient names the user already has.
                       Populate when user says "I have X, Y, Z" or "using X and Y".
ingredientUnits      : [string] | null
                       Parallel array — unit per ingredient, null where unspecified.
ingredientQuantities : [number] | null
                       Parallel array — numeric amount per ingredient, null where unspecified.
                       All three arrays must have equal length when populated.

═══════════════════════════════════════════════════════════
QUERY REWRITING
═══════════════════════════════════════════════════════════

Rewrite the user query as a clean, descriptive phrase for vector search:
  - Remove filler: "something", "maybe", "I want", "can you find", "I have"
  - Preserve food names, diet terms, cuisine words exactly
  - If the user lists ingredients they have, turn them into a dish description:
    "I have chicken, garlic, lemon" → "chicken garlic lemon dinner"
  - If the query is purely nutritional ("how much protein in pasta carbonara"),
    rewrite as a dish name: "pasta carbonara"

═══════════════════════════════════════════════════════════
SODIUM NOTE
═══════════════════════════════════════════════════════════

maxSodium is in **milligrams**. Do not convert.
  "low sodium" (no number given) → maxSodium: 600
  "140mg sodium"                 → maxSodium: 140
  "heart healthy"                → maxSodium: 600  (standard low-sodium threshold)

═══════════════════════════════════════════════════════════
OUTPUT SCHEMA  (return ONLY valid JSON — no markdown, no explanation)
═══════════════════════════════════════════════════════════

{{
  "recipe_query": string,
  "filters": {{
    "meal_type":             null | string,
    "cuisine":               null | string,
    "cooking_method":        null | [string],
    "main_protein":          null | string,
    "diet_flags":            null | [string],
    "max_ingredients":       null | number,
    "max_cook_time":         null | number,
    "has_picture":           null | boolean,
    "max_calories":          null | number,
    "min_protein":           null | number,
    "max_fat":               null | number,
    "max_carbs":             null | number,
    "min_fiber":             null | number,
    "max_sugar":             null | number,
    "max_sodium":            null | number,
    "is_high_protein":       null | boolean,
    "is_low_carb":           null | boolean,
    "is_low_calorie":        null | boolean,
    "ingredients_list":      null | [string],
    "ingredient_units":      null | [string],
    "ingredient_quantities": null | [number]
  }},
  "state": null
}}

═══════════════════════════════════════════════════════════
EXAMPLES
═══════════════════════════════════════════════════════════

User: "quick Italian pasta recipes"
{{"recipe_query":"quick Italian pasta dinner","filters":{{"meal_type":"main_course","cuisine":"italian","cooking_method":["stovetop"],"main_protein":null,"diet_flags":null,"max_ingredients":null,"max_cook_time":30,"has_picture":null,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium":null,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"state":null}}

User: "high protein low carb chicken dinner under 30 minutes"
{{"recipe_query":"high protein low carb chicken dinner","filters":{{"meal_type":"main_course","cuisine":null,"cooking_method":null,"main_protein":"chicken","diet_flags":null,"max_ingredients":null,"max_cook_time":30,"has_picture":null,"max_calories":null,"min_protein":20.0,"max_fat":null,"max_carbs":10.0,"min_fiber":null,"max_sugar":null,"max_sodium":null,"is_high_protein":true,"is_low_carb":true,"is_low_calorie":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"state":null}}

User: "low sodium heart healthy dinner ideas"
{{"recipe_query":"heart healthy low sodium dinner","filters":{{"meal_type":"main_course","cuisine":null,"cooking_method":null,"main_protein":null,"diet_flags":null,"max_ingredients":null,"max_cook_time":null,"has_picture":null,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium":600,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"state":null}}

User: "how many calories in pasta carbonara"
{{"recipe_query":"pasta carbonara","filters":{{"meal_type":null,"cuisine":"italian","cooking_method":null,"main_protein":null,"diet_flags":null,"max_ingredients":null,"max_cook_time":null,"has_picture":null,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium":null,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"state":null}}

User: "I have 200g chicken breast, 3 cloves of garlic, and some olive oil — what can I make?"
{{"recipe_query":"chicken breast garlic olive oil dinner","filters":{{"meal_type":null,"cuisine":null,"cooking_method":null,"main_protein":"chicken","diet_flags":null,"max_ingredients":null,"max_cook_time":null,"has_picture":null,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium":null,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null,"ingredients_list":["chicken breast","garlic","olive oil"],"ingredient_units":["grams","cloves",null],"ingredient_quantities":[200,3,null]}},"state":null}}

User: "vegan gluten-free breakfast with pictures"
{{"recipe_query":"vegan gluten-free breakfast","filters":{{"meal_type":"breakfast","cuisine":null,"cooking_method":null,"main_protein":"tofu","diet_flags":["vegan","gluten_free"],"max_ingredients":null,"max_cook_time":null,"has_picture":true,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium":null,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"state":null}}

Now parse this query:
User: "{user_query}"
"""

# Build chain once at module level — reused on every call
_decompose_chain = (
    ChatPromptTemplate.from_template(_DECOMPOSE_PROMPT)
    | gemini_model
    | StrOutputParser()   # keep as string — Java expects JSON, not Python dict
)



def decompose_routing(user_query: str) -> str:
    """
    Parse user query into structured JSON string for downstream Java processing.
    Returns a valid JSON string — never a Python dict.
    """
    raw = _decompose_chain.invoke({"user_query": user_query})

    # Strip markdown fences Gemini occasionally adds
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # Validate it's actually parseable JSON before sending to Java
    try:
        json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"[decompose_routing] Gemini returned invalid JSON: {e}\nRaw: {clean[:300]}")

    print(f"[decompose_routing] intent: {clean}")
    return clean  # str — valid JSON

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — GENERATE ANSWER
# ══════════════════════════════════════════════════════════════════════════════

def _format_recipe_point(point, rank: int, user_ingredients: list[str] | None) -> str:
    """Format a single recipe ScoredPoint or dict as a context block for the LLM.
    
    Handles two shapes:
      - Qdrant ScoredPoint: point.payload is a dict with 'text', 'estimated_cook_time_min', etc.
      - Java RecipeQueryResult (snake_case JSON): point is a dict where 'payload' is a plain
        text string, and structured fields live at the top level or inside 'metadata'.
    """
    if isinstance(point, dict):
        raw_payload = point.get("payload", {})
        score = point.get("score", 0.0)
        metadata = point.get("metadata") or {}
    else:
        raw_payload = getattr(point, "payload", {})
        score = getattr(point, "score", 0.0)
        metadata = getattr(point, "metadata", {}) or {}

    if isinstance(raw_payload, str):
        text = raw_payload
        payload = {}
    else:
        payload = raw_payload
        text = payload.get("text", "")

    cook_time      = payload.get("estimated_cook_time_min") or metadata.get("cookTime")
    diet_flags     = payload.get("diet_flags") or metadata.get("dietFlags") or []
    cooking_method = payload.get("cooking_method") or metadata.get("cookingMethod") or []
    
    if isinstance(diet_flags, str):
        diet_flags = [diet_flags]
    if isinstance(cooking_method, str):
        cooking_method = [cooking_method]

    nutrition = point.get("nutrition") if isinstance(point, dict) else getattr(point, "nutrition", None)
    if not nutrition:
        nutrition = payload.get("nutrition", {})
        
    nutrition_str = ""
    if nutrition:
        if isinstance(nutrition, dict):
            nutrition_str = (
                f"Nutrition : {nutrition.get('calories', 'N/A')} kcal | "
                f"{nutrition.get('protein', 'N/A')}g protein | "
                f"{nutrition.get('fat', 'N/A')}g fat | "
                f"{nutrition.get('carbs', 'N/A')}g carbs\n"
            )

    time_str = (
        f"{cook_time} min"       if cook_time and 0 < cook_time <= 119 else
        f"{cook_time // 60} hrs {cook_time % 60} mins".replace(" 0 mins", "") if cook_time and cook_time > 119 else
        "not specified"
    )

    overlap_line = ""
    if user_ingredients and text:
        matched = [i for i in user_ingredients if i.lower() in text.lower()]
        if matched:
            overlap_line = f"Matched your ingredients: {', '.join(matched)}\n"

    return (
        f"[Recipe {rank}]\n"
        f"{overlap_line}"
        f"Cook time : {time_str}\n"
        f"Method    : {', '.join(cooking_method) or 'not specified'}\n"
        f"Diet      : {', '.join(diet_flags) or 'none'}\n"
        f"{nutrition_str}"
        f"Score     : {score:.3f}\n"
        f"---\n"
        f"{text}"
    )


def _format_nutrition_point(point, rank: int) -> str:
    """Format a single nutrition ScoredPoint or dict as a context block for the LLM."""
    if isinstance(point, dict):
        payload = point.get("payload", {})
        score = point.get("score", 0.0)
    else:
        payload = getattr(point, "payload", {})
        score = getattr(point, "score", 0.0)
        
    sodium_g   = payload.get("sodium")
    sodium_str = f"{round(sodium_g * 1000, 1)}mg" if sodium_g is not None else "N/A"

    return (
        f"[Nutrition {rank}] {payload.get('food_name', 'unknown').title()}\n"
        f"Calories : {payload.get('calories', 'N/A')} kcal | "
        f"Protein  : {payload.get('protein',  'N/A')}g | "
        f"Fat      : {payload.get('fat',      'N/A')}g | "
        f"Carbs    : {payload.get('carbs',    'N/A')}g | "
        f"Fiber    : {payload.get('fiber',    'N/A')}g | "
        f"Sugar    : {payload.get('sugar',    'N/A')}g | "
        f"Sodium   : {sodium_str}\n"
        f"Score    : {score:.3f}"
    )


def _build_context(
    results: dict | list,
    user_ingredients: list[str] | None,
) -> tuple[str, str]:
    """Build recipe_section and nutrition_section strings for prompt injection."""

    if isinstance(results, list):
        recipe_points = results[:3]
        nutrition_points = []
    else:
        recipe_points = results.get("recipes", [])[:3] if isinstance(results, dict) else []
        nutrition_points = results.get("nutrition", [])[:5] if isinstance(results, dict) else []

    if recipe_points:
        blocks = [_format_recipe_point(p, i + 1, user_ingredients)
                  for i, p in enumerate(recipe_points)]
        recipe_section = (
            "RETRIEVED RECIPES\n"
            "════════════════════════════════════════════════════════\n"
            + "\n\n".join(blocks) + "\n\n"
        )
    else:
        recipe_section = "RETRIEVED RECIPES\nNo recipes found.\n\n"

    if nutrition_points:
        blocks = [_format_nutrition_point(p, i + 1)
                  for i, p in enumerate(nutrition_points)]
        nutrition_section = (
            "RETRIEVED NUTRITION DATA\n"
            "════════════════════════════════════════════════════════\n"
            + "\n".join(blocks) + "\n\n"
        )
    else:
        nutrition_section = ""

    return recipe_section, nutrition_section


_ANSWER_PROMPT = """\
You are a friendly, expert culinary advisor ("Epicure AI").
Your job is to provide a brief, engaging recommendation based ONLY on the retrieved recipes below.

User query: "{user_query}"

{recipe_section}\
{nutrition_section}\
════════════════════════════════════════════════════════
INSTRUCTIONS
════════════════════════════════════════════════════════

General rules:
- Answer using only retrieved data — never invent recipes, ingredients, or nutrition values.
- If nothing was retrieved, say so clearly and suggest the user broaden their search.
- DO NOT output the full instructions or full ingredient lists. The UI already shows the full recipe cards.
- Keep it to a short paragraph (2-4 sentences max).
- Speak directly to the user in a warm, helpful tone.

Format:
- Just write a flowing, conversational paragraph.
- Mention the top 1 or 2 best matching recipes by name (in bold).
- Briefly explain WHY they are a good fit for the user's query (e.g., matching their ingredients, hitting their macro goals, or fitting their cooking time).

Example output:
"Based on the pork and tofu you have, I highly recommend **Spicy Pork and Tofu Stir-fry**. It's quick to make in just 20 minutes, packed with flavor, and gives you a great protein boost! Or, if you're looking for something lighter, the **Minced Pork Tofu Soup** is a perfect comforting choice."
"""

_answer_chain = (
    ChatPromptTemplate.from_template(_ANSWER_PROMPT)
    | gemini_model
    | StrOutputParser()
)


def generate_answer(
    user_query: str,
    results: dict | list,
    user_ingredients: list[str] | None = None,
) -> str:
    """
    Format retrieved documents into prompt context and generate final answer.

    Args:
        user_query       : original user question
        results          : output of retrieve()
        user_ingredients : ingredient keywords from user query for overlap highlighting
    """
    recipe_section, nutrition_section = _build_context(results, user_ingredients)

    answer = _answer_chain.invoke({
        "user_query":        user_query,
        "recipe_section":    recipe_section,
        "nutrition_section": nutrition_section,
    })

    return answer


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPER
# ══════════════════════════════════════════════════════════════════════════════

def display_results(results: dict) -> None:
    """Pretty-print raw retrieval results (for debugging)."""
    intent = results.get("intent", {})
    print(f"\nReason  : {intent.get('reason', 'N/A')}")
    print(f"Estimate: {intent.get('estimate_nutrition', False)}")

    if results["recipes"]:
        print(f"\n── Recipes ({len(results['recipes'])}) ──────────────────────────")
        for p in results["recipes"]:
            cook_time = p.payload.get("estimated_cook_time_min")
            time_str  = f"{cook_time} min" if cook_time and cook_time > 0 else "time unknown"
            print(
                f"  [{p.score:.3f}] {p.payload.get('title', 'Unknown')}"
                f"  ({p.payload.get('cuisine', '')} · "
                f"{p.payload.get('meal_type', '')} · {time_str})"
            )

    if results["nutrition"]:
        print(f"\n── Nutrition ({len(results['nutrition'])}) ──────────────────────")
        for p in results["nutrition"]:
            sodium_g   = p.payload.get("sodium")
            sodium_str = f"{round(sodium_g * 1000)}mg" if sodium_g is not None else "N/A"
            print(
                f"  [{p.score:.3f}] {p.payload.get('food_name', 'Unknown')}"
                f"  ({p.payload.get('calories', 'N/A')} kcal · "
                f"{p.payload.get('protein', 'N/A')}g protein · "
                f"{p.payload.get('carbs', 'N/A')}g carbs · {sodium_str} sodium)"
            )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = "Find a vegetarian baked dessert under 20 minutes"

    # Stage 1 — decompose
    intent = decompose_routing(question)

    # Stage 2 — retrieve
    results = retrieve(
        user_query=question,
        intent=intent,
        limit=5,
    )
    display_results(results)

    # Stage 3 — generate answer
    # Extract protein keyword for ingredient overlap highlighting
    protein = (intent.get("recipe_filters") or {}).get("main_protein")
    user_ingredients = [protein] if protein else None

    answer = generate_answer(
        user_query=question,
        results=results,
        user_ingredients=user_ingredients,
    )
    print("\n── Final Answer ─────────────────────────────────────────")
    print(answer)