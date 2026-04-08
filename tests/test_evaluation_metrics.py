import numpy as np
import pandas as pd
import pytest

from skincarelib.evaluation.metrics import (
    average_similarity,
    brand_diversity_ratio,
    catalog_coverage,
    category_diversity_ratio,
    constraint_compliance_rate,
    intra_list_diversity,
)
from skincarelib.ml_system.reranker import rerank_candidates


def test_constraint_compliance_rate():
    recs = pd.DataFrame(
        {
            "price": [10, 60, 30],
            "category": ["Moisturizer", "Moisturizer", "Cleanser"],
        }
    )
    rate = constraint_compliance_rate(
        recs, budget=50, allowed_categories=["Moisturizer"]
    )
    assert rate == 1 / 3


def test_category_diversity_ratio():
    recs = pd.DataFrame({"category": ["A", "A", "B", "C"]})
    assert category_diversity_ratio(recs) == 3 / 4


def test_average_similarity():
    recs = pd.DataFrame({"similarity": [0.1, 0.2, 0.3]})
    assert average_similarity(recs) == pytest.approx(0.2)


def test_intra_list_diversity_identical_vectors():
    # Two identical vectors → pairwise sim = 1.0 → diversity = 0.0
    vectors = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    product_index = {"p1": 0, "p2": 1}
    recs = pd.DataFrame({"product_id": ["p1", "p2"]})
    result = intra_list_diversity(recs, vectors, product_index)
    assert result == pytest.approx(0.0, abs=1e-5)


def test_intra_list_diversity_orthogonal_vectors():
    # Orthogonal vectors → pairwise sim = 0.0 → diversity = 1.0
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    product_index = {"p1": 0, "p2": 1}
    recs = pd.DataFrame({"product_id": ["p1", "p2"]})
    result = intra_list_diversity(recs, vectors, product_index)
    assert result == pytest.approx(1.0, abs=1e-5)


def test_intra_list_diversity_returns_none_for_single_product():
    vectors = np.array([[1.0, 0.0]], dtype=np.float32)
    product_index = {"p1": 0}
    recs = pd.DataFrame({"product_id": ["p1"]})
    assert intra_list_diversity(recs, vectors, product_index) is None


def test_intra_list_diversity_returns_none_for_empty():
    vectors = np.array([[1.0, 0.0]], dtype=np.float32)
    product_index = {"p1": 0}
    recs = pd.DataFrame({"product_id": []})
    assert intra_list_diversity(recs, vectors, product_index) is None


def test_brand_diversity_ratio_all_different():
    recs = pd.DataFrame({"brand": ["A", "B", "C", "D"]})
    assert brand_diversity_ratio(recs) == pytest.approx(1.0)


def test_brand_diversity_ratio_all_same():
    recs = pd.DataFrame({"brand": ["La Mer", "La Mer", "La Mer"]})
    assert brand_diversity_ratio(recs) == pytest.approx(1 / 3)


def test_brand_diversity_ratio_missing_column():
    recs = pd.DataFrame({"product_id": ["p1", "p2"]})
    assert brand_diversity_ratio(recs) is None


def test_brand_diversity_ratio_empty():
    recs = pd.DataFrame({"brand": []})
    assert brand_diversity_ratio(recs) is None


def test_catalog_coverage_full():
    assert catalog_coverage(["p1", "p2", "p3"], total_catalog_size=3) == pytest.approx(
        1.0
    )


def test_catalog_coverage_partial():
    assert catalog_coverage(["p1", "p2"], total_catalog_size=10) == pytest.approx(0.2)


def test_catalog_coverage_deduplicates():
    # Same product recommended to multiple users only counts once
    assert catalog_coverage(["p1", "p1", "p2"], total_catalog_size=10) == pytest.approx(
        0.2
    )


def test_catalog_coverage_zero_catalog():
    assert catalog_coverage(["p1"], total_catalog_size=0) == pytest.approx(0.0)


def test_mmr_changes_ranking_vs_pure_relevance():
    # user_vector tilted slightly toward y so p3 has a tiny relevance edge over p2 post-MMR.
    # p1 and p2 are identical (both point to x) → p2 adds nothing new after p1 is selected.
    # p3 points to y → zero similarity to p1, so MMR diversity penalty is 0.
    #
    # Pure relevance (lambda=1.0): p1, p2, p3  (sorted by cos sim to user)
    # MMR (lambda=0.5) rank-2 scores after selecting p1:
    #   p2: 0.5 * rel(p2) - 0.5 * sim(p2, p1) = 0.5*1 - 0.5*1 = 0.0
    #   p3: 0.5 * rel(p3) - 0.5 * sim(p3, p1) = 0.5*ε - 0.5*0 = +ε  → p3 wins
    vectors = np.array(
        [
            [1.0, 0.0],  # p1 — highest relevance, points along user direction
            [1.0, 0.0],  # p2 — identical to p1, fully redundant
            [0.0, 1.0],  # p3 — orthogonal to p1, low but non-zero relevance
        ],
        dtype=np.float32,
    )
    product_index = {"p1": 0, "p2": 1, "p3": 2}
    # Small y-component gives p3 a non-zero relevance score to break the MMR tie
    user_vector = np.array([1.0, 0.01], dtype=np.float32)

    pure_relevance = rerank_candidates(
        user_vector,
        ["p1", "p2", "p3"],
        vectors,
        product_index,
        top_n=3,
        lambda_mult=1.0,
    )
    mmr_ranking = rerank_candidates(
        user_vector,
        ["p1", "p2", "p3"],
        vectors,
        product_index,
        top_n=3,
        lambda_mult=0.5,
    )

    # Pure relevance: p1 and p2 tied at top, p3 last
    assert pure_relevance[0] in ("p1", "p2")
    assert pure_relevance[2] == "p3"
    # MMR: first pick unchanged; p3 beats the redundant p2 at rank 2
    assert mmr_ranking[0] in ("p1", "p2")
    assert mmr_ranking[1] == "p3"
