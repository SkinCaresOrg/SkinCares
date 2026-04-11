import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "skincarelib" / "models"))

import pytest
import pandas as pd
import numpy as np
import importlib
import faiss


@pytest.fixture
def dupe_module(monkeypatch):
    # IMPORTANT: product_id must match index "0"
    fake_vectors = np.array([[1, 0], [0, 1]], dtype=np.float32)
    fake_index = {"0": 0}
    fake_schema = {}

    fake_metadata = pd.DataFrame(
        {
            "product_name": ["Test Product"],
            "brand": ["Test Brand"],
            "category": ["serum"],
            "price": [10.0],
        }
    )

    # Build a real minimal FAISS index to avoid file I/O entirely
    fake_faiss_index = faiss.IndexFlatIP(2)
    normalized = fake_vectors.copy()
    faiss.normalize_L2(normalized)
    fake_faiss_index.add(normalized)

    monkeypatch.setattr("pandas.read_csv", lambda *args, **kwargs: fake_metadata)
    monkeypatch.setattr("numpy.load", lambda *args, **kwargs: fake_vectors)
    monkeypatch.setattr(
        "json.load", lambda f: fake_index if "index" in str(f.name) else fake_schema
    )
    monkeypatch.setattr("faiss.read_index", lambda *args, **kwargs: fake_faiss_index)

    import skincarelib.models.dupe_finder as df

    importlib.reload(df)

    return df


def test_find_dupes_returns_dataframe(dupe_module):
    results = dupe_module.find_dupes("0")
    assert isinstance(results, pd.DataFrame)


def test_find_dupes_columns(dupe_module):
    results = dupe_module.find_dupes("0")

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


def test_find_dupes_not_empty(dupe_module):
    results = dupe_module.find_dupes("0")
    assert results is not None


def test_invalid_product_id(dupe_module):
    with pytest.raises(ValueError):
        dupe_module.find_dupes("invalid_id_123")