"""
Synthetic evaluation: content-based vs CF vs hybrid.

Generates 500 pseudo-users across 5 profile types, simulates interactions from
product signals, splits 80/20 train/test per user, and evaluates:
  - Content-only  (Rocchio user vector + MMR)
  - CF-only       (item-based co-occurrence CF)
  - Hybrid α=0.25 (25% content, 75% CF)
  - Hybrid α=0.50 (50/50)
  - Hybrid α=0.75 (75% content, 25% CF)

Reports NDCG@10, Precision@10, ILD, avg_sim per model.
Also tunes MMR lambda_mult and hybrid alpha over a hold-out slice.
"""

import json
import warnings

warnings.filterwarnings("ignore")
import random
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skincarelib.ml_system.collab_filter import ItemBasedCF
from skincarelib.ml_system.reranker import rerank_candidates
from skincarelib.models.user_profile import build_user_vector

# ── Load artifacts ─────────────────────────────────────────────────────────────
vectors = np.load(ROOT / "artifacts/product_vectors.npy")
with open(ROOT / "artifacts/product_index.json") as f:
    product_index = json.load(f)

N_PRODUCTS = vectors.shape[0]
SIGNAL_DIMS = [629, 630, 631, 632, 633, 634, 635]  # hydration..irritation_risk
SIGNAL_NAMES = [
    "hydration",
    "barrier",
    "acne_control",
    "soothing",
    "exfoliation",
    "antioxidant",
    "irritation_risk",
]

print(f"Catalog: {N_PRODUCTS} products, {vectors.shape[1]} dims")

# ── Profile type definitions ───────────────────────────────────────────────────
# Each profile specifies which signal dims they prefer (high values are good)
# and which they avoid. Used to compute interaction probability.
PROFILE_TYPES = [
    {
        "name": "oily_acne_budget",
        "prefs": {
            "skin_type": "oily",
            "concerns": ["acne", "large_pores"],
            "sensitivity_level": "rarely_sensitive",
            "budget": 25.0,
            "preferred_categories": ["Cleanser", "Treatment"],
            "preferred_ingredients": [],
            "banned_ingredients": [],
        },
        "signal_weights": np.array([0.1, -0.1, 0.8, 0.2, 0.5, 0.3, -0.7]),
    },
    {
        "name": "dry_aging_premium",
        "prefs": {
            "skin_type": "dry",
            "concerns": ["fine_lines", "dullness"],
            "sensitivity_level": "not_sensitive",
            "budget": 200.0,
            "preferred_categories": ["Moisturizer", "Treatment"],
            "preferred_ingredients": [],
            "banned_ingredients": [],
        },
        "signal_weights": np.array([0.8, 0.6, -0.2, 0.4, 0.2, 0.7, -0.3]),
    },
    {
        "name": "sensitive_redness",
        "prefs": {
            "skin_type": "sensitive",
            "concerns": ["redness", "dryness"],
            "sensitivity_level": "very_sensitive",
            "budget": 100.0,
            "preferred_categories": ["Moisturizer"],
            "preferred_ingredients": [],
            "banned_ingredients": [],
        },
        "signal_weights": np.array([0.5, 0.7, -0.1, 0.9, -0.3, 0.1, -1.0]),
    },
    {
        "name": "combo_dark_spots",
        "prefs": {
            "skin_type": "combination",
            "concerns": ["dark_spots", "oiliness"],
            "sensitivity_level": "somewhat_sensitive",
            "budget": 50.0,
            "preferred_categories": ["Treatment", "Moisturizer"],
            "preferred_ingredients": [],
            "banned_ingredients": [],
        },
        "signal_weights": np.array([0.2, 0.1, 0.4, 0.3, 0.5, 0.8, -0.5]),
    },
    {
        "name": "normal_maintenance",
        "prefs": {
            "skin_type": "normal",
            "concerns": ["maintenance"],
            "sensitivity_level": "not_sensitive",
            "budget": None,
            "preferred_categories": [],
            "preferred_ingredients": [],
            "banned_ingredients": [],
        },
        "signal_weights": np.array([0.4, 0.3, 0.1, 0.2, 0.2, 0.5, -0.2]),
    },
]

# ── Precompute product signal matrix ──────────────────────────────────────────
product_signals = vectors[:, SIGNAL_DIMS]  # (N, 7)


def like_probability(signal_weights: np.ndarray, product_idx: int) -> float:
    """Sigmoid of dot product between user preference weights and product signals."""
    x = float(np.dot(signal_weights, product_signals[product_idx]))
    return 1.0 / (1.0 + np.exp(-3.0 * x))


