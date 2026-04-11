import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import faiss

from .dupe_scorer import DupeScorer
from .dupe_explainer import explain_dupe


ROOT = Path(__file__).resolve().parent.parent.parent

VECTORS_PATH     = ROOT / "artifacts" / "product_vectors.npy"
INDEX_PATH       = ROOT / "artifacts" / "product_index.json"
SCHEMA_PATH      = ROOT / "artifacts" / "feature_schema.json"
METADATA_PATH    = ROOT / "data" / "processed" / "products_with_signals.csv"
FAISS_INDEX_PATH = ROOT / "artifacts" / "faiss.index"

# How many ANN neighbours to fetch from FAISS before price/subtype filtering.
# Larger = better recall at the cost of more scoring work downstream.
FAISS_RETRIEVAL_K = 2500  # ~5% of the catalogue


# ---------------------------
# Product subtype detection
# ---------------------------
PRODUCT_TYPE_PATTERNS = {
    "eye_treatment": ["eye"],
    "lip_treatment": ["lip"],
    "hand_care": ["hand"],
    "body_care": ["body"],
    "cleanser": ["cleanser", "face wash", "wash"],
    "serum": ["serum", "ampoule"],
    "sunscreen": ["spf", "sunscreen", "sun screen"],
    "mask": ["mask"],
    "toner": ["toner", "essence"],
}


def infer_product_subtype(product_name: str):
    """Infer a more specific product subtype from product name."""
    name = str(product_name).lower()

    for subtype, keywords in PRODUCT_TYPE_PATTERNS.items():
        if any(keyword in name for keyword in keywords):
            return subtype

    return None


# ---------------------------
# Load artifacts
# ---------------------------
def load_artifacts():
    vectors = np.load(VECTORS_PATH)

    with open(INDEX_PATH) as f:
        product_index = json.load(f)

    with open(SCHEMA_PATH) as f:
        feature_schema = json.load(f)

    metadata = pd.read_csv(METADATA_PATH)
    metadata.columns = metadata.columns.str.lower()
    metadata["product_id"] = metadata.index.astype(str)

    needed = {"product_id", "brand", "price", "product_name", "category"}
    missing = needed - set(metadata.columns)
    if missing:
        raise ValueError(f"products_with_signals.csv missing columns: {missing}")

    metadata["price"] = pd.to_numeric(metadata["price"], errors="coerce")
    metadata = metadata[metadata["product_id"].isin(product_index)].copy()
    metadata = metadata.reset_index(drop=True)

    # faiss.read_index raises RuntimeError if the file is missing,
    # not FileNotFoundError, so we catch both at the call site
    faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))

    return vectors, product_index, feature_schema, metadata, faiss_index


_LOAD_ERROR: Optional[Exception] = None

try:
    VECTORS, PRODUCT_INDEX, FEATURE_SCHEMA, METADATA, FAISS_INDEX = load_artifacts()
except (FileNotFoundError, RuntimeError) as e:
    import warnings

    _LOAD_ERROR = e
    warnings.warn(f"Could not load artifacts: {e}. Running in degraded mode.")

    VECTORS        = None
    PRODUCT_INDEX  = {}
    FEATURE_SCHEMA = None
    FAISS_INDEX    = None
    METADATA = pd.DataFrame(
        columns=["product_id", "product_name", "brand", "category", "price"]
    )

INDEX_TO_ID   = {v: k for k, v in PRODUCT_INDEX.items()}
_PRICE_LOOKUP = METADATA.set_index("product_id")["price"].to_dict()

if FEATURE_SCHEMA is not None and PRODUCT_INDEX:
    SCORER = DupeScorer(VECTORS, PRODUCT_INDEX, FEATURE_SCHEMA, _PRICE_LOOKUP)
else:
    SCORER = None


