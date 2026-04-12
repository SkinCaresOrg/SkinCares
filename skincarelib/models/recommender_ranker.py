import json
from pathlib import Path

import numpy as np
import pandas as pd

from skincarelib.models.similarity import score_similarity
from skincarelib.models.user_profile import build_user_vector

ROOT = Path(__file__).resolve().parent.parent.parent

VECTORS_PATH = ROOT / "artifacts" / "product_vectors.npy"
INDEX_PATH = ROOT / "artifacts" / "product_index.json"
SIGNALS_PATH = ROOT / "data" / "processed" / "products_with_signals.csv"

_SIGNAL_COLS = [
    "hydration",
    "barrier",
    "acne_control",
    "soothing",
    "exfoliation",
    "antioxidant",
    "irritation_risk",
]
_SCORE_COLS = [
    "score_dry",
    "score_oily",
    "score_sensitive",
    "score_combination",
    "score_normal",
]

_EMPTY_RECS = pd.DataFrame(
    columns=["product_id", "brand", "category", "price", "similarity"]
)


def load_artifacts():
    """Load product vectors, index, and metadata from disk."""
    vectors = np.load(VECTORS_PATH)

    with open(INDEX_PATH) as f:
        product_index = json.load(f)

    metadata = pd.read_csv(SIGNALS_PATH)

    if "product_id" not in metadata.columns:
        metadata.insert(0, "product_id", metadata.index.astype(str))
    metadata["product_id"] = metadata["product_id"].astype(str)

    for col in ["brand", "category", "price"]:
        if col not in metadata.columns:
            metadata[col] = ""

    metadata["price"] = pd.to_numeric(metadata["price"], errors="coerce")

    return vectors, product_index, metadata


def rank_products(
    user_vector,
    product_vectors,
    metadata_df,
    constraints,
    top_n=10,
    tokens_df=None,
    product_index=None,
):
    """
    Filter the product catalog by constraints and rank by similarity to the user vector.

    Args:
        user_vector:     np.ndarray shape (N_features,)
        product_vectors: np.ndarray shape (N, N_features)
        metadata_df:     DataFrame with columns [product_id, brand, category, price]
                         and optionally [skin_type, score_dry, …, hydration, …]
        constraints:     dict with optional keys:
                           budget (float): max price in dollars (inclusive)
                           categories (list[str]): allowed category names
                           skin_type (str): restrict to products labelled for this skin type
                             e.g. "dry" | "oily" | "sensitive" | "combination" | "normal"
                           banned_ingredients (list[str]): ingredient tokens to exclude
                           liked_product_ids (list[str]): already-liked products to exclude
        top_n:           int, number of recommendations to return
        tokens_df:       DataFrame with columns [product_id, ingredient_tokens] (for banned filtering)
        product_index:   dict mapping product_id (str) -> row index (int)

    Returns:
        DataFrame with columns [product_id, brand, category, price, similarity,
        skin_type, score_dry, score_oily, score_sensitive, score_combination,
        score_normal, hydration, barrier, acne_control, soothing, exfoliation,
        antioxidant, irritation_risk] — signal/score columns present only when
        available in metadata_df.
    """
    candidates = metadata_df.copy()

    # --- Filter 1: Budget (hard cap on raw price) ---
    budget = constraints.get("budget")
    if budget is not None:
        candidates = candidates[candidates["price"] <= float(budget)]

    # --- Filter 2: Category / routine step ---
    allowed_categories = constraints.get("categories")
    if allowed_categories:
        candidates = candidates[candidates["category"].isin(allowed_categories)]

    # --- Filter 3: Skin type ---
    skin_type_filter = (constraints.get("skin_type") or "").lower().strip()
    if skin_type_filter and "skin_type" in candidates.columns:
        candidates = candidates[candidates["skin_type"] == skin_type_filter]

    # --- Filter 4: Banned ingredients ---
    banned_ingredients = constraints.get("banned_ingredients") or []
    if banned_ingredients and tokens_df is not None:
        banned_set = {ing.lower().strip() for ing in banned_ingredients}

        def has_no_banned(token_string):
            if not isinstance(token_string, str) or not token_string.strip():
                return True  # missing data -> pass through safely
            tokens = {t.strip().lower() for t in token_string.split(",")}
            return tokens.isdisjoint(banned_set)

        keep_cols = [c for c in candidates.columns]
        merged = candidates.merge(
            tokens_df[["product_id", "ingredient_tokens"]],
            on="product_id",
            how="left",
        )
        mask = merged["ingredient_tokens"].apply(has_no_banned)
        candidates = merged[mask][keep_cols]

    # --- Filter 5: Exclude already-liked products ---
    liked_ids = constraints.get("liked_product_ids") or []
    if liked_ids:
        candidates = candidates[~candidates["product_id"].isin(liked_ids)]

    if candidates.empty:
        return _EMPTY_RECS.copy()

    # --- Score: cosine similarity on filtered subset ---
    # Guard against products that are in metadata but not in the vector index
    if product_index is not None:
        valid_mask = candidates["product_id"].isin(product_index)
        candidates = candidates[valid_mask].reset_index(drop=True)

    if candidates.empty:
        return _EMPTY_RECS.copy()

    is_cold_start = np.linalg.norm(user_vector) < 1e-9

    if not is_cold_start and product_index is not None:
        candidate_indices = [product_index[pid] for pid in candidates["product_id"]]
        candidate_vectors = product_vectors[candidate_indices]
        sims = score_similarity(user_vector, candidate_vectors)
    else:
        sims = np.zeros(len(candidates), dtype=np.float32)

    candidates = candidates.copy()
    candidates["similarity"] = sims

    # --- Rank ---
    if is_cold_start:
        # Cold start fallback: return highest-priced (proxy for popular/premium) products
        # Probably not ideal but better than random. Might be better to use some kindof review metric
        recs = candidates.sort_values("price", ascending=False).head(top_n)
    else:
        recs = candidates.sort_values("similarity", ascending=False).head(top_n)

    base_cols = ["product_id", "brand", "category", "price", "similarity"]
    extra_cols = ["skin_type"] + _SCORE_COLS + _SIGNAL_COLS
    out_cols = base_cols + [c for c in extra_cols if c in recs.columns]
    return recs[out_cols].reset_index(drop=True)


