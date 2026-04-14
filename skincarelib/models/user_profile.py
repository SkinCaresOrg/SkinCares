import json
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent

GROUPS_PATH = ROOT / "features" / "ingredient_groups.json"
TFIDF_PATH = ROOT / "artifacts" / "tfidf.joblib"
SCHEMA_PATH = ROOT / "artifacts" / "feature_schema.json"

TFIDF_START = 0
TFIDF_END = None  # set by _init_layout() from feature_schema.json
GROUPS_START = None
TOTAL_DIMS = None
PRICE_DIM = (
    None  # set by _init_layout() — always schema["price_index"], NOT TOTAL_DIMS - 1
)

_schema = None  # cached parsed schema


def _init_layout():
    global _schema, TFIDF_END, GROUPS_START, TOTAL_DIMS, PRICE_DIM
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"feature_schema.json not found at {SCHEMA_PATH}. "
            "Run models/vectorizer.py first."
        )
    with open(SCHEMA_PATH) as f:
        _schema = json.load(f)
    TFIDF_END = len(_schema["tfidf"])
    GROUPS_START = TFIDF_END
    TOTAL_DIMS = _schema["total_features"]
    PRICE_DIM = _schema["price_index"]


_init_layout()

# Skin type -> (groups to boost, groups to suppress)
SKIN_TYPE_PREFS = {
    "dry": (
        ["humectant", "emollient", "occlusive", "soothing_agent"],
        ["exfoliant", "irritant_flag"],
    ),
    "oily": (["exfoliant", "active", "ph_adjuster"], ["occlusive", "emollient"]),
    "sensitive": (
        ["soothing_agent", "humectant"],
        ["irritant_flag", "exfoliant", "active"],
    ),
    "combination": (["humectant"], ["irritant_flag"]),
    "normal": (["active", "antioxidant"], []),
}

# Skin type -> (signal dims to boost, signal dims to suppress)
# Derived from the 7-dim CosIng signal space: hydration, barrier, acne_control,
# soothing, exfoliation, antioxidant, irritation_risk
SKIN_TYPE_SIGNAL_PREFS = {
    "dry": (
        ["hydration", "barrier", "soothing"],
        ["acne_control", "exfoliation", "irritation_risk"],
    ),
    "oily": (["acne_control", "exfoliation"], ["barrier", "hydration"]),
    "sensitive": (["soothing", "barrier"], ["irritation_risk", "exfoliation"]),
    "combination": (["hydration", "acne_control"], ["irritation_risk"]),
    "normal": (["antioxidant", "hydration"], ["irritation_risk"]),
}

# Concern -> (signal dims to boost, signal dims to suppress)
CONCERN_SIGNAL_PREFS = {
    "acne": (["acne_control", "exfoliation"], ["barrier"]),
    "dryness": (["hydration", "barrier", "soothing"], ["exfoliation"]),
    "oiliness": (["acne_control", "exfoliation"], ["barrier", "hydration"]),
    "redness": (["soothing", "barrier"], ["irritation_risk", "exfoliation"]),
    "dark_spots": (["antioxidant", "exfoliation"], []),
    "fine_lines": (["antioxidant", "hydration", "barrier"], []),
    "dullness": (["antioxidant", "exfoliation"], []),
    "large_pores": (["acne_control", "exfoliation"], ["barrier"]),
    "maintenance": (["antioxidant", "hydration"], []),
}

# Sensitivity level -> irritation_risk suppress factor (0 = no change, 1 = zero out)
SENSITIVITY_SUPPRESS = {
    "very_sensitive": 0.0,  # fully suppress irritation_risk dim
    "somewhat_sensitive": 0.4,
    "rarely_sensitive": 0.7,
    "not_sensitive": 1.0,  # no change
    "not_sure": 0.7,  # conservative default
}

# ── Boost / suppress magnitudes ───────────────────────────────────────────────
# Kept as module-level constants so they're easy to tune and test in isolation.
_GROUP_BOOST_FACTOR = 0.3  # scale applied to catalog mean for group dim boost
_GROUP_SUPPRESS_FACTOR = 0.5  # multiplicative suppression for group dims