# ---------------------------
# FAISS-based candidate retrieval
# ---------------------------
def _faiss_candidates(source_id: str, k: int = FAISS_RETRIEVAL_K) -> list:
    """Return up to k product IDs nearest to source via FAISS ANN search.

    Vectors are L2-normalised at index build time so inner product == cosine
    similarity. Replaces the previous full dataframe scan, which does not
    scale beyond ~50k products.
    """
    source_idx = PRODUCT_INDEX[source_id]
    query = VECTORS[source_idx].reshape(1, -1).copy().astype(np.float32)
    faiss.normalize_L2(query)

    _, neighbour_indices = FAISS_INDEX.search(query, k + 1)
    neighbour_indices = neighbour_indices.flatten()

    return [
        INDEX_TO_ID[idx]
        for idx in neighbour_indices
        if idx in INDEX_TO_ID and INDEX_TO_ID[idx] != source_id
    ]


# ---------------------------
# Main dupe finder
# ---------------------------
def find_dupes(product_id, top_n=5, max_price=None, weights=None, explain=True):
    if SCORER is None or FAISS_INDEX is None:
        raise RuntimeError(
            "DupeScorer not initialized — artifacts failed to load at import time.\n"
            f"Expected files:\n"
            f"  {VECTORS_PATH}\n"
            f"  {INDEX_PATH}\n"
            f"  {SCHEMA_PATH}\n"
            f"  {METADATA_PATH}\n"
            f"  {FAISS_INDEX_PATH}\n"
            f"Original error: {_LOAD_ERROR}\n"
            "Run vectorizer.py to regenerate missing artifacts."
        )

    if product_id not in PRODUCT_INDEX:
        raise ValueError(f"Unknown product_id: {product_id!r}")

    source_row      = METADATA[METADATA["product_id"] == product_id].iloc[0]
    source_category = source_row["category"]
    source_price    = source_row["price"]
    source_subtype  = infer_product_subtype(source_row["product_name"])

    # --- Retrieval: FAISS ANN instead of full dataframe scan ---
    candidate_ids = _faiss_candidates(product_id, k=FAISS_RETRIEVAL_K)

    # --- Filtering ---
    candidates = METADATA[METADATA["product_id"].isin(candidate_ids)].copy()

    # Must be same category and cheaper
    candidates = candidates[
        (candidates["category"] == source_category)
        & (candidates["price"] < source_price)
    ]

    # Subtype filter — keyword based
    if source_subtype is not None:
        filtered = candidates[
            candidates["product_name"].str.lower().apply(
                lambda name: infer_product_subtype(name) == source_subtype
            )
        ].copy()

        if not filtered.empty:
            candidates = filtered

    if max_price is not None:
        candidates = candidates[candidates["price"] <= max_price]

    if candidates.empty:
        return pd.DataFrame(
            columns=[
                "product_id", "product_name", "brand", "category", "price",
                "dupe_score", "cosine_sim", "price_score", "ingredient_group_score",
            ]
        )

    scored = SCORER.score(
        source_id=product_id,
        source_price=source_price,
        candidate_ids=candidates["product_id"].tolist(),
        weights=weights,
    )

    results = candidates.merge(scored, on="product_id", how="inner")
    results = (
        results.sort_values("dupe_score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    results = results[[
        "product_id", "product_name", "brand", "category", "price",
        "dupe_score", "cosine_sim", "price_score", "ingredient_group_score",
    ]]

    if explain:
        results["explanation"] = results.apply(
            lambda row: explain_dupe(source_row, row), axis=1
        )

    return results


def get_artifacts():
    return VECTORS, PRODUCT_INDEX, FEATURE_SCHEMA, METADATA


# ---------------------------
# Demo run
# ---------------------------
if __name__ == "__main__":
    demo_id  = next(iter(PRODUCT_INDEX))
    demo_row = METADATA[METADATA["product_id"] == demo_id].iloc[0]

    print("Finding dupes for:")
    print(f"  {demo_row['brand']} | {demo_row['category']} | ${demo_row['price']:.2f}")
    print()

    results = find_dupes(demo_id)

    if results.empty:
        print("No cheaper dupes found.")
    else:
        pd.set_option("display.max_colwidth", 80)
        print(results.to_string(index=False, float_format="%.4f"))