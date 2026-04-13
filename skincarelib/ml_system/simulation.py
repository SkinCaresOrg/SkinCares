from __future__ import annotations

import argparse
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np

from skincarelib.ml_system.artifacts import load_artifacts, find_project_root
from skincarelib.ml_system.feedback_update import (
    UserState,
    update_user_state,
    compute_user_vector,
    create_feedback_model,
)
from skincarelib.ml_system.reranker import rerank_candidates
from skincarelib.models.recommender_ranker import rank_products


def load_metadata(root) -> pd.DataFrame:
    path = root / "data" / "processed" / "products_dataset_processed.csv"
    df = pd.read_csv(path, dtype={"product_id": str})

    # Add product_id if not present
    if "product_id" not in df.columns:
        df.insert(0, "product_id", df.index.astype(str))

    # Ensure product_id is string
    df["product_id"] = df["product_id"].astype(str)

    for col in ["brand", "category", "price"]:
        if col not in df.columns:
            df[col] = ""

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df


def load_tokens(root) -> pd.DataFrame:
    path = root / "data" / "processed" / "products_tokens.csv"
    if not path.exists():
        return pd.DataFrame(columns=["product_id", "ingredient_tokens"])
    df = pd.read_csv(path)
    df["product_id"] = df["product_id"].astype(str)
    return df


def format_product(pid: str, meta_indexed: pd.DataFrame) -> str:
    pid = str(pid)
    if pid not in meta_indexed.index:
        return f"{pid} | (metadata missing)"
    row = meta_indexed.loc[pid]
    price = row.get("price", None)
    price_str = f"${price:.2f}" if pd.notna(price) else "NA"
    return f"{pid} | {row.get('brand', '')} | {row.get('category', '')} | {price_str}"


def pretty_list(product_ids: List[str], meta_indexed: pd.DataFrame, n: int = 10) -> str:
    return "\n".join(
        [
            f"{i:>2}. {format_product(pid, meta_indexed)}"
            for i, pid in enumerate(product_ids[:n], start=1)
        ]
    )


