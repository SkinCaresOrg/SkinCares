from typing import Dict, List

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def rerank_candidates(
    user_vector: np.ndarray,
    candidate_ids: List[str],
    product_vectors: np.ndarray,
    product_index: Dict[str, int],
    top_n: int = 10,
    lambda_mult: float = 0.7,
) -> List[str]:
    """
    Rerank candidates using Maximal Marginal Relevance (MMR).

    At each step, selects the candidate that maximises:
        lambda_mult * sim(candidate, user) - (1 - lambda_mult) * max_sim(candidate, already_selected)

    lambda_mult=1.0 -> pure relevance (original behaviour, no diversity penalty)
    lambda_mult=0.7 -> default: relevance-leaning with diversity enforcement
    lambda_mult=0.5 -> balanced relevance / diversity
    lambda_mult=0.0 -> pure diversity (ignores user vector entirely)
    """
    valid_ids = [pid for pid in candidate_ids if pid in product_index]
    if not valid_ids:
        return []

    X = product_vectors[[product_index[pid] for pid in valid_ids]]
    relevance = cosine_similarity(user_vector.reshape(1, -1), X).flatten()

    if lambda_mult == 1.0:
        order = np.argsort(relevance)[::-1]
        return [valid_ids[i] for i in order[: min(top_n, len(order))]]

    # Precompute pairwise similarities between all candidates once
    pairwise = cosine_similarity(X)  # shape (n_candidates, n_candidates)

    selected: List[int] = []
    remaining = list(range(len(valid_ids)))

    while len(selected) < min(top_n, len(valid_ids)):
        if not selected:
            # First pick: no selected set yet, just take most relevant
            best = max(remaining, key=lambda i: relevance[i])
        else:
            best, best_score = None, -np.inf
            for i in remaining:
                redundancy = max(pairwise[i, j] for j in selected)
                score = lambda_mult * relevance[i] - (1 - lambda_mult) * redundancy
                if score > best_score:
                    best_score = score
                    best = i
        selected.append(best)
        remaining.remove(best)

    return [valid_ids[i] for i in selected]


def mock_candidates_similarity_seed(
    seed_product_id: str,
    product_vectors: np.ndarray,
    product_index: Dict[str, int],
    index_to_id: Dict[int, str],
    k: int = 200,
) -> List[str]:
    seed_product_id = str(seed_product_id)
    seed_idx = product_index[seed_product_id]
    seed_vec = product_vectors[seed_idx].reshape(1, -1)

    sims = cosine_similarity(seed_vec, product_vectors).flatten()
    order = np.argsort(sims)[::-1]

    order = [i for i in order if i != seed_idx]
    top_idxs = order[: min(k, len(order))]

    return [index_to_id[i] for i in top_idxs]