_SIGNAL_BOOST = 0.25  # additive boost for skin-type signal dims
_SIGNAL_SUPPRESS = 0.5  # multiplicative suppression for skin-type signal dims

_CONCERN_BOOST = 0.2  # additive boost per concern-aligned signal dim
_CONCERN_SUPPRESS = 0.6  # multiplicative suppression per concern-opposed dim

_INGREDIENT_BOOST = 0.15  # additive boost per preferred ingredient token
_CATEGORY_BOOST = 0.5  # additive boost per preferred category dim

# ── Module-level caches — populated lazily on first call ──────────────────────
_group_map = None  # ingredient -> group name
_group_names = None  # sorted list of unique group names
_group_dim = None  # group name -> absolute dim index
_cat_dim = None  # category name -> absolute dim index
_tfidf_vocab = None  # token -> dim index (0-511)
_signal_dim = None  # signal name -> absolute dim index


def _load_group_info():
    global _group_map, _group_names, _group_dim
    if _group_names is not None:
        return
    with open(GROUPS_PATH) as f:
        _group_map = json.load(f)
    # Filter out empty-string group names (ingredient_groups.json may be partially filled)
    _group_names = sorted(g for g in set(_group_map.values()) if g)
    _group_dim = {name: GROUPS_START + i for i, name in enumerate(_group_names)}


def _load_cat_info():
    global _cat_dim
    if _cat_dim is not None:
        return
    if _schema is not None:
        cat_names = [c.replace("cat_", "") for c in _schema["categories"]]
        cat_start = _schema["price_index"] - len(_schema["categories"])
    elif SCHEMA_PATH.exists():
        with open(SCHEMA_PATH) as f:
            s = json.load(f)
        cat_names = [c.replace("cat_", "") for c in s["categories"]]
        cat_start = s["price_index"] - len(s["categories"])
    else:
        # Alphabetical fallback matching sklearn fit order on the known label set
        cat_names = [
            "Cleanser",
            "Eye cream",
            "Face Mask",
            "Moisturizer",
            "Sun protect",
            "Treatment",
        ]
        cat_start = GROUPS_START + 1  # 1 group dim when all groups are empty
    _cat_dim = {name: cat_start + i for i, name in enumerate(cat_names)}


def _load_tfidf_vocab():
    global _tfidf_vocab
    if _tfidf_vocab is not None:
        return
    vec = joblib.load(TFIDF_PATH)
    _tfidf_vocab = vec.vocabulary_  # token -> dim index (0-511)


def _load_signal_info():
    global _signal_dim
    if _signal_dim is not None:
        return
    if _schema is not None:
        signals = _schema.get("signals", {})
    elif SCHEMA_PATH.exists():
        with open(SCHEMA_PATH) as f:
            signals = json.load(f).get("signals", {})
    else:
        signals = {}
    _signal_dim = {name: info["start"] for name, info in signals.items()}


