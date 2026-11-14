"""
upload_recipes.py
-----------------
End-to-end workflow for adding new recipes to Qdrant.

Pipeline
--------
  Input JSON  →  enrich (metadata + nutrition)  →  Qdrant upsert

Usage
-----
    python upload_recipes.py --input new_dishes.json

Or call programmatically:
    from upload_recipes import ingest
    ingest("new_dishes.json")
"""

import argparse
import json
import os
import re
import tempfile
import uuid

import torch
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, PayloadSchemaType
)

# ── pipeline modules (must be in the same directory) ──────────────────────────
from enrich_recipes import to_rag_chunk, load_recipes_safe
from nutrition_calculator import calculate_recipe_nutrition


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG  — edit these or override via environment variables
# ══════════════════════════════════════════════════════════════════════════════

QDRANT_URL        = os.getenv("QDRANT_URL",
    "https://cf19a9b2-fef9-49a9-96b2-003c18348045.eu-central-1-0.aws.cloud.qdrant.io:6333")
QDRANT_API_KEY    = ""
COLLECTION        = "recipes_nutrition2"
NUTRITION_COLLECTION = "nutrition"
VECTOR_DIM        = 384
BATCH_SIZE        = 512


# ══════════════════════════════════════════════════════════════════════════════
# QDRANT SETUP
# ══════════════════════════════════════════════════════════════════════════════

INDEXED_FIELDS = {
    "meal_type":                  PayloadSchemaType.KEYWORD,
    "cuisine":                    PayloadSchemaType.KEYWORD,
    "main_protein":               PayloadSchemaType.KEYWORD,
    "cooking_method":             PayloadSchemaType.KEYWORD,
    "diet_flags":                 PayloadSchemaType.KEYWORD,
    "ingredient_count":           PayloadSchemaType.INTEGER,
    "estimated_cook_time_min":    PayloadSchemaType.INTEGER,
    "has_picture":                PayloadSchemaType.BOOL,
    "ingredients_list":           PayloadSchemaType.KEYWORD,
    "nutrition_total.calories":   PayloadSchemaType.FLOAT,
    "nutrition_total.protein":    PayloadSchemaType.FLOAT,
    "nutrition_total.fat":        PayloadSchemaType.FLOAT,
    "nutrition_total.carbs":      PayloadSchemaType.FLOAT,
    "nutrition_total.fiber":      PayloadSchemaType.FLOAT,
    "nutrition_total.sugar":      PayloadSchemaType.FLOAT,
    "nutrition_total.sodium_mg":  PayloadSchemaType.FLOAT,
    "nutrition_coverage":         PayloadSchemaType.FLOAT,
}


def _ensure_collection(client: QdrantClient):
    """Create collection and payload indexes if they don't exist yet."""
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"  Created collection '{COLLECTION}'")

    for field, schema in INDEXED_FIELDS.items():
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name=field,
            field_schema=schema,
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAYLOAD BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def _build_payload(meta: dict) -> dict:
    """
    Flatten nested fields so Qdrant dot-notation indexes resolve correctly.
    """
    nt = meta.get("nutrition_total") or {}
    return {
        "text": meta.get("text", ""),
        **{k: v for k, v in meta.items()
           if k not in ("parsed_ingredients", "nutrition_total", "text")},
        # parsed_ingredients → parallel arrays
        "ingredients_list":          [p["name"]         for p in meta.get("parsed_ingredients", [])],
        "quantities_list":           [p["quantity"]     for p in meta.get("parsed_ingredients", [])],
        "units_list":                [p["unit"]         for p in meta.get("parsed_ingredients", [])],
        "qty_per_100g_list":         [p["qty_per_100g"] for p in meta.get("parsed_ingredients", [])],
        # nutrition_total → flat dot-notation keys
        "nutrition_total.calories":  nt.get("calories"),
        "nutrition_total.protein":   nt.get("protein"),
        "nutrition_total.fat":       nt.get("fat"),
        "nutrition_total.carbs":     nt.get("carbs"),
        "nutrition_total.fiber":     nt.get("fiber"),
        "nutrition_total.sugar":     nt.get("sugar"),
        "nutrition_total.sodium_mg": nt.get("sodium_mg"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def _upload_chunks(
    chunks:  list[dict],
    model:   SentenceTransformer,
    client:  QdrantClient,
):
    """Embed and upsert a list of enriched chunks into Qdrant."""
    texts    = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=256).tolist()

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload=_build_payload({**c["metadata"], "text": c["text"]}),
        )
        for emb, c in zip(embeddings, chunks)
    ]
    client.upsert(collection_name=COLLECTION, points=points)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

def ingest(
    input_path:  str,
    batch_size:  int = BATCH_SIZE,
    api_key:     str = QDRANT_API_KEY,
    qdrant_url:  str = QDRANT_URL,
):
    """
    Full pipeline: JSON file → enrich → upload to Qdrant.

    Parameters
    ----------
    input_path : path to the new recipes JSON file
    batch_size : how many recipes to embed and upload per batch
    api_key    : Qdrant API key (falls back to QDRANT_API_KEY env var)
    qdrant_url : Qdrant cluster URL
    """
    # ── 1. Init clients ───────────────────────────────────────────────────────
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  Embedding device : {device}")
    model = SentenceTransformer("all-MiniLM-L6-v2", device=device)

    client = QdrantClient(url=qdrant_url, api_key=api_key)
    _ensure_collection(client)

    # ── 2. Load input JSON ────────────────────────────────────────────────────
    with open(input_path, encoding="utf-8") as f:
        raw_data: dict = json.load(f)

    total = len(raw_data)
    print(f"  Loaded {total} recipes from {input_path}")

    # ── 3. Enrich + upload in batches ─────────────────────────────────────────
    batch:   list[dict] = []
    written  = skipped = 0

    for key, rec in raw_data.items():
        # Skip malformed records
        if not isinstance(rec, dict) or not (rec.get("title") or "").strip():
            skipped += 1
            continue

        # Enrich: metadata + nutrition lookup against the nutrition collection
        chunk = to_rag_chunk(
            key, rec,
            qdrant_client=client,
            nutrition_collection=NUTRITION_COLLECTION,
        )
        batch.append(chunk)

        if len(batch) >= batch_size:
            _upload_chunks(batch, model, client)
            written += len(batch)
            batch.clear()
            print(f"  Uploaded {written}/{total} ...", end="\r")

    # Final partial batch
    if batch:
        _upload_chunks(batch, model, client)
        written += len(batch)

    print(f"\n  Done. Uploaded={written}  Skipped={skipped}  "
          f"Collection='{COLLECTION}'")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest new recipes into Qdrant.")
    parser.add_argument("--input",   required=True, help="Path to the recipes JSON file")
    parser.add_argument("--api-key", default=QDRANT_API_KEY, help="Qdrant API key")
    parser.add_argument("--url",     default=QDRANT_URL,     help="Qdrant cluster URL")
    parser.add_argument("--batch",   type=int, default=BATCH_SIZE, help="Upload batch size")
    args = parser.parse_args()

    ingest(
        input_path=args.input,
        batch_size=args.batch,
        api_key=args.api_key,
        qdrant_url=args.url,
    )
