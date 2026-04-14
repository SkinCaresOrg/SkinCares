"""
Compare cold-start candidate pool strategies:
  A) top-k cosine  → MMR rerank
  B) cluster-sampled pool → MMR rerank   (our fix for popularity bias)

Metrics per profile: ILD, avg_sim, brand diversity
Cross-user metrics:  catalog coverage, inter-user Jaccard overlap
Coverage scaling:    how coverage grows as we add more diverse users
"""

import json
import warnings

warnings.filterwarnings("ignore")
import random

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

from skincarelib.ml_system.reranker import (
    rerank_candidates,
    build_diverse_candidate_pool,
)
from skincarelib.models.user_profile import build_user_vector

root = Path(__file__).resolve().parent.parent
vectors = np.load(root / "artifacts/product_vectors.npy")
with open(root / "artifacts/product_index.json") as f:
    product_index = json.load(f)
index_to_id = {v: k for k, v in product_index.items()}

print(f"Catalog: {vectors.shape[0]} products, {vectors.shape[1]} dims")

print("Fitting MiniBatchKMeans (20 clusters)...")
mbk = MiniBatchKMeans(n_clusters=20, random_state=42, n_init=3, batch_size=2048)
labels = mbk.fit_predict(vectors)
cluster_to_ids: dict = {}
for vi, ci in enumerate(labels):
    pid = index_to_id.get(vi)
    if pid is not None:
        cluster_to_ids.setdefault(int(ci), []).append(pid)
print("Done.\n")

meta = pd.read_csv(root / "data/processed/products_with_signals.csv")
meta["product_id"] = meta.index.astype(str)
pid_to_brand = dict(zip(meta["product_id"], meta["brand"]))

TOP_N = 10
POOL_SIZE = 200

# ── Helpers ───────────────────────────────────────────────────────────────────


def top_k_cosine_pool(user_vec, k=POOL_SIZE):
    """O(N) top-k by dot product — no pairwise matrix."""
    sims = vectors @ user_vec / (np.linalg.norm(vectors, axis=1) + 1e-9)
    top_idx = np.argpartition(sims, -k)[-k:]
    top_idx = top_idx[np.argsort(sims[top_idx])[::-1]]
    return [index_to_id[i] for i in top_idx if i in index_to_id]


def cluster_pool(user_vec):
    return build_diverse_candidate_pool(
        user_vector=user_vec,
        kmeans=mbk,
        cluster_to_ids=cluster_to_ids,
        product_vectors=vectors,
        product_index=product_index,
        pool_size=POOL_SIZE,
    )


def ild(pids):
    vecs = [vectors[product_index[p]] for p in pids if p in product_index]
    if len(vecs) < 2:
        return None
    M = sk_cosine(vecs)
    n = len(vecs)
    tri = [M[i, j] for i in range(n) for j in range(i + 1, n)]
    return round(float(1 - np.mean(tri)), 4)


def avg_sim(user_vec, pids):
    vecs = [vectors[product_index[p]] for p in pids if p in product_index]
    if not vecs:
        return None
    return round(float(sk_cosine(user_vec.reshape(1, -1), vecs).mean()), 4)


def run(user_vec, pool_fn):
    pool = pool_fn(user_vec)
    return rerank_candidates(user_vec, pool, vectors, product_index, top_n=TOP_N)


# ── 5 core profiles ───────────────────────────────────────────────────────────
CORE_PROFILES = [
    {
        "name": "oily_acne_budget",
        "skin_type": "oily",
        "concerns": ["acne", "large_pores"],
        "sensitivity_level": "rarely_sensitive",
        "budget": 25.0,
        "preferred_categories": ["Cleanser", "Treatment"],
        "preferred_ingredients": [],
        "banned_ingredients": [],
    },
    {
        "name": "dry_aging_premium",
        "skin_type": "dry",
        "concerns": ["fine_lines", "dullness"],
        "sensitivity_level": "not_sensitive",
        "budget": 200.0,
        "preferred_categories": ["Moisturizer", "Treatment"],
        "preferred_ingredients": [],
        "banned_ingredients": [],
    },
    {
        "name": "sensitive_redness",
        "skin_type": "sensitive",
        "concerns": ["redness", "dryness"],
        "sensitivity_level": "very_sensitive",
        "budget": 100.0,
        "preferred_categories": ["Moisturizer"],
        "preferred_ingredients": [],
        "banned_ingredients": [],
    },
    {
        "name": "combo_dark_spots",
        "skin_type": "combination",
        "concerns": ["dark_spots", "oiliness"],
        "sensitivity_level": "somewhat_sensitive",
        "budget": 50.0,
        "preferred_categories": ["Treatment", "Moisturizer"],
        "preferred_ingredients": [],
        "banned_ingredients": [],
    },
    {
        "name": "normal_maintenance",
        "skin_type": "normal",
        "concerns": ["maintenance"],
        "sensitivity_level": "not_sensitive",
        "budget": None,
        "preferred_categories": [],
        "preferred_ingredients": [],
        "banned_ingredients": [],
    },
]