# ── Generate synthetic users ──────────────────────────────────────────────────
N_USERS = 500
N_INTERACTIONS = 25  # per user
TRAIN_FRAC = 0.8

random.seed(42)
np.random.seed(42)

id_to_idx = {str(pid): idx for pid, idx in product_index.items()}

print(f"Generating {N_USERS} synthetic users ({N_INTERACTIONS} interactions each)...")

users = []
for u in range(N_USERS):
    ptype = PROFILE_TYPES[u % len(PROFILE_TYPES)]
    # Slightly vary signal weights per user for diversity
    noise = np.random.normal(0, 0.1, size=7)
    sw = ptype["signal_weights"] + noise

    # Sample products to interact with — stratified so not all are top-similarity
    # Sample 3× more than needed, then filter by probability
    sample_size = N_INTERACTIONS * 6
    sampled_idx = np.random.choice(
        N_PRODUCTS, size=min(sample_size, N_PRODUCTS), replace=False
    )

    interactions = []
    for pidx in sampled_idx:
        p = like_probability(sw, pidx)
        liked = np.random.random() < p
        pid = None
        for k, v in product_index.items():
            if v == pidx:
                pid = str(k)
                break
        if pid is not None:
            interactions.append((str(u), pid, liked))
        if len(interactions) >= N_INTERACTIONS:
            break

    if len(interactions) < 5:
        continue  # skip users with too few interactions

    n_train = max(1, int(len(interactions) * TRAIN_FRAC))
    train = interactions[:n_train]
    test = interactions[n_train:]

    # Ground truth: test items that were liked
    test_liked = {pid for _, pid, liked in test if liked}
    if not test_liked:
        continue

    users.append(
        {
            "user_id": str(u),
            "profile": ptype,
            "signal_weights": sw,
            "train": train,
            "test": test,
            "test_liked": test_liked,
            "train_liked": [pid for _, pid, liked in train if liked],
        }
    )

print(f"Valid users: {len(users)}")

# ── Build user product_index (needed by build_user_vector) ────────────────────
# product_index maps str product_id -> int row index (already loaded above)

# ── Build CF model ─────────────────────────────────────────────────────────────
print("Fitting ItemBasedCF...")
all_train = [interaction for u in users for interaction in u["train"]]
cf = ItemBasedCF()
cf.fit(all_train)
print(f"CF fitted on {len(all_train)} interactions, {cf.n_items} items")


# ── Helpers ────────────────────────────────────────────────────────────────────
def ild(pids):
    vecs = [vectors[product_index[p]] for p in pids if p in product_index]
    if len(vecs) < 2:
        return None
    M = sk_cosine(vecs)
    n = len(vecs)
    tri = [M[i, j] for i in range(n) for j in range(i + 1, n)]
    return float(1 - np.mean(tri))


def avg_sim_score(user_vec, pids):
    vecs = [vectors[product_index[p]] for p in pids if p in product_index]
    if not vecs:
        return None
    return float(sk_cosine(user_vec.reshape(1, -1), vecs).mean())


# Precompute once — used by all ranking helpers to avoid rebuilding per call
_idx_to_pid = {v: k for k, v in product_index.items()}


def ndcg_at_k(recs, relevant_set, k=10):
    """Compute NDCG@k. Relevant = products in test_liked."""
    dcg = 0.0
    for i, pid in enumerate(recs[:k]):
        if pid in relevant_set:
            dcg += 1.0 / np.log2(i + 2)
    ideal_n = min(len(relevant_set), k)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_n))
    return dcg / idcg if idcg > 0 else 0.0


def precision_at_k(recs, relevant_set, k=10):
    hits = sum(1 for pid in recs[:k] if pid in relevant_set)
    return hits / k


def mean_rank_of_relevant(recs, relevant_set):
    """Mean 1-based rank of relevant items in the ranked list. None if no hits."""
    ranks = [i + 1 for i, pid in enumerate(recs) if pid in relevant_set]
    return float(np.mean(ranks)) if ranks else None


def _cosine_rank(user_vec, exclude_ids, top_n=100):
    """Pure cosine ranking — O(N) dot products + argsort. Used for NDCG/mean_rank.

    MMR is a serving diversity tool, not a retrieval model. NDCG@k should be
    measured against the retrieval ranking (cosine), not the diversity reranking.
    """
    norms = np.linalg.norm(vectors, axis=1) + 1e-9
    sims = vectors @ user_vec / norms
    exclude_set = set(exclude_ids)
    top_idx = np.argsort(sims)[::-1]
    return [_idx_to_pid[i] for i in top_idx if _idx_to_pid.get(i) not in exclude_set][
        :top_n
    ]


