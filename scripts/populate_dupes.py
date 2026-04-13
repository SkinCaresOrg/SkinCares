"""
populate_dupes.py

Batch job that runs find_dupes() for every product in the catalogue
and writes the results to the product_dupes table in Supabase.

Usage:
    python scripts/populate_dupes.py

Environment variables required (.env):
    SUPABASE_URL
    SUPABASE_KEY  (service_role key — needed to bypass RLS)
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Make sure skincarelib is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skincarelib.models.dupe_finder import find_dupes, PRODUCT_INDEX

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BATCH_SIZE = 100        # rows per supabase insert
TOP_N = 3              # dupes per product
LOG_EVERY = 500         # print progress every N products


def run():
    product_ids = list(PRODUCT_INDEX.keys())
    total = len(product_ids)
    print(f"Starting populate_dupes for {total} products...")

    batch = []
    inserted = 0
    skipped = 0
    errors = 0

    for i, product_id in enumerate(product_ids):
        try:
            results = find_dupes(product_id, top_n=TOP_N, explain=True)

            for _, row in results.iterrows():
                batch.append({
                    "source_product_id": int(product_id),
                    "dupe_product_id":   int(row["product_id"]),
                    "dupe_score":        float(row["dupe_score"]),
                    "cosine_sim":        float(row["cosine_sim"]),
                    "price_score":       float(row["price_score"]),
                    "ingredient_group_score": float(row["ingredient_group_score"]),
                    "explanation":       str(row.get("explanation", "")),
                })

        except ValueError:
            skipped += 1
            continue
        except Exception as e:
            errors += 1
            print(f"  ERROR product_id={product_id}: {e}")
            continue

        # flush batch
        if len(batch) >= BATCH_SIZE:
            _flush(batch)
            inserted += len(batch)
            batch = []

        if (i + 1) % LOG_EVERY == 0:
            print(f"  [{i+1}/{total}] inserted={inserted} skipped={skipped} errors={errors}")

    # flush remaining
    if batch:
        _flush(batch)
        inserted += len(batch)

    print(f"\nDone. inserted={inserted} skipped={skipped} errors={errors}")


def _flush(batch: list):
    """Insert a batch of rows, ignoring duplicates."""
    try:
        supabase.table("product_dupes").upsert(
            batch,
            on_conflict="source_product_id,dupe_product_id"
        ).execute()
    except Exception as e:
        print(f"  Supabase flush error: {e}")


if __name__ == "__main__":
    start = time.time()
    run()
    print(f"Elapsed: {time.time() - start:.1f}s")