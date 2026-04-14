from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from skincarelib.evaluation.metrics import catalog_coverage, summarize_metrics
from skincarelib.ml_system.artifacts import find_project_root
from skincarelib.models.recommender_ranker import load_artifacts, rank_products
from skincarelib.models.user_profile import build_user_vector


@dataclass(frozen=True)
class EvaluationScenario:
    name: str
    liked_product_ids: List[str]
    explicit_prefs: Dict[str, object]
    constraints: Dict[str, object]
    top_n: int = 10


def ndcg_at_k(
    recs: pd.DataFrame, relevant_ids: List[str], k: int = 10
) -> Optional[float]:
    """
    Normalized Discounted Cumulative Gain at K.

    Measures ranking quality — a relevant product at rank 1 is worth more
    than the same product at rank 5. Here relevance = 1 if the product was
    in the liked set, 0 otherwise.

    Returns a score in [0, 1] where 1 = perfect ranking.
    Returns None if there are no relevant products to judge against.
    """
    if not relevant_ids or recs.empty:
        return None

    relevant_set = set(str(pid) for pid in relevant_ids)
    rec_ids = recs["product_id"].astype(str).tolist()[:k]

    dcg = sum(
        1.0 / np.log2(rank + 2)
        for rank, pid in enumerate(rec_ids)
        if pid in relevant_set
    )

    # Ideal DCG: all relevant items ranked first
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / np.log2(rank + 2) for rank in range(ideal_hits))

    if idcg == 0:
        return None
    return float(dcg / idcg)


def run_scenario(
    scenario: EvaluationScenario,
    vectors: np.ndarray,
    product_index: Dict[str, int],
    metadata_df: pd.DataFrame,
    tokens_df: Optional[pd.DataFrame] = None,
) -> Dict[str, object]:
    user_vector = build_user_vector(
        scenario.liked_product_ids,
        scenario.explicit_prefs,
        vectors,
        product_index,
    )

    recs = rank_products(
        user_vector=user_vector,
        product_vectors=vectors,
        metadata_df=metadata_df,
        constraints=scenario.constraints,
        top_n=scenario.top_n,
        tokens_df=tokens_df,
        product_index=product_index,
    )

    budget = scenario.constraints.get("budget") if scenario.constraints else None
    categories = (
        scenario.constraints.get("categories") if scenario.constraints else None
    )

    metrics = summarize_metrics(
        recs,
        budget=budget,
        allowed_categories=categories,
        product_vectors=vectors,
        product_index=product_index,
    )

    # Use liked_product_ids as holdout only when they aren't excluded from results.
    # If constraints["liked_product_ids"] overlaps with liked_product_ids, those
    # products are filtered out of recs and nDCG would always be 0 — not useful.
    excluded = set(scenario.constraints.get("liked_product_ids") or [])
    holdout = [pid for pid in scenario.liked_product_ids if pid not in excluded]
    ndcg = ndcg_at_k(recs, relevant_ids=holdout, k=scenario.top_n)

    return {
        "scenario": scenario.name,
        "top_n": scenario.top_n,
        "n_recs_returned": len(recs),
        "recommended_ids": recs["product_id"].astype(str).tolist(),
        "metrics": {**metrics.to_dict(), "ndcg_at_k": ndcg},
    }