def recommend(liked_product_ids, explicit_prefs, constraints, top_n=10):
    """
    End-to-end recommendation pipeline. Loads artifacts from disk on each call.
    Note to self: Might change later if we want to call frequently and need to cache artifacts in memory.

    Args:
        liked_product_ids: list[str]
        explicit_prefs:    dict (see build_user_vector for keys)
        constraints:       dict (see rank_products for keys)
        top_n:             int

    Returns:
        DataFrame with columns [product_id, brand, category, price, similarity]
    """
    vectors, product_index, metadata_df = load_artifacts()
    # tokens_df is derived from the same signals CSV; prefer ingredient_tokens_clean,
    # fall back to ingredient_tokens so the banned-ingredient filter works unchanged.
    tokens_raw = pd.read_csv(SIGNALS_PATH)
    if "product_id" not in tokens_raw.columns:
        tokens_raw.insert(0, "product_id", tokens_raw.index.astype(str))
    tokens_raw["product_id"] = tokens_raw["product_id"].astype(str)
    token_col = (
        "ingredient_tokens_clean"
        if "ingredient_tokens_clean" in tokens_raw.columns
        else "ingredient_tokens"
    )
    tokens_df = tokens_raw[["product_id", token_col]].rename(
        columns={token_col: "ingredient_tokens"}
    )

    user_vector = build_user_vector(
        liked_product_ids, explicit_prefs, vectors, product_index
    )

    # Pass liked_product_ids into constraints so ranked results exclude them
    merged_constraints = dict(constraints)
    if liked_product_ids:
        existing = merged_constraints.get("liked_product_ids") or []
        merged_constraints["liked_product_ids"] = list(
            set(existing) | set(liked_product_ids)
        )

    return rank_products(
        user_vector=user_vector,
        product_vectors=vectors,
        metadata_df=metadata_df,
        constraints=merged_constraints,
        top_n=top_n,
        tokens_df=tokens_df,
        product_index=product_index,
    )
