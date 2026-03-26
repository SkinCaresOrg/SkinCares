import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def recommender_module(monkeypatch):
    vectors = np.array(
        [
            [1, 0, 0],
            [0.9, 0.1, 0],
            [0, 1, 0],
        ],
        dtype=np.float32,
    )

    product_index = {
        "p1": 0,
        "p2": 1,
        "p3": 2,
    }

    metadata = pd.DataFrame(
        {
            "product_id": ["p1", "p2", "p3"],
            "brand": ["A", "B", "C"],
            "category": ["serum", "serum", "cleanser"],
            "price": [50, 30, 20],
        }
    )

    tokens = pd.DataFrame(
        {
            "product_id": ["p1", "p2", "p3"],
            "ingredient_tokens": ["niacinamide", "niacinamide", "water"],
        }
    )

    import skincarelib.models.recommender_ranker as recommender

    monkeypatch.setattr(
        recommender,
        "load_artifacts",
        lambda: (vectors, product_index, metadata),
    )

    monkeypatch.setattr(
        recommender.pd,
        "read_csv",
        lambda *args, **kwargs: tokens,
    )

    monkeypatch.setattr(
        recommender,
        "score_similarity",
        lambda user_vec, prod_vecs, weights=None, dims_mask=None: np.array(
            [0.9] * len(prod_vecs), dtype=np.float32
        ),
    )

    return recommender


def test_recommend_returns_results(recommender_module):
    results = recommender_module.recommend(
        liked_product_ids=["p1"],
        explicit_prefs={},
        constraints={},
        top_n=2,
    )

    assert isinstance(results, pd.DataFrame)
    assert len(results) > 0


def test_recommend_respects_budget_constraint(recommender_module):
    results = recommender_module.recommend(
        liked_product_ids=["p1"],
        explicit_prefs={},
        constraints={"budget": 25},
        top_n=5,
    )

    assert all(results["price"] <= 25)


def test_recommend_excludes_liked_products(recommender_module):
    results = recommender_module.recommend(
        liked_product_ids=["p1"],
        explicit_prefs={},
        constraints={},
        top_n=5,
    )

    assert "p1" not in results["product_id"].values


def test_recommend_empty_when_no_candidates(recommender_module):
    results = recommender_module.recommend(
        liked_product_ids=["p1"],
        explicit_prefs={},
        constraints={"budget": 1},
        top_n=5,
    )

    assert results.empty