def run_simulation(
    top_n: int = 10,
    candidate_k: int = 200,
    budget: Optional[float] = 100.0,
    categories: Optional[List[str]] = None,
    model_type: str = "weighted_avg",
):
    # ---- Load artifacts ----
    product_vectors, product_index, _, schema = load_artifacts()
    dim = product_vectors.shape[1]

    root = find_project_root()
    meta = load_metadata(root)
    tokens_df = load_tokens(root)

    # Index for pretty printing
    meta_idx = meta.copy()
    meta_idx["product_id"] = meta_idx["product_id"].astype(str)
    meta_idx = meta_idx.set_index("product_id", drop=False)

    print(
        f"Loaded vectors: {product_vectors.shape} (products={product_vectors.shape[0]}, dim={dim})"
    )
    print(f"Using model: {model_type}")

    # ---- Initialize user ----
    user = UserState(dim=dim)

    # ---- Constraints for ranker ----
    constraints: Dict[str, Any] = {}
    if budget is not None:
        constraints["budget"] = float(budget)
    if categories:
        constraints["categories"] = categories
    constraints["banned_ingredients"] = []
    constraints["liked_product_ids"] = []

    # ---- Build user vector (cold start) and get candidate pool ----
    user_vec_before = compute_user_vector(user, schema=schema)

    candidates_df = rank_products(
        user_vector=user_vec_before,
        product_vectors=product_vectors,
        metadata_df=meta,
        constraints=constraints,
        top_n=candidate_k,
        tokens_df=tokens_df,
        product_index=product_index,
    )

    if candidates_df.empty:
        print("No candidates returned from ranker. Try loosening constraints.")
        return

    candidate_ids = candidates_df["product_id"].astype(str).tolist()
    print(f"\nCandidate pool size: {len(candidate_ids)} (rank_products)")
    print(f"Constraints: {constraints}")

    # ---- BEFORE feedback: rerank candidate pool ----
    if model_type == "weighted_avg":
        user_vec = user_vec_before
        ranked_before = rerank_candidates(
            user_vector=user_vec,
            candidate_ids=candidate_ids,
            product_vectors=product_vectors,
            product_index=product_index,
            top_n=top_n,
        )
    else:
        # Cold start: use weighted average for initial ranking
        ranked_before = rerank_candidates(
            user_vector=user_vec_before,
            candidate_ids=candidate_ids,
            product_vectors=product_vectors,
            product_index=product_index,
            top_n=top_n,
        )

    print("\n=== BEFORE FEEDBACK ===")
    print(pretty_list(ranked_before, meta_idx, n=top_n))

    # ---- Interaction plan (edit to match your UX reasons) ----
    interaction_plan = [
        ("like", candidate_ids[0], ["hydrated_well"]),
        ("like", candidate_ids[3], ["absorbed_quickly"]),
        ("dislike", candidate_ids[10], ["too_greasy"]),
        ("irritation", candidate_ids[15], ["irritated_my_skin"]),
        ("like", candidate_ids[25], ["good_price_to_quality"]),
    ]

    print("\nApplied interactions:")
    for reaction, pid, reasons in interaction_plan:
        print(
            f"  - {reaction.upper():<10} {format_product(pid, meta_idx)} | reasons={reasons}"
        )

    # ---- Apply interactions ----
    for reaction, pid, reasons in interaction_plan:
        pid = str(pid)
        if pid not in product_index:
            continue
        vec = product_vectors[product_index[pid]]
        update_user_state(user, reaction, vec, reason_tags=reasons)

    # ---- AFTER feedback: rerank with selected model ----
    if model_type == "weighted_avg":
        user_vec_after = compute_user_vector(user, schema=schema)
        ranked_after = rerank_candidates(
            user_vector=user_vec_after,
            candidate_ids=candidate_ids,
            product_vectors=product_vectors,
            product_index=product_index,
            top_n=top_n,
        )
    else:
        # Train ML model
        model = create_feedback_model(model_type=model_type, dim=dim)
        if model.fit(user):
            # Score candidates with ML model
            candidate_indices = []
            valid_candidate_ids = []
            for pid in candidate_ids:
                if pid in product_index:
                    candidate_indices.append(product_index[pid])
                    valid_candidate_ids.append(pid)
            candidate_vectors = product_vectors[candidate_indices]
            scores = model.score_products(candidate_vectors)

            # Create mapping from valid candidate IDs to their scores and sort
            pid_to_score = dict(zip(valid_candidate_ids, scores))
            ranked_after = sorted(
                valid_candidate_ids,
                key=lambda pid: pid_to_score.get(pid, 0),
                reverse=True,
            )[:top_n]
        else:
            ranked_after = ranked_before

    # ---- Exclude liked products from AFTER recommendations ----
    liked_ids = {
        str(pid) for reaction, pid, _ in interaction_plan if reaction.lower() == "like"
    }

    ranked_after = [pid for pid in ranked_after if str(pid) not in liked_ids][:top_n]

    print("\n=== AFTER FEEDBACK ===")
    print(pretty_list(ranked_after, meta_idx, n=top_n))

    overlap = len(set(ranked_before) & set(ranked_after))
    print(f"\nTop-{top_n} overlap BEFORE vs AFTER: {overlap}/{top_n}")

    print("\nUser state summary:")
    print(f"  interactions: {user.interactions}")
    print(f"  liked count:  {len(user.liked_vectors)}")
    print(f"  disliked count: {len(user.disliked_vectors)}")

    # Model-specific info
    if (
        model_type != "weighted_avg"
        and hasattr(model, "is_trained")
        and model.is_trained
    ):
        if hasattr(model, "get_feature_importance"):
            imp = model.get_feature_importance()
            if len(imp) > 0:
                print("\nTop feature importances:")
                top_indices = np.argsort(imp)[-5:][::-1]
                for idx in top_indices:
                    print(f"  Feature {idx}: {imp[idx]:.4f}")