def get_content_recs(user_vec, exclude_ids, top_n=10, lambda_mult=0.7):
    """Top-200 cosine pool → MMR rerank to top_n for serving metrics (ILD, avg_sim)."""
    pool = _cosine_rank(user_vec, exclude_ids, top_n=200)
    return rerank_candidates(
        user_vec, pool, vectors, product_index, top_n=top_n, lambda_mult=lambda_mult
    )


def get_cf_recs(seed_ids, exclude_ids, all_pids, top_n=100):
    """CF score all candidates, return top_n."""
    exclude_set = set(exclude_ids)
    candidates = [p for p in all_pids if p not in exclude_set][:2000]
    cf_scores = cf.score(seed_ids, candidates)
    order = np.argsort(cf_scores)[::-1]
    return [candidates[i] for i in order[:top_n]]


def get_hybrid_ranked(user_vec, seed_ids, exclude_ids, top_n=100):
    """
    Hybrid cosine+CF ranking (no MMR) — used for NDCG/mean_rank evaluation.
    alpha=0.5: equal weight on normalised content and CF scores.
    """
    exclude_set = set(exclude_ids)
    norms = np.linalg.norm(vectors, axis=1) + 1e-9
    content_sims = vectors @ user_vec / norms

    top_content_idx = np.argsort(content_sims)[::-1]
    candidates = [
        _idx_to_pid[i] for i in top_content_idx if _idx_to_pid.get(i) not in exclude_set
    ][:400]

    content_scores = np.array(
        [
            content_sims[product_index[p]] if p in product_index else 0.0
            for p in candidates
        ],
        dtype=np.float32,
    )
    cf_scores_arr = cf.score(seed_ids, candidates)

    def norm01(x):
        mn, mx = x.min(), x.max()
        return (x - mn) / (mx - mn + 1e-9)

    combined = 0.5 * norm01(content_scores) + 0.5 * norm01(cf_scores_arr)
    order = np.argsort(combined)[::-1]
    return [candidates[i] for i in order[:top_n]]


# Build list of all known product IDs
all_product_ids = list(product_index.keys())

# ── Evaluate models ────────────────────────────────────────────────────────────
# NDCG and mean_rank use pure cosine ranking (fast, no MMR overhead).
# ILD and avg_sim use MMR top-10 (the actual serving output).
# This separation is intentional: NDCG measures retrieval quality;
# MMR is a post-retrieval diversity step that shouldn't affect the retrieval score.
RANK_FNS = {
    "content": lambda u, lm: _cosine_rank(u["user_vec"], u["train_liked"], top_n=100),
    "cf": lambda u, _: get_cf_recs(
        u["train_liked"], u["train_liked"], all_product_ids, top_n=100
    ),
    "hybrid_0.50": lambda u, lm: get_hybrid_ranked(
        u["user_vec"], u["train_liked"], u["train_liked"], top_n=100
    ),
}
SERVE_FNS = {
    "content": lambda u, lm: get_content_recs(
        u["user_vec"], u["train_liked"], top_n=10, lambda_mult=lm
    ),
    "cf": lambda u, _: get_cf_recs(
        u["train_liked"], u["train_liked"], all_product_ids, top_n=10
    ),
    "hybrid_0.50": lambda u, lm: get_hybrid_ranked(
        u["user_vec"], u["train_liked"], u["train_liked"], top_n=10
    ),
}

LAMBDA_MULTS = [0.3, 0.5, 0.7, 0.9]

print("\nBuilding user vectors...")
for u in users:
    u["user_vec"] = build_user_vector(
        liked_product_ids=u["train_liked"],
        explicit_prefs=u["profile"]["prefs"],
        product_vectors=vectors,
        product_index=product_index,
    )

print("Done. Running evaluations...\n")

# ── Lambda tuning (content model only, on first 100 users) ────────────────────
# NDCG tuning: vary MMR lambda — but since NDCG uses pure cosine rank,
# we're actually tuning ILD here (lambda only affects serving diversity).
print("── MMR lambda_mult tuning — ILD@10 vs diversity tradeoff (100 users) ──────")
print(f"{'lambda_mult':<14} {'ILD@10':>8} {'avg_sim@10':>12}")
print("─" * 38)

