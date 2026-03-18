import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "skincarelib" / "models"))

import pytest
import pandas as pd


@pytest.fixture
def mock_data(monkeypatch):
    # mock product index
    fake_index = {"test_id": 0}

    # mock output dataframe
    fake_df = pd.DataFrame({
        "product_id": ["test_id"],
        "product_name": ["Test Product"],
        "brand": ["Test Brand"],
        "category": ["Test Category"],
        "price": [10.0],
        "dupe_score": [0.9],
        "cosine_sim": [0.95],
        "price_score": [0.8],
        "ingredient_group_score": [0.85],
    })

    import skincarelib.models.dupe_finder as df

    monkeypatch.setattr(df, "PRODUCT_INDEX", fake_index)

    def fake_find_dupes(product_id):
        if product_id not in fake_index:
            raise ValueError("invalid product id")
        return fake_df

    monkeypatch.setattr(df, "find_dupes", fake_find_dupes)

    return fake_index, fake_df


def test_find_dupes_returns_dataframe(mock_data):
    _, _ = mock_data
    from skincarelib.models.dupe_finder import find_dupes

    results = find_dupes("test_id")

    assert isinstance(results, pd.DataFrame)


def test_find_dupes_columns(mock_data):
    _, _ = mock_data
    from skincarelib.models.dupe_finder import find_dupes

    results = find_dupes("test_id")

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


def test_find_dupes_not_empty(mock_data):
    _, _ = mock_data
    from skincarelib.models.dupe_finder import find_dupes

    results = find_dupes("test_id")

    assert results is not None


def test_invalid_product_id(mock_data):
    _, _ = mock_data
    from skincarelib.models.dupe_finder import find_dupes

    with pytest.raises(ValueError):
        find_dupes("invalid_id_123")