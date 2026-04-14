import json
import os
from pathlib import Path
from typing import Optional
import warnings
import logging

import numpy as np
import pandas as pd

try:
    import faiss
except ImportError:
    faiss = None
from .dupe_scorer import DupeScorer
from .dupe_explainer import explain_dupe

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent

VECTORS_PATH = ROOT / "artifacts" / "product_vectors.npy"
INDEX_PATH = ROOT / "artifacts" / "product_index.json"
SCHEMA_PATH = ROOT / "artifacts" / "feature_schema.json"
METADATA_PATH = ROOT / "data" / "processed" / "products_with_signals.csv"
FAISS_INDEX_PATH = ROOT / "artifacts" / "faiss.index"

# How many ANN neighbours to fetch from FAISS before price/subtype filtering.
FAISS_RETRIEVAL_K = 1000  # ~2% of the catalogue


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


REMOTE_ASSET_MODE = bool(os.getenv("SUPABASE_URL", "").strip())
SUPPRESS_MISSING_ASSET_WARNINGS = (
    _is_truthy(os.getenv("SKINCARES_SUPPRESS_MISSING_ASSET_WARNINGS", ""))
    or REMOTE_ASSET_MODE
)
AUTO_REBUILD_ARTIFACTS = _is_truthy(
    os.getenv(
        "SKINCARES_AUTO_REBUILD_ARTIFACTS",
        "false" if REMOTE_ASSET_MODE else "true",
    )
)


def _notify(message: str) -> None:
    if SUPPRESS_MISSING_ASSET_WARNINGS:
        logger.info(message)
    else:
        warnings.warn(message)


def _core_artifact_paths() -> tuple[Path, Path, Path]:
    return VECTORS_PATH, INDEX_PATH, SCHEMA_PATH


def _ensure_core_artifacts() -> None:
    missing = [path for path in _core_artifact_paths() if not path.exists()]
    if not missing:
        return

    missing_message = "Missing core artifacts: " + ", ".join(
        str(path) for path in missing
    )
    if not AUTO_REBUILD_ARTIFACTS:
        raise FileNotFoundError(missing_message)

    _notify(missing_message + ". Attempting to rebuild from source data.")

    from . import vectorizer

    vectorizer.run()

    still_missing = [path for path in _core_artifact_paths() if not path.exists()]
    if still_missing:
        raise FileNotFoundError(
            "Auto-rebuild did not produce required artifacts: "
            + ", ".join(str(path) for path in still_missing)
        )


def _build_faiss_index(vectors: np.ndarray):
    if faiss is None:
        raise RuntimeError("faiss is not installed")

    normalized = vectors.copy().astype(np.float32)
    faiss.normalize_L2(normalized)

    dim = normalized.shape[1]
    index = faiss.IndexHNSWFlat(dim, 48, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = 300
    index.hnsw.efSearch = 256

    index.add(normalized)
    return index


def _load_or_rebuild_faiss_index(vectors: np.ndarray):
    if faiss is None:
        raise RuntimeError("faiss is not installed")

    if FAISS_INDEX_PATH.exists():
        try:
            return faiss.read_index(str(FAISS_INDEX_PATH))
        except RuntimeError as error:
            _notify(
                f"Could not read existing FAISS index at {FAISS_INDEX_PATH}: {error}. "
                "Rebuilding from vectors."
            )
    else:
        _notify(f"Missing FAISS index at {FAISS_INDEX_PATH}. Rebuilding from vectors.")

    index = _build_faiss_index(vectors)
    try:
        FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(FAISS_INDEX_PATH))
    except Exception as write_error:
        _notify(
            f"Rebuilt FAISS index in memory but could not persist to "
            f"{FAISS_INDEX_PATH}: {write_error}"
        )
    return index


# ---------------------------
# Product subtype detection
# ---------------------------