tune_users = users[:100]
best_lm = 0.7  # default; tune by ILD if needed
for lm in LAMBDA_MULTS:
    ilds, sims = [], []
    for u in tune_users:
        recs = get_content_recs(
            u["user_vec"], u["train_liked"], top_n=10, lambda_mult=lm
        )
        il = ild(recs)
        if il is not None:
            ilds.append(il)
        s = avg_sim_score(u["user_vec"], recs)
        if s is not None:
            sims.append(s)
    print(
        f"{lm:<14.2f} {float(np.mean(ilds)) if ilds else 0:>8.4f} {float(np.mean(sims)) if sims else 0:>12.4f}"
    )

print(f"\nUsing lambda_mult={best_lm} for serving metrics.\n")

# ── Full model comparison (remaining users) ───────────────────────────────────
eval_users = users[100:]
print(
    f"── Full model comparison ({len(eval_users)} users) ──────────────────────────────────"
)
print(
    f"{'Model':<16} {'NDCG@10':>8} {'NDCG@100':>10} {'P@10':>6} {'mean_rank':>10} {'ILD@10':>8} {'avg_sim':>9}"
)
print("─" * 76)

results = {}
for model_name in RANK_FNS:
    rank_fn = RANK_FNS[model_name]
    serve_fn = SERVE_FNS[model_name]
    n10, n100, precs, ranks, ilds_list, sims = [], [], [], [], [], []
    for u in eval_users:
        try:
            ranked = rank_fn(u, best_lm)  # pure cosine / CF rank — for NDCG
            served = serve_fn(u, best_lm)  # MMR top-10 — for ILD, avg_sim
        except Exception:
            continue
        if not ranked:
            continue
        n10.append(ndcg_at_k(ranked, u["test_liked"], k=10))
        n100.append(ndcg_at_k(ranked, u["test_liked"], k=100))
        precs.append(precision_at_k(ranked, u["test_liked"], k=10))
        mr = mean_rank_of_relevant(ranked, u["test_liked"])
        if mr is not None:
            ranks.append(mr)
        il = ild(served)
        if il is not None:
            ilds_list.append(il)
        s = avg_sim_score(u["user_vec"], served)
        if s is not None:
            sims.append(s)

    r = {
        "ndcg10": float(np.mean(n10)) if n10 else 0.0,
        "ndcg100": float(np.mean(n100)) if n100 else 0.0,
        "precision": float(np.mean(precs)) if precs else 0.0,
        "mean_rank": float(np.mean(ranks)) if ranks else None,
        "ild": float(np.mean(ilds_list)) if ilds_list else 0.0,
        "avg_sim": float(np.mean(sims)) if sims else 0.0,
        "n": len(n10),
    }
    results[model_name] = r
    mr_str = f"{r['mean_rank']:.1f}" if r["mean_rank"] is not None else "none"
    print(
        f"{model_name:<16} {r['ndcg10']:>8.4f} {r['ndcg100']:>10.4f} {r['precision']:>6.4f} "
        f"{mr_str:>10} {r['ild']:>8.4f} {r['avg_sim']:>9.4f}"
    )

# ── Per-profile breakdown ─────────────────────────────────────────────────────
print("\n── Per-profile breakdown (content vs hybrid_0.50) ────────────────────────")
print(
    f"{'Profile':<25} {'Model':<16} {'NDCG@10':>8} {'NDCG@100':>10} {'mean_rank':>10}"
)
print("─" * 74)

for pname in [pt["name"] for pt in PROFILE_TYPES]:
    ptype_users = [u for u in eval_users if u["profile"]["name"] == pname]
    if not ptype_users:
        continue
    for model_name in ["content", "hybrid_0.50"]:
        rank_fn = RANK_FNS[model_name]
        n10, n100, ranks = [], [], []
        for u in ptype_users:
            try:
                ranked = rank_fn(u, best_lm)
            except Exception:
                continue
            if not ranked:
                continue
            n10.append(ndcg_at_k(ranked, u["test_liked"], k=10))
            n100.append(ndcg_at_k(ranked, u["test_liked"], k=100))
            mr = mean_rank_of_relevant(ranked, u["test_liked"])
            if mr is not None:
                ranks.append(mr)
        nd10 = float(np.mean(n10)) if n10 else 0.0
        nd100 = float(np.mean(n100)) if n100 else 0.0
        mr_str = f"{float(np.mean(ranks)):.1f}" if ranks else "none"
        print(f"{pname:<25} {model_name:<16} {nd10:>8.4f} {nd100:>10.4f} {mr_str:>10}")
    print()

print("Done.")
