from pathlib import Path
import importlib.util
import json
import os
import tempfile
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from enrich_recipes import to_rag_chunk

import torch
from sentence_transformers import SentenceTransformer

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading SentenceTransformer on {device}...")
model = SentenceTransformer("all-MiniLM-L6-v2", device=device)

DEFAULT_PATH = Path(__file__).resolve().parent / "enrich_recipe.py"
ETL_PATH = Path(os.getenv("ETL_NODE_PATH", DEFAULT_PATH)).resolve()

app = FastAPI(title="Recipe Ingest API")

load_dotenv()

qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
qdrant_client = QdrantClient(
    url="https://cf19a9b2-fef9-49a9-96b2-003c18348045.eu-central-1-0.aws.cloud.qdrant.io:6333",
    api_key=qdrant_api_key,
)

# Ensure the food_name index exists on startup
from qdrant_client.http import models
try:
    print("Ensuring text index on 'food_name' in 'nutrition' collection...")
    qdrant_client.create_payload_index(
        collection_name="nutrition",
        field_name="food_name",
        field_schema=models.TextIndexParams(
            type="text",
            tokenizer=models.TokenizerType.WORD,
            min_token_len=2,
            max_token_len=15,
            lowercase=True,
        )
    )
except Exception as e:
    pass # Usually throws an error if it already exists, which is fine

# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

class Dish(BaseModel):
    id:            Optional[str]       = None
    name:          str                          # maps to → title
    ingredients:   list[str]
    cooking_method: Optional[str] = None         # maps to → instructions

class DishesPayload(BaseModel):
    dishes: list[Dish]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _dishes_to_recipe_json(dishes: list[Dish]) -> dict:
    """
    Convert the dishes.json schema into the {uuid: recipe} format
    that ingest_recipes.ingest() expects.

    dishes.json field   →   ingest_recipes field
    -----------------       --------------------
    name                →   title
    ingredients         →   ingredients  (list[str])
    cooking_method      →   instructions
    id                  →   used as the recipe key (uuid4 if absent)
    """
    return {
        (dish.id or str(uuid.uuid4())): {
            "title":        dish.name,
            "ingredients":  dish.ingredients,
            "instructions": dish.cooking_method or "",
            "picture_link": None,
        }
        for dish in dishes
    }


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process")
def process_dishes(payload: DishesPayload):
    """
    Process new dishes and return enriched RAG chunks.
    """
    if not payload.dishes:
        raise HTTPException(status_code=400, detail="dishes list is empty")

    recipe_dict = _dishes_to_recipe_json(payload.dishes)

    chunks = []
    for key, rec in recipe_dict.items():
        chunk = to_rag_chunk(
            key,
            rec,
            qdrant_client=qdrant_client,
            nutrition_collection="nutrition",
            embed_model=model
        )
        # Generate vector using the local model
        vector = model.encode(chunk["text"], show_progress_bar=False).tolist()
        chunk["vector"] = vector
        
        # Flatten metadata for Qdrant dot-notation indexing
        meta = chunk["metadata"]
        nt = meta.get("nutrition_total") or {}
        parsed = meta.get("parsed_ingredients", [])
        flattened_meta = {
            **{k: v for k, v in meta.items() if k not in ("parsed_ingredients", "nutrition_total", "text")},
            "ingredients_list":          [p.get("name")         for p in parsed if isinstance(p, dict)],
            "quantities_list":           [p.get("quantity")     for p in parsed if isinstance(p, dict)],
            "units_list":                [p.get("unit")         for p in parsed if isinstance(p, dict)],
            "qty_per_100g_list":         [p.get("qty_per_100g") for p in parsed if isinstance(p, dict)],
            "nutrition_total.calories":  nt.get("calories")  if isinstance(nt, dict) else None,
            "nutrition_total.protein":   nt.get("protein")   if isinstance(nt, dict) else None,
            "nutrition_total.fat":       nt.get("fat")       if isinstance(nt, dict) else None,
            "nutrition_total.carbs":     nt.get("carbs")     if isinstance(nt, dict) else None,
            "nutrition_total.fiber":     nt.get("fiber")     if isinstance(nt, dict) else None,
            "nutrition_total.sugar":     nt.get("sugar")     if isinstance(nt, dict) else None,
            "nutrition_total.sodium_mg": nt.get("sodium_mg") if isinstance(nt, dict) else None,
        }
        chunk["metadata"] = flattened_meta
        
        chunks.append(chunk)

    return chunks

# uvicorn app:app --port 6000 --reload

# Invoke-RestMethod -Uri "http://localhost:8080/api/dishes" -Method Post -ContentType "application/json" -Body '{"name": "Spaghetti Bolognese", "ingredients": ["1 pound ground beef", "2 cups tomato sauce", "2 cloves garlic", "1 medium onion"], "cookingMethod": "Boil spaghetti until al dente. In a pan, cook ground beef with garlic and onion, then add tomato sauce. Mix with pasta."}'