# ── Per-profile comparison ────────────────────────────────────────────────────
print(f"{'Profile':<25} {'Method':<14} {'ILD':>7} {'avg_sim':>9} {'brands':>8}")
print("─" * 68)

cosine_sets, cluster_sets = [], []
for p in CORE_PROFILES:
    prefs = {k: v for k, v in p.items() if k != "name"}
    uv = build_user_vector(
        liked_product_ids=[],
        explicit_prefs=prefs,
        product_vectors=vectors,
        product_index=product_index,
    )
    cr = run(uv, top_k_cosine_pool)
    cl = run(uv, cluster_pool)
    cosine_sets.append(set(cr))
    cluster_sets.append(set(cl))
    for method, recs in [("cosine+MMR", cr), ("cluster+MMR", cl)]:
        brands = len({pid_to_brand.get(pid, "?") for pid in recs})
        print(
            f"{p['name']:<25} {method:<14} {str(ild(recs)):>7} {str(avg_sim(uv, recs)):>9} {brands:>8}"
        )
    print()

# ── Cross-user (5 profiles) ───────────────────────────────────────────────────
print("── Cross-user metrics (5 core profiles) ─────────────────────────────────")
for label, sets in [("cosine+MMR", cosine_sets), ("cluster+MMR", cluster_sets)]:
    unique = set().union(*sets)
    cov = round(len(unique) / len(product_index) * 100, 3)
    pairs, jsum = 0, 0.0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            inter = len(sets[i] & sets[j])
            union = len(sets[i] | sets[j])
            jsum += inter / union if union else 0
            pairs += 1
    avg_j = round(jsum / pairs, 4) if pairs else 0
    print(
        f"  {label:<14}  coverage={cov}%  inter_user_jaccard={avg_j}  unique={len(unique)}"
    )

# ── Coverage scaling: 5 → 10 → 20 → 50 users ─────────────────────────────────
print("\n── Coverage scaling (50 diverse synthetic users) ─────────────────────────")
skin_types = ["oily", "dry", "sensitive", "combination", "normal"]
concern_sets = [
    ["acne", "large_pores"],
    ["fine_lines", "dullness"],
    ["redness", "dryness"],
    ["dark_spots", "oiliness"],
    ["maintenance"],
    ["dryness", "fine_lines"],
    ["acne", "redness"],
    ["dullness", "dark_spots"],
]
budgets = [25.0, 50.0, 100.0, 200.0, None]
sensitivities = [
    "very_sensitive",
    "somewhat_sensitive",
    "rarely_sensitive",
    "not_sensitive",
]
cat_sets = [
    ["Cleanser", "Treatment"],
    ["Moisturizer"],
    ["Treatment", "Moisturizer"],
    ["Cleanser"],
    [],
    ["Moisturizer", "Treatment"],
]

random.seed(42)
synthetic = [
    {
        "skin_type": random.choice(skin_types),
        "concerns": random.choice(concern_sets),
        "sensitivity_level": random.choice(sensitivities),
        "budget": random.choice(budgets),
        "preferred_categories": random.choice(cat_sets),
        "preferred_ingredients": [],
        "banned_ingredients": [],
    }
    for _ in range(50)
]

cosine_all, cluster_all = [], []
for p in synthetic:
    uv = build_user_vector(
        liked_product_ids=[],
        explicit_prefs=p,
        product_vectors=vectors,
        product_index=product_index,
    )
    cosine_all.append(set(run(uv, top_k_cosine_pool)))
    cluster_all.append(set(run(uv, cluster_pool)))

print(
    f"  {'users':<8} {'cosine_cov':>12} {'cluster_cov':>13} {'cosine_unique':>14} {'cluster_unique':>15}"
)
print("  " + "─" * 65)
for n in [5, 10, 20, 30, 50]:
    cu = set().union(*cosine_all[:n])
    cl = set().union(*cluster_all[:n])
    cc = round(len(cu) / len(product_index) * 100, 3)
    clc = round(len(cl) / len(product_index) * 100, 3)
    print(f"  {n:<8} {cc:>11}%  {clc:>12}%  {len(cu):>14}  {len(cl):>15}")