# Direct mapping from dataset category labels to internal subtypes.
# Used as the primary signal — more reliable than keyword matching since
# it uses the explicit label already assigned to the product.
CATEGORY_TO_SUBTYPE = {
    # Eye
    "Eye Cream, Gel, Oils, & Serum": "eye_treatment",
    "Eye Masks & Pads": "eye_treatment",
    "Eyes": "eye_treatment",
    "Dark Circle Treatments": "eye_treatment",
    "Puffiness Treatments": "eye_treatment",
    "Eyelid + Lash": "eye_treatment",
    # Lip
    "Lip Balms, Gels, Moisturizers & Oils": "lip_treatment",
    "Lip Care": "lip_treatment",
    "Lip Exfoliators + Scrubs": "lip_treatment",
    "Lip Mask": "lip_treatment",
    "Lips": "lip_treatment",
    # Hand & foot
    "Hand": "hand_care",
    "Hand Masks": "hand_care",
    "Moisturizing Gloves": "hand_care",
    "Liquid or Cream Hand Soaps": "hand_soap",
    "Feet": "foot_care",
    "Foot Mask": "foot_care",
    # Neck
    "Neck & Décolleté": "neck_care",
    # Masks
    "Facial Masks": "mask",
    "Face": "mask",
    # Exfoliators
    "Facial Scrubs": "exfoliator",
    "Exfoliators": "exfoliator",
    "Exfoliators & Scrubs": "exfoliator",
    "Exfoliators, Polishes, & Scrubs": "exfoliator",
    "Microdermabrasion": "exfoliator",
    "Polishes": "exfoliator",
    "Scrubs": "exfoliator",
    # Peels
    "Acids & Peels": "peel",
    "Peels": "peel",
    "Glycolic Acid": "peel",
    "Salicylic Acid": "peel",
    "Alpha Beta": "peel",
    # Cleansers
    "Facial Cleansers": "cleanser",
    "Facial Cleansing Milks": "cleanser",
    "Facial Foaming Cleansers": "cleanser",
    "Facial Washes": "cleanser",
    "Foaming Cleansers": "cleanser",
    "Cleansers": "cleanser",
    "Pore Cleansing": "cleanser",
    "Facial Cleansing Oil": "cleansing_oil",
    "Micellar Water": "micellar",
    "Facial Wipes": "wipes",
    "Cloths, Towelettes, & Wipes": "wipes",
    "Facial Bar Soap": "soap",
    "Bar Soaps": "soap",
    "Liquid Cleansers & Soaps": "soap",
    # Serums
    "Serums": "serum",
    "Serum": "serum",
    "Moisturizing Serums": "serum",
    "Complexes": "serum",
    "Drops": "serum",
    "Ampoules": "serum",
    # Retinol
    "Retinol": "retinol",
    # Toners
    "Toners": "toner",
    "Toners & Astringents": "toner",
    "Astringents": "toner",
    "Essence": "toner",
    # Mists
    "Mists": "mist",
    "Spray Moisturizer": "mist",
    "Spray Moisturizers": "mist",
    # Oils
    "Oils": "face_oil",
    # Gels
    "Facial Gels": "gel",
    # Moisturizers
    "Emulsions": "moisturizer",
    "Daytime Moisturizers": "moisturizer",
    "Nighttime Moisturizers": "moisturizer",
    "Moisturizers": "moisturizer",
    "Tinted Moisturizers": "tinted_moisturizer",
    "Moisturizers with SPF": "sunscreen",
    # Anti-aging
    "Anti-Aging": "anti_aging",
    "Anti-Aging/Anti-Wrinkle": "anti_aging",
    "Anti-Aging/Anti-Wrinkle (RX)": "anti_aging",
    "Anti-Wrinkle": "anti_aging",
    "Anti-Wrinkle Treatments": "anti_aging",
    "Firming Treatments": "anti_aging",
    # Treatments
    "Dark Spot Corrector & Pigment Corrector": "spot_treatment",
    "Spot Treatments": "spot_treatment",
    "Skin Lightening": "spot_treatment",
    "Acne Care (OTC)": "acne_treatment",
    "Pore Treatments": "pore_treatment",
    "Pore Refining": "pore_treatment",
    "Pore Strips": "pore_treatment",
    "Lash & Brow Growth": "lash_brow",
    # Body
    "Body": "body_care",
    "Lotions": "body_care",
    "Butters": "body_care",
    "Body Wipes": "body_care",
    "Stretch Marks": "body_care",
    "Ethnic Creams, Lotions & Oils": "body_care",
    "Balms": "balm",
    "Balms, Ointments & Salves": "balm",
    "OIntments": "balm",
}

# Keyword fallback — used when category is missing or not in the mapping.
PRODUCT_TYPE_PATTERNS = {
    "eye_treatment": [
        "eye cream",
        "eye gel",
        "eye serum",
        "eye oil",
        "eye lift",
        "eye mask",
        "eye treatment",
        "eye complex",
        "eye repair",
        "dark circle",
        "depuff",
        "de-puff",
        "under eye",
        "undereye",
    ],
    "lip_treatment": [
        "lip balm",
        "lip mask",
        "lip oil",
        "lip gloss",
        "lip care",
        "lip serum",
        "lip butter",
        "lip treatment",
    ],
    "hand_care": [
        "hand cream",
        "hand butter",
        "hand lotion",
        "hand mask",
        "hand treatment",
    ],
    "foot_care": ["foot cream", "foot mask", "foot balm", "heel cream"],
    "neck_care": ["neck cream", "neck serum", "décolleté", "decolletage"],
    "body_care": [
        "body cream",
        "body lotion",
        "body butter",
        "body oil",
        "body wash",
        "body treatment",
    ],
    "cleanser": [
        "cleanser",
        "face wash",
        "cleansing milk",
        "micellar",
        "cleansing water",
        "cleansing foam",
    ],
    "serum": ["serum", "ampoule", "booster", "concentrate"],
    "sunscreen": ["spf", "sunscreen", "sun screen", "sun protection"],
    "mask": [
        "sheet mask",
        "face mask",
        "facial mask",
        "sleeping mask",
        "overnight mask",
        "mud mask",
        "clay mask",
        "peel off mask",
        "masque",
        "treatment mask",
    ],
    "toner": ["toner", "essence", "lotion toner"],
    "peel": [
        "peel",
        "exfoliant",
        "aha",
        "bha",
        "lactic acid",
        "glycolic acid",
        "salicylic acid",
    ],
    "retinol": ["retinol", "retinoid", "retin-a", "tretinoin"],
    "face_oil": ["face oil", "facial oil", "dry oil"],
    "spot_treatment": [
        "spot treatment",
        "blemish treatment",
        "acne treatment",
        "dark spot",
    ],
    "mist": ["face mist", "facial mist", "setting spray", "toning mist"],
}


