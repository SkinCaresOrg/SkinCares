import json
from pathlib import Path

import numpy as np
import pandas as pd

from .dupe_scorer import DupeScorer
from .dupe_explainer import explain_dupe


ROOT = Path(__file__).resolve().parent.parent.parent

VECTORS_PATH = ROOT / "artifacts" / "product_vectors.npy"
INDEX_PATH = ROOT / "artifacts" / "product_index.json"
SCHEMA_PATH = ROOT / "artifacts" / "feature_schema.json"
METADATA_PATH = ROOT / "data" / "processed" / "products_dataset_clean_tokens.csv"


def load_artifacts():
    vectors = np.load(VECTORS_PATH)

    with open(INDEX_PATH) as f:
        product_index = json.load(f)

    with open(SCHEMA_PATH) as f:
        feature_schema = json.load(f)

    metadata = pd.read_csv(METADATA_PATH)

    # Normalize column names to lowercase
    metadata.columns = metadata.columns.str.lower()

    # product_id comes from the row index to match keys in product_index.json
    metadata["product_id"] = metadata.index.astype(str)

    needed = {"product_id", "brand", "price"}
    missing = needed - set(metadata.columns)
    if missing:
        raise ValueError(f"products_dataset_processed.csv missing columns: {missing}")

    # Use 'action' as category if it exists, otherwise use 'label' or 'name'
    if "action" not in metadata.columns:
        if "label" in metadata.columns:
            metadata["category"] = metadata["label"]
        elif "name" in metadata.columns:
            metadata["category"] = metadata["name"]
        else:
            metadata["category"] = "unknown"
    else:
        metadata["category"] = metadata["action"]

    metadata["price"] = pd.to_numeric(metadata["price"], errors="coerce")

    # drop rows that weren't included when the vectors were built
    metadata = metadata[metadata["product_id"].isin(product_index)].copy()
    metadata = metadata.reset_index(drop=True)

    return vectors, product_index, feature_schema, metadata


VECTORS, PRODUCT_INDEX, FEATURE_SCHEMA, METADATA = load_artifacts()

INDEX_TO_ID = {v: k for k, v in PRODUCT_INDEX.items()}

# price lookup built here so DupeScorer doesn't need to import from this module
_PRICE_LOOKUP = METADATA.set_index("product_id")["price"].to_dict()

SCORER = DupeScorer(VECTORS, PRODUCT_INDEX, FEATURE_SCHEMA, _PRICE_LOOKUP)


def find_dupes(product_id, top_n=5, max_price=None, weights=None, explain=True):
    """Find the top-N cheaper products in the same category.

    Parameters
    ----------
    product_id : str
    top_n : int
    max_price : float, optional
        Hard price ceiling. Defaults to just below the source price.
    weights : dict, optional
        Override scorer weights, e.g. {"cosine": 0.6, "price": 0.2, "ingredient_group": 0.2}.
    explain : bool
        If True, adds a plain-English explanation column to the results.
    """
    if product_id not in PRODUCT_INDEX:
        raise ValueError(f"Unknown product_id: {product_id!r}")

    source_row = METADATA[METADATA["product_id"] == product_id].iloc[0]
    source_category = source_row["category"]
    source_price = source_row["price"]

    candidates = METADATA[
        (METADATA["product_id"] != product_id)
        & (METADATA["category"] == source_category)
        & (METADATA["price"] < source_price)
    ].copy()

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