def run_model_comparison(
    top_n: int = 10,
    candidate_k: int = 200,
    budget: Optional[float] = 100.0,
    categories: Optional[List[str]] = None,
):
    """Compare different feedback models on the same interaction sequence."""

    # ---- Load artifacts ----
    product_vectors, product_index, _, schema = load_artifacts()
    dim = product_vectors.shape[1]

    root = find_project_root()
    meta = load_metadata(root)
    tokens_df = load_tokens(root)

    meta_idx = meta.copy()
    meta_idx["product_id"] = meta_idx["product_id"].astype(str)
    meta_idx = meta_idx.set_index("product_id", drop=False)

    print(f"Loaded vectors: {product_vectors.shape}")
    print("Comparing ML models...\n")

    # ---- Setup constraints ----
    constraints: Dict[str, Any] = {}
    if budget is not None:
        constraints["budget"] = float(budget)
    if categories:
        constraints["categories"] = categories
    constraints["banned_ingredients"] = []
    constraints["liked_product_ids"] = []

    # ---- Get candidate pool ----
    user_vec_before = np.zeros(dim, dtype=np.float32)
    candidates_df = rank_products(
        user_vector=user_vec_before,
        product_vectors=product_vectors,
        metadata_df=meta,
        constraints=constraints,
        top_n=candidate_k,
        tokens_df=tokens_df,
        product_index=product_index,
    )

    if candidates_df.empty:
        print("No candidates. Loosening constraints...")
        return

    candidate_ids = candidates_df["product_id"].astype(str).tolist()

    # ---- Fixed interaction sequence ----
    # Define desired interactions by candidate index, then filter based on availability.
    base_interactions = [
        ("like", 0, ["hydrated_well"]),
        ("like", 3, ["absorbed_quickly"]),
        ("dislike", 10, ["too_greasy"]),
        ("irritation", 15, ["irritated_my_skin"]),
        ("like", 25, ["good_price_to_quality"]),
    ]

    interaction_plan = []
    for reaction, idx, reasons in base_interactions:
        if idx < len(candidate_ids):
            interaction_plan.append((reaction, candidate_ids[idx], reasons))

    if not interaction_plan:
        print("Not enough candidates to build interaction plan for comparison.")
        return

    print("Fixed interaction sequence:")
    for reaction, pid, reasons in interaction_plan:
        print(f"  {reaction.upper():<10} {format_product(pid, meta_idx)}")

    # ---- Test each model ----
    model_types = [
        "weighted_avg",
        "logistic",
        "random_forest",
        "gradient_boosting",
        "contextual_bandit",
    ]
    results = {}

    for model_type in model_types:
        print(f"\n{'=' * 60}")
        print(f"Model: {model_type}")
        print(f"{'=' * 60}")

        # Create fresh user state
        user = UserState(dim=dim)

        # Apply interactions
        for reaction, pid, reasons in interaction_plan:
            pid = str(pid)
            if pid not in product_index:
                continue
            vec = product_vectors[product_index[pid]]
            update_user_state(user, reaction, vec, reason_tags=reasons)

        # Get recommendations
        if model_type == "weighted_avg":
            user_vec = compute_user_vector(user, schema=schema)
            ranked = rerank_candidates(
                user_vector=user_vec,
                candidate_ids=candidate_ids,
                product_vectors=product_vectors,
                product_index=product_index,
                top_n=top_n,
            )
        elif model_type == "contextual_bandit":
            # Bandit learns incrementally, not batch training
            from skincarelib.ml_system.ml_feedback_model import ContextualBanditFeedback

            model = ContextualBanditFeedback(dim=dim)
            for vec in user.liked_vectors:
                model.update(vec, reward=1)
            for vec in user.disliked_vectors:
                model.update(vec, reward=0)

            candidate_indices = [
                product_index[pid] for pid in candidate_ids if pid in product_index
            ]
            candidate_vectors = product_vectors[candidate_indices]
            scores = model.score_products(candidate_vectors)

            pid_to_score = {
                candidate_ids[i]: scores[i] for i in range(len(candidate_ids))
            }
            ranked = sorted(
                [pid for pid in candidate_ids if pid in product_index],
                key=lambda pid: pid_to_score.get(pid, 0),
                reverse=True,
            )[:top_n]
        else:
            model = create_feedback_model(model_type=model_type, dim=dim)
            if model.fit(user):
                candidate_indices = [
                    product_index[pid] for pid in candidate_ids if pid in product_index
                ]
                candidate_vectors = product_vectors[candidate_indices]
                scores = model.score_products(candidate_vectors)

                pid_to_score = {
                    candidate_ids[i]: scores[i] for i in range(len(candidate_ids))
                }
                ranked = sorted(
                    [pid for pid in candidate_ids if pid in product_index],
                    key=lambda pid: pid_to_score.get(pid, 0),
                    reverse=True,
                )[:top_n]
            else:
                ranked = []

        results[model_type] = ranked
        print(f"\nTop {top_n} recommendations:")
        print(pretty_list(ranked, meta_idx, n=top_n))

    # Compare results
    print(f"\n{'=' * 60}")
    print("COMPARISON SUMMARY")
    print(f"{'=' * 60}")

    for i, pid in enumerate(results["weighted_avg"][:5], 1):
        print(f"\nRank {i}: {format_product(pid, meta_idx)}")
        for model_type in model_types[1:]:
            if pid in results[model_type]:
                rank = results[model_type].index(pid) + 1
                print(f"  {model_type:<20} rank: {rank}")
            else:
                print(f"  {model_type:<20} rank: N/A")


def main():
    p = argparse.ArgumentParser(
        description="Skincare recommendation with various feedback models."
    )
    p.add_argument("--top_n", type=int, default=10)
    p.add_argument("--candidate_k", type=int, default=200)
    p.add_argument("--budget", type=float, default=100.0)
    p.add_argument(
        "--categories",
        type=str,
        nargs="*",
        default=["Creams"],
        help="Allowed categories (space-separated). Examples: Creams, Serums, Lotions",
    )
    p.add_argument(
        "--model",
        type=str,
        choices=[
            "weighted_avg",
            "logistic",
            "random_forest",
            "gradient_boosting",
            "contextual_bandit",
        ],
        default="weighted_avg",
        help="Feedback model type.",
    )
    p.add_argument(
        "--compare",
        action="store_true",
        help="Compare all models instead of running single model.",
    )
    args = p.parse_args()

    cats = args.categories if args.categories else None

    if args.compare:
        run_model_comparison(
            top_n=args.top_n,
            candidate_k=args.candidate_k,
            budget=args.budget,
            categories=cats,
        )
    else:
        run_simulation(
            top_n=args.top_n,
            candidate_k=args.candidate_k,
            budget=args.budget,
            categories=cats,
            model_type=args.model,
        )


if __name__ == "__main__":
    main()
