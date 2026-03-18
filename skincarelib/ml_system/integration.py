from __future__ import annotations

from typing import Any, Dict, Literal

import pandas as pd
import numpy as np

from skincarelib.ml_system.artifacts import load_artifacts
from skincarelib.ml_system.candidate_source import get_candidates
from skincarelib.ml_system.feedback_update import (
    UserState,
    compute_user_vector,
    create_feedback_model,
)
from skincarelib.ml_system.reranker import rerank_candidates


def recommend_with_feedback(
    user_state: UserState,
    metadata_df: pd.DataFrame,
    tokens_df: pd.DataFrame,
    constraints: Dict[str, Any],
    top_n: int = 10,
    candidate_k: int = 200,
    model_type: Literal["weighted_avg", "logistic", "random_forest", "gradient_boosting", "contextual_bandit"] = "weighted_avg",
) -> pd.DataFrame:
    """
    Pipeline:
      1) candidate list from ranker (constraint-aware)
      2) rerank with user preference model (weighted average or ML-based)
      3) return ordered DataFrame
    
    Args:
        user_state: User interaction history
        metadata_df: Product metadata
        tokens_df: Product tokens
        constraints: Constraints for candidate selection
        top_n: Number of recommendations to return
        candidate_k: Size of candidate pool
        model_type: Feedback model type:
            - "weighted_avg": Legacy weighted average (default)
            - "logistic": Logistic regression
            - "random_forest": Random forest classifier
            - "gradient_boosting": Gradient boosting classifier
            - "contextual_bandit": Online learning bandit
    
    Returns:
        Ranked DataFrame of recommendations
    """
    product_vectors, product_index, _, schema = load_artifacts()

    # Choose scoring method based on model_type
    if model_type == "weighted_avg":
        user_vec = compute_user_vector(user_state, schema=schema)
        candidates = get_candidates(
            user_vector=user_vec,
            product_vectors=product_vectors,
            metadata_df=metadata_df,
            constraints=constraints,
            tokens_df=tokens_df,
            product_index=product_index,
            k=candidate_k,
        )
        
        if not candidates:
            return pd.DataFrame(columns=["product_id", "brand", "category", "price", "similarity"])
        
        reranked_ids = rerank_candidates(
            user_vector=user_vec,
            candidate_ids=candidates,
            product_vectors=product_vectors,
            product_index=product_index,
            top_n=top_n,
        )
    else:
        # ML-based model
        model = create_feedback_model(model_type=model_type, dim=product_vectors.shape[1])
        
        # Train model on user interactions
        if not model.fit(user_state):
            # Fall back to weighted average if insufficient training data
            return recommend_with_feedback(
                user_state=user_state,
                metadata_df=metadata_df,
                tokens_df=tokens_df,
                constraints=constraints,
                top_n=top_n,
                candidate_k=candidate_k,
                model_type="weighted_avg"
            )
        
        # Get candidates using weighted average as baseline (for constraint handling)
        user_vec = compute_user_vector(user_state, schema=schema)
        candidates = get_candidates(
            user_vector=user_vec,
            product_vectors=product_vectors,
            metadata_df=metadata_df,
            constraints=constraints,
            tokens_df=tokens_df,
            product_index=product_index,
            k=candidate_k,
        )
        
        if not candidates:
            return pd.DataFrame(columns=["product_id", "brand", "category", "price", "similarity"])
        
        # Score candidates using ML model
        candidate_indices = [product_index[pid] for pid in candidates if pid in product_index]
        candidate_vectors = product_vectors[candidate_indices]
        scores = model.score_products(candidate_vectors)
        
        # Sort by score
        valid_candidates = [candidates[i] for i in range(len(candidates)) if candidates[i] in product_index]
        order = np.argsort(scores)[::-1]
        reranked_ids = [valid_candidates[i] for i in order[: min(top_n, len(order))]]

    # Format output
    out = metadata_df[metadata_df["product_id"].astype(str).isin(reranked_ids)].copy()
    out["product_id"] = out["product_id"].astype(str)
    out = out.set_index("product_id").loc[reranked_ids].reset_index()

    return out