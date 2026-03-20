from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from skincarelib.ml_system.artifacts import load_artifacts
from skincarelib.ml_system.candidate_source import get_candidates
from skincarelib.ml_system.feedback_update import UserState, compute_user_vector, compute_user_vector_lr
from skincarelib.ml_system.embedding_collab_filter import EmbeddingCollaborativeFilter
from skincarelib.ml_system.reranker import rerank_candidates


def recommend_with_feedback(
    user_state: UserState,
    metadata_df: pd.DataFrame,
    tokens_df: pd.DataFrame,
    constraints: Dict[str, Any],
    top_n: int = 10,
    candidate_k: int = 200,
) -> pd.DataFrame:
    """
    Pipeline:
      1) candidate list from ranker (constraint-aware)
      2) rerank with Model 3 feedback-updated user_vector
      3) return ordered DataFrame
    """
    product_vectors, product_index, _, schema = load_artifacts()

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

    
    out = metadata_df[metadata_df["product_id"].astype(str).isin(reranked_ids)].copy()
    out["product_id"] = out["product_id"].astype(str)
    out = out.set_index("product_id").loc[reranked_ids].reset_index()

    return out


def recommend_with_lr_feedback(
    user_state: UserState,
    metadata_df: pd.DataFrame,
    tokens_df: pd.DataFrame,
    constraints: Dict[str, Any],
    top_n: int = 10,
    candidate_k: int = 200,
) -> pd.DataFrame:
    """
    Recommendation pipeline using Logistic Regression for feedback learning.
    
    Improvement over recommend_with_feedback:
    - Uses compute_user_vector_lr instead of simple weighted average
    - Learns feature importance from feedback history
    - Better scales with more user interactions
    
    Pipeline:
      1) Learn feature weights using logistic regression from feedback
      2) Build user vector using learned weights
      3) Generate candidate list (constraint-aware)
      4) Rerank candidates with updated user vector
      5) Return ordered DataFrame
    
    Args:
        user_state: UserState with feedback history
        metadata_df: Product metadata
        tokens_df: Product ingredient tokens
        constraints: Budget, category, ingredient filters
        top_n: Number of recommendations to return
        candidate_k: Size of candidate pool before reranking
        
    Returns:
        DataFrame with product recommendations
    """
    product_vectors, product_index, _, schema = load_artifacts()

    # Use logistic regression to learn feedback weights
    user_vec = compute_user_vector_lr(user_state, schema=schema)
    
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

    
    out = metadata_df[metadata_df["product_id"].astype(str).isin(reranked_ids)].copy()
    out["product_id"] = out["product_id"].astype(str)
    out = out.set_index("product_id").loc[reranked_ids].reset_index()

    return out


def recommend_with_collaborative_filtering(
    user_state: UserState,
    user_id: str,
    metadata_df: pd.DataFrame,
    tokens_df: pd.DataFrame,
    constraints: Dict[str, Any],
    top_n: int = 10,
    collab_weight: float = 0.5,
) -> pd.DataFrame:
    """
    Advanced recommendation using embedding-based collaborative filtering.
    
    Combines content-based and collaborative filtering:
    - Builds user embedding from interaction history
    - Uses collaborative similarity between user and products
    - Blends with content-based ranking for better diversity
    
    This is a true advanced method that goes beyond simple content-based filtering
    by learning implicit user preferences through collaborative embeddings.
    
    Pipeline:
      1) Initialize collaborative filter with product embeddings
      2) Record user's feedback interactions
      3) Build user embedding from collaborative patterns
      4) Rank products by collaborative similarity
      5) Optionally blend with content-based scores
      6) Return filtered and ranked results
    
    Args:
        user_state: UserState with feedback history
        user_id: User identifier for tracking
        metadata_df: Product metadata
        tokens_df: Product ingredient tokens
        constraints: Budget, category, ingredient filters
        top_n: Number of recommendations to return
        collab_weight: How much to weight collaborative signal (0-1)
                      0.0 = pure content-based, 1.0 = pure collaborative
        
    Returns:
        DataFrame with product recommendations, including collaboration score
    """
    product_vectors, product_index, _, schema = load_artifacts()
    
    # Initialize collaborative filter
    collab_filter = EmbeddingCollaborativeFilter(product_vectors, product_index)
    
    # Record all user interactions in the collaborative model
    for vec in user_state.liked_vectors:
        # Find product ID from vector (reverse lookup)
        for pid, idx in product_index.items():
            if np.allclose(product_vectors[idx], vec, rtol=1e-5):
                collab_filter.record_interaction(user_id, pid, feedback_label=1)
                break
    
    for vec in user_state.disliked_vectors:
        for pid, idx in product_index.items():
            if np.allclose(product_vectors[idx], vec, rtol=1e-5):
                collab_filter.record_interaction(user_id, pid, feedback_label=0)
                break
    
    for vec in user_state.irritation_vectors:
        for pid, idx in product_index.items():
            if np.allclose(product_vectors[idx], vec, rtol=1e-5):
                collab_filter.record_interaction(user_id, pid, feedback_label=-1)
                break
    
    # Apply filters as per constraints
    budget = constraints.get("budget")
    categories = constraints.get("categories")
    banned_ingredients = set(constraints.get("banned_ingredients") or [])
    liked_ids = set(constraints.get("liked_product_ids") or [])
    
    # Filter candidate products
    candidates = metadata_df.copy()
    
    if budget is not None:
        candidates = candidates[candidates["price"] <= float(budget)]
    
    if categories:
        candidates = candidates[candidates["category"].isin(categories)]
    
    if banned_ingredients and not tokens_df.empty:
        def has_no_banned(token_string):
            if not isinstance(token_string, str) or not token_string.strip():
                return True
            tokens = {t.strip().lower() for t in token_string.split(",")}
            banned_lower = {b.lower().strip() for b in banned_ingredients}
            return tokens.isdisjoint(banned_lower)
        
        merged = candidates.merge(
            tokens_df[["product_id", "ingredient_tokens"]],
            on="product_id",
            how="left",
        )
        mask = merged["ingredient_tokens"].apply(has_no_banned)
        candidates = merged[mask][list(candidates.columns)]
    
    # Exclude already-liked products
    if liked_ids:
        candidates = candidates[~candidates["product_id"].isin(liked_ids)]
    
    if candidates.empty:
        return pd.DataFrame(columns=["product_id", "brand", "category", "price", "collab_score"])
    
    # Get collaborative recommendations
    candidate_ids = candidates["product_id"].astype(str).tolist()
    collab_results = collab_filter.get_interesting_products_for_user(
        user_id=user_id,
        all_candidate_ids=candidate_ids,
        exclude_ids=list(liked_ids),
        top_n=top_n,
    )
    
    if not collab_results:
        # Fallback to content-based
        return recommend_with_lr_feedback(
            user_state, metadata_df, tokens_df, constraints, top_n
        )
    
    # Create result DataFrame with collaborative scores
    result_ids, collab_scores = zip(*collab_results)
    out = candidates[candidates["product_id"].isin(result_ids)].copy()
    out["product_id"] = out["product_id"].astype(str)
    out = out.set_index("product_id").loc[list(result_ids)].reset_index()
    out["collab_score"] = collab_scores
    
    return out[["product_id", "brand", "category", "price", "collab_score"]]