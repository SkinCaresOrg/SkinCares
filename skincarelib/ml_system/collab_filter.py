"""
Item-based Collaborative Filtering using interaction co-occurrence.

Classical neighborhood CF: items are similar if many users co-interacted with them.
Separate from EmbeddingCollaborativeFilter (which is a user-profile embedding model,
not cross-user CF).

Usage:
    cf = ItemBasedCF()
    cf.fit(interactions)           # interactions: list of (user_id, product_id, liked)
    scores = cf.score(seen_ids, candidate_ids)
"""

from typing import Dict, List, Tuple

import numpy as np
from collections import defaultdict


class ItemBasedCF:
    """
    Item-based CF via co-occurrence: two items are similar if users who liked one
    also tended to like the other.

    Fit:
        Build a co-occurrence count matrix over liked interactions only.
        Normalise by each item's total co-occurrence count (column-wise L1) to get
        an item-item "association" score analogous to adjusted cosine.

    Score:
        For a set of seed items the user already liked, sum the association scores
        toward each candidate item and return those sums as CF scores.
    """

    def __init__(self):
        # item_id -> dict{other_item_id -> float co-occurrence count}
        self._cooccur: Dict[str, Dict[str, float]] = {}
        self._item_totals: Dict[str, float] = {}
        self._fitted = False

    def fit(self, interactions: List[Tuple[str, str, bool]]) -> "ItemBasedCF":
        """
        Build co-occurrence from interactions.

        Args:
            interactions: list of (user_id, product_id, liked)
                          Only liked=True interactions are used.
        """
        # Group liked product IDs per user
        user_likes: Dict[str, List[str]] = defaultdict(list)
        for uid, pid, liked in interactions:
            if liked:
                user_likes[str(uid)].append(str(pid))

        cooccur: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for pids in user_likes.values():
            for i, a in enumerate(pids):
                for b in pids:
                    if a != b:
                        cooccur[a][b] += 1.0

        # Normalise each row by total co-occurrence count
        self._cooccur = {}
        self._item_totals = {}
        for item, nbrs in cooccur.items():
            total = sum(nbrs.values())
            self._item_totals[item] = total
            if total > 0:
                self._cooccur[item] = {k: v / total for k, v in nbrs.items()}
            else:
                self._cooccur[item] = {}

        self._fitted = True
        return self

    def score(
        self,
        seed_ids: List[str],
        candidate_ids: List[str],
    ) -> np.ndarray:
        """
        Score candidates given seed items the user liked.

        Args:
            seed_ids:      product IDs the user has liked (training set)
            candidate_ids: product IDs to score

        Returns:
            np.ndarray shape (len(candidate_ids),) — CF association scores.
            Products not seen during fit score 0.
        """
        if not self._fitted or not seed_ids:
            return np.zeros(len(candidate_ids), dtype=np.float32)

        scores = np.zeros(len(candidate_ids), dtype=np.float32)
        for i, cid in enumerate(candidate_ids):
            s = 0.0
            for seed in seed_ids:
                s += self._cooccur.get(seed, {}).get(cid, 0.0)
            scores[i] = s
        return scores

    @property
    def n_items(self) -> int:
        return len(self._cooccur)
