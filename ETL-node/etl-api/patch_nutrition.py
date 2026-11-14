"""
patch_nutrition.py
------------------
Patches nutrition metadata into an already-enriched recipe JSONL file.
Uses semantic vector search (SentenceTransformer) to match ingredients
against the Qdrant nutrition collection.

Speed optimisations
-------------------
1. Batch embedding   — all unique uncached ingredient names in a recipe
                       batch are embedded in a single model.encode() call
                       (SentenceTransformer is heavily vectorised for this).
2. Parallel Qdrant   — embeddings are dispatched to Qdrant concurrently
                       via ThreadPoolExecutor, eliminating sequential
                       round-trip latency.
3. Pre-warm cache    — the two steps above run before per-recipe calculation,
                       so the calculation loop is pure in-memory cache hits.

Other features
--------------
- Ingredient-level cache (disk-persisted JSON) survives restarts
- Checkpoint/resume — safe to interrupt and re-run
- Google Drive save after every batch — output never lost on disconnect

Usage (Colab):
    from patch_nutrition import patch_nutrition
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    patch_nutrition(
        input_path="/content/recipes_rag_enriched.jsonl",
        output_path="/content/drive/MyDrive/recipes_rag_enriched_nutrition.jsonl",
        qdrant_client=qdrant_client,
        embed_model=model,
        nutrition_collection="nutrition",
        cache_path="/content/drive/MyDrive/nutrition_cache.json",
        checkpoint_path="/content/drive/MyDrive/nutrition_patch_checkpoint.txt",
    )
"""

from __future__ import annotations

import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from qdrant_client import QdrantClient

from nutrition_calculator import (
    _SKIP_NAMES,
    _to_grams,
    _normalise_query,
    _scale_nutrition,
    _sum_nutrition,
)


# ══════════════════════════════════════════════════════════════════════════════
# CACHE
# ══════════════════════════════════════════════════════════════════════════════

class NutritionCache:
    """
    Disk-backed ingredient → per-100g nutrition payload cache.
    Key  : normalised ingredient name string
    Value: metadata dict from Qdrant (per 100g), or None if no match found.
           None is a valid cached result — it means the ingredient was looked
           up and genuinely not found, so we don't re-query it.
    """

    def __init__(self, cache_path: str = "nutrition_cache.json"):
        self.path     = cache_path
        self._data: dict[str, Optional[dict]] = {}
        self._hits    = 0
        self._misses  = 0
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self._data = json.load(f)
            print(f"  Cache loaded: {len(self._data):,} entries from {self.path}")

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self, key: str) -> tuple[bool, Optional[dict]]:
        if key in self._data:
            self._hits += 1
            return True, self._data[key]
        self._misses += 1
        return False, None

    def set(self, key: str, value: Optional[dict]):
        self._data[key] = value

    @property
    def stats(self) -> str:
        total = self._hits + self._misses
        rate  = self._hits / total * 100 if total else 0
        return (f"cache {len(self._data):,} entries | "
                f"hits={self._hits:,} misses={self._misses:,} "
                f"hit-rate={rate:.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING
# ══════════════════════════════════════════════════════════════════════════════

def _make_query_texts(names: list[str]) -> list[str]:
    """
    Format ingredient names to match how the nutrition collection was indexed.
    """
    return [f"Nutrition facts for {n}:" for n in names]


def _batch_embed(names: list[str], embed_model) -> dict[str, list[float]]:
    """
    Embed a list of unique ingredient names in one vectorised call.
    Returns a dict mapping each name → its embedding vector.
    """
    if not names:
        return {}
    texts   = _make_query_texts(names)
    vectors = embed_model.encode(texts, show_progress_bar=False, batch_size=256)
    return {name: vec.tolist() for name, vec in zip(names, vectors)}


# ══════════════════════════════════════════════════════════════════════════════
# PARALLEL QDRANT LOOKUP
# ══════════════════════════════════════════════════════════════════════════════

def _single_qdrant_query(
    query:           str,
    vector:          list[float],
    qdrant_client:   QdrantClient,
    collection:      str,
    score_threshold: float,
) -> tuple[str, Optional[dict]]:
    """Single Qdrant search — designed to run inside a thread pool."""
    try:
        response = qdrant_client.query_points(
            collection_name=collection,
            query=vector,
            limit=1,
            score_threshold=score_threshold,
            with_payload=True,
        )
        payload = response.points[0].payload if response.points else None
    except Exception as e:
        print(f"  ⚠ Lookup failed for '{query}': {e}")
        payload = None
    return query, payload


def _prewarm_cache(
    queries:         list[str],        # normalised ingredient names not yet cached
    vectors:         dict[str, list[float]],
    qdrant_client:   QdrantClient,
    collection:      str,
    cache:           NutritionCache,
    score_threshold: float,
    max_workers:     int,
):
    """
    Fire all uncached Qdrant lookups concurrently, then store results in cache.
    After this returns, every query in `queries` is in the cache.
    """
    if not queries:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _single_qdrant_query,
                q, vectors[q], qdrant_client, collection, score_threshold,
            ): q
            for q in queries
            if q in vectors          # skip if embedding failed for any reason
        }
        for future in as_completed(futures):
            query, payload = future.result()
            cache.set(query, payload)