def infer_product_subtype(product_name: str, category: str = None):
    """Infer product subtype using category label as primary signal.

    Category mapping is always checked first — if the category has an explicit
    mapping it is used directly. Keyword matching on the product name is only
    used when the category is missing or not in the mapping.
    """
    # Primary: use category mapping directly
    if category:
        subtype = CATEGORY_TO_SUBTYPE.get(category)
        if subtype:
            return subtype

    # Fallback: keyword match on product name
    name = str(product_name).lower()
    for subtype, keywords in PRODUCT_TYPE_PATTERNS.items():
        if any(kw in name for kw in keywords):
            return subtype

    return None


# ---------------------------
# Load artifacts
# ---------------------------
def load_artifacts():
    _ensure_core_artifacts()

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

    if faiss is None:
        faiss_index = None
        _notify("FAISS is not installed; using brute-force dupe candidate retrieval.")
    else:
        faiss_index = _load_or_rebuild_faiss_index(vectors)

    return vectors, product_index, feature_schema, metadata, faiss_index


_LOAD_ERROR: Optional[Exception] = None

try:
    VECTORS, PRODUCT_INDEX, FEATURE_SCHEMA, METADATA, FAISS_INDEX = load_artifacts()
except (FileNotFoundError, RuntimeError) as e:
    _LOAD_ERROR = e
    _notify(f"Could not load artifacts: {e}. Running in degraded mode.")

    VECTORS = None
    PRODUCT_INDEX = {}
    FEATURE_SCHEMA = None
    FAISS_INDEX = None
    METADATA = pd.DataFrame(
        columns=["product_id", "product_name", "brand", "category", "price"]
    )

INDEX_TO_ID = {v: k for k, v in PRODUCT_INDEX.items()}
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


def _bruteforce_candidates(source_id: str, k: int = FAISS_RETRIEVAL_K) -> list:
    """Return up to k nearest product IDs via cosine similarity without FAISS."""
    source_idx = PRODUCT_INDEX[source_id]
    source_vec = VECTORS[source_idx].astype(np.float32)
    all_vecs = VECTORS.astype(np.float32)

    source_norm = float(np.linalg.norm(source_vec)) + 1e-9
    all_norms = np.linalg.norm(all_vecs, axis=1) + 1e-9
    sims = (all_vecs @ source_vec) / (all_norms * source_norm)

    ranked_indices = np.argsort(sims)[::-1]
    candidate_ids = []
    for idx in ranked_indices:
        product_id = INDEX_TO_ID.get(int(idx))
        if product_id is None or product_id == source_id:
            continue
        candidate_ids.append(product_id)
        if len(candidate_ids) >= k:
            break

    return candidate_ids


# ---------------------------
# Main dupe finder
# ---------------------------
def find_dupes(product_id, top_n=5, max_price=None, weights=None, explain=True):
    if SCORER is None:
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

    source_row = METADATA[METADATA["product_id"] == product_id].iloc[0]
    source_category = source_row["category"]
    source_price = source_row["price"]
    source_subtype = infer_product_subtype(source_row["product_name"], source_category)

    # --- Retrieval: FAISS ANN when available, brute-force cosine otherwise ---
    if FAISS_INDEX is not None:
        candidate_ids = _faiss_candidates(product_id, k=FAISS_RETRIEVAL_K)
    else:
        candidate_ids = _bruteforce_candidates(product_id, k=FAISS_RETRIEVAL_K)

    # --- Filtering ---
    candidates = METADATA[METADATA["product_id"].isin(candidate_ids)].copy()

    # Must be same category and cheaper
    candidates = candidates[
        (candidates["category"] == source_category)
        & (candidates["price"] < source_price)
    ]

    # Subtype filter — category-first with keyword fallback
    if source_subtype is not None:
        filtered = candidates[
            candidates.apply(
                lambda row: (
                    infer_product_subtype(row["product_name"], row["category"])
                    == source_subtype
                ),
                axis=1,
            )
        ].copy()

        if not filtered.empty:
            candidates = filtered

    if max_price is not None:
        candidates = candidates[candidates["price"] <= max_price]

    if candidates.empty:
        return pd.DataFrame(
            columns=[
                "product_id",
                "product_name",
                "brand",
                "category",
                "price",
                "dupe_score",
                "cosine_sim",
                "price_score",
                "ingredient_group_score",
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
    results = results[
        [
            "product_id",
            "product_name",
            "brand",
            "category",
            "price",
            "dupe_score",
            "cosine_sim",
            "price_score",
            "ingredient_group_score",
        ]
    ]

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
    demo_id = next(iter(PRODUCT_INDEX))
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
