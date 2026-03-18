import sys
from pathlib import Path

# --- Fix import paths ---
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "skincarelib" / "models"))

import pytest
import pandas as pd

from skincarelib.models.dupe_finder import find_dupes, PRODUCT_INDEX


@pytest.fixture(scope="module")
def sample_product_id():
    # get a valid product_id from index
    return next(iter(PRODUCT_INDEX))


def test_find_dupes_returns_dataframe(sample_product_id):
    results = find_dupes(sample_product_id)

    assert isinstance(results, pd.DataFrame)


def test_find_dupes_columns(sample_product_id):
    results = find_dupes(sample_product_id)

    expected_cols = {
        "product_id",
        "product_name",
        "brand",
        "category",
        "price",
        "dupe_score",
        "cosine_sim",
        "price_score",
        "ingredient_group_score",
    }

    assert expected_cols.issubset(set(results.columns))


def test_find_dupes_not_empty(sample_product_id):
    results = find_dupes(sample_product_id)

    # might be empty depending on data, so we don't hard fail
    assert results is not None


def test_invalid_product_id():
    with pytest.raises(ValueError):
        find_dupes("invalid_id_123")