def default_scenarios(
    product_index: Dict[str, int], metadata_df: pd.DataFrame
) -> List[EvaluationScenario]:
    # Pick sample product IDs from actual indexed products
    indexed = metadata_df[metadata_df["product_id"].isin(product_index.keys())]
    creams = indexed[indexed["category"] == "Creams"]["product_id"].tolist()
    serums = indexed[indexed["category"] == "Serums"]["product_id"].tolist()
    budget_products = indexed[indexed["price"] <= 30]["product_id"].tolist()

    return [
        EvaluationScenario(
            name="cold_start_no_feedback",
            liked_product_ids=[],
            explicit_prefs={"skin_type": "dry"},
            constraints={
                "budget": None,
                "categories": None,
                "banned_ingredients": [],
                "liked_product_ids": [],
            },
            top_n=10,
        ),
        EvaluationScenario(
            name="dry_skin_creams_budget",
            liked_product_ids=creams[:2] if len(creams) >= 2 else [],
            explicit_prefs={"skin_type": "dry", "budget": 50.0},
            constraints={
                "budget": 50.0,
                "categories": ["Creams"],
                "banned_ingredients": [],
                "liked_product_ids": creams[:2],
            },
            top_n=10,
        ),
        EvaluationScenario(
            name="oily_skin_serums",
            liked_product_ids=serums[:2] if len(serums) >= 2 else [],
            explicit_prefs={"skin_type": "oily"},
            constraints={
                "budget": None,
                "categories": ["Serums"],
                "banned_ingredients": [],
                "liked_product_ids": serums[:2],
            },
            top_n=10,
        ),
        EvaluationScenario(
            name="sensitive_skin_low_budget",
            liked_product_ids=budget_products[:2] if len(budget_products) >= 2 else [],
            explicit_prefs={"skin_type": "sensitive", "budget": 30.0},
            constraints={
                "budget": 30.0,
                "categories": None,
                "banned_ingredients": ["fragrance", "alcohol"],
                "liked_product_ids": budget_products[:2],
            },
            top_n=10,
        ),
        EvaluationScenario(
            name="no_constraints_broad",
            liked_product_ids=creams[:1] + serums[:1] if creams and serums else [],
            explicit_prefs={"skin_type": "combination"},
            constraints={
                "budget": None,
                "categories": None,
                "banned_ingredients": [],
                "liked_product_ids": [],
            },
            top_n=10,
        ),
    ]


def run_all(scenarios: Optional[List[EvaluationScenario]] = None) -> Dict[str, object]:
    vectors, product_index, metadata_df = load_artifacts()

    if scenarios is None:
        scenarios = default_scenarios(product_index, metadata_df)

    # Build tokens_df once for banned-ingredient filtering across all scenarios.
    token_col = (
        "ingredient_tokens_clean"
        if "ingredient_tokens_clean" in metadata_df.columns
        else "ingredient_tokens"
    )
    tokens_df = (
        metadata_df[["product_id", token_col]].rename(
            columns={token_col: "ingredient_tokens"}
        )
        if token_col in metadata_df.columns
        else None
    )

    results = [
        run_scenario(s, vectors, product_index, metadata_df, tokens_df)
        for s in scenarios
    ]

    # Catalog coverage aggregated across all scenarios
    all_recommended = [pid for r in results for pid in r["recommended_ids"]]
    total_catalog = len(product_index)
    coverage = catalog_coverage(all_recommended, total_catalog)

    return {
        "n_scenarios": len(results),
        "catalog_size": total_catalog,
        "catalog_coverage_across_scenarios": round(coverage, 4),
        "scenarios": results,
    }


def write_report(path: Path, report: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def main() -> None:
    root = find_project_root()
    report = run_all()
    output_path = root / "artifacts" / "evaluation_report.json"
    write_report(output_path, report)

    print(f"\n{'=' * 55}")
    print(f"EVALUATION BASELINE — {report['n_scenarios']} scenarios")
    print(f"Catalog: {report['catalog_size']} products")
    print(
        f"Catalog coverage across scenarios: {report['catalog_coverage_across_scenarios']:.1%}"
    )
    print(f"{'=' * 55}")
    for s in report["scenarios"]:
        m = s["metrics"]
        print(f"\n[{s['scenario']}]")
        print(f"  returned:          {s['n_recs_returned']}/{s['top_n']}")
        print(f"  constraint_compliance: {m['constraint_compliance']:.2f}")
        print(f"  category_diversity:    {m['category_diversity']:.2f}")
        print(
            f"  avg_similarity:        {m['avg_similarity']:.4f}"
            if m["avg_similarity"] is not None
            else "  avg_similarity:        N/A"
        )
        print(
            f"  intra_list_diversity:  {m['intra_list_diversity']:.4f}"
            if m["intra_list_diversity"] is not None
            else "  intra_list_diversity:  N/A"
        )
        print(
            f"  brand_diversity:       {m['brand_diversity']:.4f}"
            if m["brand_diversity"] is not None
            else "  brand_diversity:       N/A"
        )
        print(
            f"  ndcg@{s['top_n']}:             {m['ndcg_at_k']:.4f}"
            if m["ndcg_at_k"] is not None
            else f"  ndcg@{s['top_n']}:             N/A (no holdout)"
        )
    print(f"\nWrote report: {output_path}")


if __name__ == "__main__":
    main()
