from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine


@dataclass(frozen=True)
class EvaluationMetrics:
    constraint_compliance: float
    category_diversity: float
    avg_similarity: Optional[float]
    intra_list_diversity: Optional[float] = field(default=None)
    brand_diversity: Optional[float] = field(default=None)

    def to_dict(self) -> dict:
        return {
            "constraint_compliance": self.constraint_compliance,
            "category_diversity": self.category_diversity,
            "avg_similarity": self.avg_similarity,
            "intra_list_diversity": self.intra_list_diversity,
            "brand_diversity": self.brand_diversity,
        }


def constraint_compliance_rate(
    recs: pd.DataFrame,
    budget: Optional[float],
    allowed_categories: Optional[Iterable[str]],
) -> float:
    if recs.empty:
        return 0.0

    mask = pd.Series(True, index=recs.index)

    if budget is not None and "price" in recs.columns:
        prices = pd.to_numeric(recs["price"], errors="coerce")
        mask &= prices <= float(budget)

    if allowed_categories and "category" in recs.columns:
        allowed = set(allowed_categories)
        mask &= recs["category"].isin(allowed)

    return float(mask.mean())


def category_diversity_ratio(recs: pd.DataFrame) -> float:
    if recs.empty or "category" not in recs.columns:
        return 0.0
    return float(recs["category"].nunique() / len(recs))


def average_similarity(recs: pd.DataFrame) -> Optional[float]:
    if recs.empty or "similarity" not in recs.columns:
        return None
    sims = pd.to_numeric(recs["similarity"], errors="coerce")
    if sims.dropna().empty:
        return None
    return float(sims.mean())


def intra_list_diversity(
    recs: pd.DataFrame,
    product_vectors: np.ndarray,
    product_index: Dict[str, int],
) -> Optional[float]:
    """
    Average pairwise diversity within the recommendation list.
    Computed as 1 - mean(pairwise cosine similarity) across all pairs in top-N.
    Returns None if fewer than 2 products can be looked up in the vector index.
    Range: [0, 1] where 1 = maximally diverse, 0 = all identical.
    """
    if recs.empty:
        return None
    pids = [str(pid) for pid in recs["product_id"] if str(pid) in product_index]
    if len(pids) < 2:
        return None
    vecs = product_vectors[[product_index[pid] for pid in pids]]
    sim_matrix = sklearn_cosine(vecs)
    n = len(pids)
    upper_triangle = [sim_matrix[i, j] for i in range(n) for j in range(i + 1, n)]
    if not upper_triangle:
        return None
    mean_sim = np.nanmean(upper_triangle)
    if np.isnan(mean_sim):
        return None
    return float(1.0 - mean_sim)


def brand_diversity_ratio(recs: pd.DataFrame) -> Optional[float]:
    """
    Fraction of unique brands in the recommendation list.
    Range: [1/n, 1] where 1 = all different brands, 1/n = all same brand.
    Returns None if brand column is missing.
    """
    if recs.empty or "brand" not in recs.columns:
        return None
    return float(recs["brand"].nunique() / len(recs))


def catalog_coverage(
    all_recommended_ids: Iterable[str],
    total_catalog_size: int,
) -> float:
    """
    Fraction of the catalog that appears in recommendations across multiple users/scenarios.
    Call this after aggregating recommended product_ids from all evaluation scenarios.
    Range: [0, 1] where 1 = every product was recommended at least once.
    """
    if total_catalog_size == 0:
        return 0.0
    return float(len(set(all_recommended_ids)) / total_catalog_size)


def summarize_metrics(
    recs: pd.DataFrame,
    budget: Optional[float],
    allowed_categories: Optional[List[str]],
    product_vectors: Optional[np.ndarray] = None,
    product_index: Optional[Dict[str, int]] = None,
) -> EvaluationMetrics:
    return EvaluationMetrics(
        constraint_compliance=constraint_compliance_rate(
            recs, budget=budget, allowed_categories=allowed_categories
        ),
        category_diversity=category_diversity_ratio(recs),
        avg_similarity=average_similarity(recs),
        intra_list_diversity=(
            intra_list_diversity(recs, product_vectors, product_index)
            if product_vectors is not None and product_index is not None
            else None
        ),
        brand_diversity=brand_diversity_ratio(recs),
    )
