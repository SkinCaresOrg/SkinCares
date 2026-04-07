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