def build_user_vector(
    liked_product_ids, explicit_prefs, product_vectors, product_index
):
    """
    Build a user preference vector from liked products and explicit preferences.

    Args:
        liked_product_ids: list[str] — product IDs the user has liked
        explicit_prefs:    dict with optional keys:
                             skin_type (str): "dry" | "oily" | "sensitive" | "combination" | "normal"
                             budget (float): max price in dollars
                             preferred_ingredients (list[str]): ingredient names to boost
                             preferred_categories (list[str]): category names to boost
                             banned_ingredients (list[str]): used downstream by ranker, not here
        product_vectors:   np.ndarray shape (N, total_features)
        product_index:     dict mapping product_id (str) -> row index (int)

    Returns:
        np.ndarray shape (total_features,), dtype float32
    """
    _load_group_info()
    _load_cat_info()
    _load_signal_info()

    # --- Step 1: Base vector from liked products ---
    valid_ids = [pid for pid in (liked_product_ids or []) if pid in product_index]
    if valid_ids:
        indices = [product_index[pid] for pid in valid_ids]
        base_vector = product_vectors[indices].mean(axis=0).astype(np.float32)
    else:
        base_vector = np.zeros(TOTAL_DIMS, dtype=np.float32)

    # --- Step 2a: Skin type -> ingredient group dim boost/suppress ---
    skin_type = (explicit_prefs.get("skin_type") or "").lower().strip()
    if skin_type in SKIN_TYPE_PREFS:
        boost_groups, suppress_groups = SKIN_TYPE_PREFS[skin_type]
        # Use catalog mean per group dim as reference magnitude for boosts
        catalog_group_mean = product_vectors[
            :, GROUPS_START : GROUPS_START + len(_group_names)
        ].mean(axis=0)
        for grp in boost_groups:
            if grp not in _group_dim:
                continue
            dim = _group_dim[grp]
            group_offset = dim - GROUPS_START
            delta = float(catalog_group_mean[group_offset]) * _GROUP_BOOST_FACTOR
            base_vector[dim] += delta
        for grp in suppress_groups:
            if grp not in _group_dim:
                continue
            base_vector[_group_dim[grp]] *= _GROUP_SUPPRESS_FACTOR

    # --- Step 2b: Skin type -> functional signal dim boost/suppress ---
    if skin_type in SKIN_TYPE_SIGNAL_PREFS and _signal_dim:
        boost_sigs, suppress_sigs = SKIN_TYPE_SIGNAL_PREFS[skin_type]
        for sig in boost_sigs:
            if sig in _signal_dim:
                base_vector[_signal_dim[sig]] += _SIGNAL_BOOST
        for sig in suppress_sigs:
            if sig in _signal_dim:
                base_vector[_signal_dim[sig]] *= _SIGNAL_SUPPRESS

    # --- Step 2c: Skin concerns -> signal dim boost/suppress ---
    concerns = explicit_prefs.get("concerns") or []
    if concerns and _signal_dim:
        for concern in concerns:
            if concern in CONCERN_SIGNAL_PREFS:
                boost_sigs, suppress_sigs = CONCERN_SIGNAL_PREFS[concern]
                for sig in boost_sigs:
                    if sig in _signal_dim:
                        base_vector[_signal_dim[sig]] += _CONCERN_BOOST
                for sig in suppress_sigs:
                    if sig in _signal_dim:
                        base_vector[_signal_dim[sig]] *= _CONCERN_SUPPRESS

    # --- Step 2d: Sensitivity level -> irritation_risk suppression ---
    sensitivity = (explicit_prefs.get("sensitivity_level") or "not_sure").lower()
    if _signal_dim and "irritation_risk" in _signal_dim:
        factor = SENSITIVITY_SUPPRESS.get(sensitivity, 0.7)
        base_vector[_signal_dim["irritation_risk"]] *= factor

    # --- Step 3: Preferred ingredients -> TF-IDF dim boost ---
    preferred_ingredients = explicit_prefs.get("preferred_ingredients") or []
    if preferred_ingredients and TFIDF_PATH.exists():
        _load_tfidf_vocab()
        for ing in preferred_ingredients:
            token = ing.lower().strip()
            if token in _tfidf_vocab:
                base_vector[_tfidf_vocab[token]] += _INGREDIENT_BOOST

    # --- Step 4: Preferred categories -> category dim boost ---
    preferred_categories = explicit_prefs.get("preferred_categories") or []
    for cat in preferred_categories:
        if cat in _cat_dim:
            base_vector[_cat_dim[cat]] += _CATEGORY_BOOST

    # --- Step 5: budget -> price dim (cold start only) ---
    budget = explicit_prefs.get("budget")
    price_dim = PRICE_DIM
    if budget is not None and not valid_ids:
        budget = float(budget)
        if budget <= 20:
            base_vector[price_dim] = 0.15
        elif budget <= 50:
            base_vector[price_dim] = 0.35
        elif budget <= 100:
            base_vector[price_dim] = 0.60
        else:
            base_vector[price_dim] = 0.85

    return base_vector
