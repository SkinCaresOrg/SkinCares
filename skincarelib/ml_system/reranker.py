from typing import List, Dict

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


def build_diverse_candidate_pool(
    user_vector: np.ndarray,
    kmeans,
    cluster_to_ids: Dict[int, List[str]],
    product_vectors: np.ndarray,
    product_index: Dict[str, int],
    pool_size: int = 200,
    top_clusters: int = 8,
) -> List[str]:
    """
    Build a diverse candidate pool by sampling from multiple clusters proportionally.

    The problem with top-k cosine as a pre-filter: it always pulls from the same
    high-norm products that have large dot products with almost any user vector,
    which causes catalog coverage to flatline even as user diversity increases.

    This function instead:
    1. Scores all cluster centroids against the user vector (O(K), very cheap)
    2. Takes the top_clusters closest clusters
    3. Allocates pool slots proportionally to centroid similarity
       (closer cluster gets more slots, but every cluster gets at least some)
    4. Within each cluster, picks the best candidates by cosine similarity

    The resulting pool is passed to rerank_candidates for final MMR reranking.
    """
    centroid_sims = cosine_similarity(
        user_vector.reshape(1, -1), kmeans.cluster_centers_
    ).flatten()
    best_clusters = np.argsort(centroid_sims)[::-1][:top_clusters]

    # Proportional slot allocation — weight by centroid similarity, floor at 1
    best_sims = np.maximum(centroid_sims[best_clusters], 0.0)
    total = best_sims.sum()
    if total < 1e-9:
        allocations = [pool_size // top_clusters] * top_clusters
    else:
        allocations = [max(1, int(pool_size * s / total)) for s in best_sims]

    pool: List[str] = []
    for cid, alloc in zip(best_clusters, allocations):
        cluster_pids = [
            p for p in cluster_to_ids.get(int(cid), []) if p in product_index
        ]
        if not cluster_pids:
            continue
        cvecs = product_vectors[[product_index[p] for p in cluster_pids]]
        sims = cosine_similarity(user_vector.reshape(1, -1), cvecs).flatten()
        top_in = np.argsort(sims)[::-1][:alloc]
        pool.extend(cluster_pids[i] for i in top_in)

    return pool


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
