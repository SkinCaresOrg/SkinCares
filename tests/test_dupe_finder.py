import builtins
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "skincarelib" / "models"))

import importlib

import numpy as np
import pandas as pd
import pytest

faiss = pytest.importorskip("faiss", reason="faiss not installed")


@pytest.fixture
def dupe_module(monkeypatch):
    # Two products: source "0" at $20, cheaper candidate "1" at $10
    # Both in the same category so find_dupes actually has candidates to score
    fake_vectors = np.array([[1, 0], [0.9, 0.1]], dtype=np.float32)
    fake_index = {"0": 0, "1": 1}
    fake_schema = {}

    fake_metadata = pd.DataFrame(
        {
            "product_id": ["0", "1"],
            "product_name": ["Expensive Serum", "Cheap Serum"],
            "brand": ["Brand A", "Brand B"],
            "category": ["serum", "serum"],
            "price": [20.0, 10.0],
        }
    )

    # Build a real minimal FAISS index to avoid file I/O entirely
    fake_faiss_index = faiss.IndexFlatIP(2)
    normalized = fake_vectors.copy()
    faiss.normalize_L2(normalized)
    fake_faiss_index.add(normalized)

    artifact_filenames = {
        "product_vectors.npy",
        "product_index.json",
        "feature_schema.json",
        "products_with_signals.csv",
        "faiss.index",
    }

    original_exists = Path.exists

    def fake_exists(path_obj):
        if path_obj.name in artifact_filenames:
            return True
        return original_exists(path_obj)

    def fake_open(path, *args, **kwargs):
        path_str = str(path)
        if path_str.endswith("product_index.json") or path_str.endswith(
            "feature_schema.json"
        ):
            stream = io.StringIO("{}")
            stream.name = path_str
            return stream
        return builtins.open(path, *args, **kwargs)

    monkeypatch.setattr("pandas.read_csv", lambda *args, **kwargs: fake_metadata)
    monkeypatch.setattr("numpy.load", lambda *args, **kwargs: fake_vectors)
    monkeypatch.setattr(
        "json.load", lambda f: fake_index if "index" in str(f.name) else fake_schema
    )
    monkeypatch.setattr("faiss.read_index", lambda *args, **kwargs: fake_faiss_index)
    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr("builtins.open", fake_open)

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
    assert len(results) > 0


def test_invalid_product_id(dupe_module):
    with pytest.raises(ValueError):
        dupe_module.find_dupes("invalid_id_123")