# ══════════════════════════════════════════════════════════════════════════════
# BATCH PRE-WARM  (collect → embed → query in parallel)
# ══════════════════════════════════════════════════════════════════════════════

def prewarm_batch(
    chunks:          list[dict],
    qdrant_client:   QdrantClient,
    collection:      str,
    embed_model,
    cache:           NutritionCache,
    score_threshold: float,
    max_workers:     int,
):
    """
    Given a list of recipe chunks (one batch), find all unique uncached
    ingredient names, embed them all at once, then query Qdrant in parallel.
    After this call the cache has entries for every ingredient in the batch.
    """
    # 1. Collect unique normalised names not already in cache
    uncached: set[str] = set()
    for chunk in chunks:
        for ing in chunk["metadata"].get("parsed_ingredients", []):
            name = ing.get("name", "")
            if not name or name in _SKIP_NAMES:
                continue
            q = _normalise_query(name)
            if q and q not in cache._data:
                uncached.add(q)

    if not uncached:
        return   # everything already cached

    # 2. Batch embed all uncached names in one call
    vectors = _batch_embed(list(uncached), embed_model)

    # 3. Parallel Qdrant queries
    _prewarm_cache(
        list(uncached), vectors,
        qdrant_client, collection,
        cache, score_threshold, max_workers,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PER-RECIPE NUTRITION  (pure cache — no network calls after prewarm)
# ══════════════════════════════════════════════════════════════════════════════

def _calculate_nutrition_from_cache(
    parsed_ingredients: list[dict],
    cache:              NutritionCache,
) -> dict:
    per_ingredient = []
    matched = attempted = 0

    for ing in parsed_ingredients:
        name = ing.get("name", "")
        if not name or name in _SKIP_NAMES:
            continue
        attempted += 1

        grams = _to_grams(ing.get("quantity"), ing.get("unit"), name)
        if grams is None:
            continue

        q = _normalise_query(name)
        _, payload = cache.get(q) if q else (False, None)
        if payload is None:
            continue

        matched += 1
        per_ingredient.append(_scale_nutrition(payload, grams))

    totals = _sum_nutrition(per_ingredient)
    totals["sodium_mg"] = round(totals["sodium"] * 1000, 1)
    coverage = round(matched / attempted, 3) if attempted else 0.0

    return {
        "nutrition_total":     totals,
        "nutrition_matched":   matched,
        "nutrition_total_ing": attempted,
        "nutrition_coverage":  coverage,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHECKPOINT + DRIVE FLUSH
# ══════════════════════════════════════════════════════════════════════════════

def _load_checkpoint(path: str) -> int:
    if os.path.exists(path):
        with open(path) as f:
            return int(f.read().strip())
    return -1


def _save_checkpoint(path: str, line_index: int):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(line_index))
    os.replace(tmp, path)


def _flush_to_drive(local_path: str, drive_path: str):
    if not os.path.exists(local_path):
        return
    with open(local_path, encoding="utf-8") as src, \
         open(drive_path, "a", encoding="utf-8") as dst:
        shutil.copyfileobj(src, dst)
    open(local_path, "w").close()   # clear buffer


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def patch_nutrition(
    input_path:           str,
    output_path:          str,
    qdrant_client:        QdrantClient,
    embed_model,
    nutrition_collection: str   = "nutrition",
    batch_size:           int   = 10_000,
    score_threshold:      float = 0.55,
    max_workers:          int   = 32,
    cache_path:           str   = "nutrition_cache.json",
    checkpoint_path:      str   = "nutrition_patch_checkpoint.txt",
):
    """
    Patch nutrition metadata into an enriched recipe JSONL file.

    Parameters
    ----------
    input_path           : source JSONL (already has parsed_ingredients)
    output_path          : destination JSONL on Drive (nutrition fields added)
    qdrant_client        : connected QdrantClient
    embed_model          : SentenceTransformer model (same as used to index nutrition)
    nutrition_collection : Qdrant collection name for nutrition data
    batch_size           : recipes per batch (default 10 000)
    score_threshold      : minimum cosine similarity to accept a match
    max_workers          : parallel Qdrant threads (default 32; tune to your
                           Qdrant plan's rate limit — reduce if you get 429s)
    cache_path           : ingredient cache JSON path (put on Drive)
    checkpoint_path      : resume checkpoint path (put on Drive)
    """
    cache     = NutritionCache(cache_path)
    resume_at = _load_checkpoint(checkpoint_path)

    if resume_at >= 0:
        print(f"  Resuming from line {resume_at + 1} "
              f"(lines 0–{resume_at} already saved to Drive)")

    print("  Counting total records...", end="\r")
    with open(input_path, encoding="utf-8") as f:
        total_lines = sum(1 for _ in f)
    print(f"  Total records: {total_lines:,}")

    local_batch_path = input_path + ".batch_buf.jsonl"
    open(local_batch_path, "w").close()
    if not os.path.exists(output_path):
        open(output_path, "w").close()

    batch_num   = 0
    batch_start = time.time()
    lines_done  = resume_at + 1 if resume_at >= 0 else 0

    with open(input_path, encoding="utf-8") as fin:
        # Read the whole file into RAM in streaming windows of batch_size
        pending: list[tuple[int, dict]] = []   # (line_index, chunk)

        for i, line in enumerate(fin):
            if i <= resume_at:
                continue

            pending.append((i, json.loads(line)))

            if len(pending) < batch_size and i < total_lines - 1:
                continue   # keep accumulating

            # ── we have a full batch (or it's the last line) ──────────────

            chunks = [c for _, c in pending]

            # Step 1: embed all unique uncached ingredients + parallel Qdrant
            t_prewarm = time.time()
            prewarm_batch(
                chunks, qdrant_client, nutrition_collection,
                embed_model, cache, score_threshold, max_workers,
            )
            prewarm_secs = time.time() - t_prewarm

            # Step 2: calculate nutrition for every recipe (pure cache hits)
            with open(local_batch_path, "w", encoding="utf-8") as fbatch:
                for line_i, chunk in pending:
                    parsed    = chunk["metadata"].get("parsed_ingredients", [])
                    nutrition = _calculate_nutrition_from_cache(parsed, cache)
                    chunk["metadata"].update(nutrition)
                    fbatch.write(json.dumps(chunk, ensure_ascii=False) + "\n")

            lines_done += len(pending)
            last_i      = pending[-1][0]
            pending.clear()

            # Step 3: flush to Drive + save cache + checkpoint
            _flush_to_drive(local_batch_path, output_path)
            cache.save()
            _save_checkpoint(checkpoint_path, last_i)

            batch_num += 1
            elapsed    = time.time() - batch_start
            remaining  = total_lines - lines_done
            eta_min    = (elapsed / batch_size * remaining) / 60 if lines_done > 0 else 0

            print(
                f"  Batch {batch_num} saved ✓ | "
                f"{lines_done:,}/{total_lines:,} lines | "
                f"prewarm {prewarm_secs:.0f}s | total {elapsed:.0f}s | "
                f"ETA ~{eta_min:.0f} min | {cache.stats}"
            )
            batch_start = time.time()

    if os.path.exists(local_batch_path):
        os.remove(local_batch_path)

    print(f"\n  Done. {lines_done:,} records → {output_path}")
    print(f"  {cache.stats}")