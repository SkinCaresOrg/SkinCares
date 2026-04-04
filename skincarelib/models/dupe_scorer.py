import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


# cosine captures ingredient similarity via TF-IDF
# price rewards candidates close to the source price, not just the cheapest
# ingredient_group captures functional overlap using the 15-group taxonomy
DEFAULT_WEIGHTS = {
    "cosine": 0.55,
    "price": 0.20,
    "ingredient_group": 0.25,
}


class DupeScorer:
    """Computes a composite dupe score for candidate products.

    Score = w_cosine * cosine_sim
          + w_price  * price_score
          + w_ig     * ingredient_group_score

    cosine_sim:
        Cosine similarity between TF-IDF ingredient vectors.

    price_score:
        candidate_price / source_price. Rewards candidates that sit close
        to the source price tier rather than just the absolute cheapest.
        Always < 1 because candidates are pre-filtered to be cheaper.

    ingredient_group_score:
        Jaccard similarity over active functional ingredient groups. A group
        is considered active if its vector slice has a non-zero mean. Falls
        back to 0.0 gracefully if the schema has no group boundaries.
    """

    def __init__(self, vectors, product_index, feature_schema, price_lookup):
        self.vectors = vectors
        self.product_index = product_index
        self.price_lookup = price_lookup
        self.group_slices = self._parse_schema(feature_schema)

    def score(self, source_id, source_price, candidate_ids, weights=None):
        w = self._resolve_weights(weights)

        source_idx = self.product_index[source_id]
        source_vec = self.vectors[source_idx]

        cand_indices = [self.product_index[pid] for pid in candidate_ids]
        cand_vecs = self.vectors[cand_indices]

        cosine_scores = cosine_similarity(
            source_vec.reshape(1, -1), cand_vecs
        ).flatten()

        price_scores = self._price_scores(source_price, candidate_ids)
        ig_scores = self._ingredient_group_scores(source_vec, cand_vecs)

        dupe_scores = (
            w["cosine"] * cosine_scores
            + w["price"] * price_scores
            + w["ingredient_group"] * ig_scores
        )

        return pd.DataFrame(
            {
                "product_id": candidate_ids,
                "cosine_sim": cosine_scores,
                "price_score": price_scores,
                "ingredient_group_score": ig_scores,
                "dupe_score": dupe_scores,
            }
        )

    def _price_scores(self, source_price, candidate_ids):
        if source_price <= 0:
            return np.zeros(len(candidate_ids))
        prices = np.array([self.price_lookup.get(pid, 0.0) for pid in candidate_ids])
        return np.clip(prices / source_price, 0.0, 1.0)

    def _ingredient_group_scores(self, source_vec, cand_vecs):
        if not self.group_slices:
            return np.zeros(cand_vecs.shape[0])

        source_groups = self._active_groups(source_vec)
        scores = np.zeros(cand_vecs.shape[0])

        for i, cand_vec in enumerate(cand_vecs):
            cand_groups = self._active_groups(cand_vec)
            intersection = len(source_groups & cand_groups)
            union = len(source_groups | cand_groups)
            scores[i] = intersection / union if union > 0 else 0.0

        return scores

    def _active_groups(self, vec):
        # a group is active if any of its ingredients appeared in the product
        return {
            name
            for name, (start, end) in self.group_slices.items()
            if vec[start:end].mean() > 0
        }

    def _parse_schema(self, schema):
        """Extract {group_name: (start, end)} from feature_schema.json.

        Expects groups to be a dict of {name: {start, end}}, which is the
        format written by vectorizer.py. Returns empty dict if the schema
        is in the old flat-list format — scores degrade to 0.0 gracefully.
        """
        groups = schema.get("groups", {})
        if not isinstance(groups, dict):
            return {}
        slices = {}
        for name, bounds in groups.items():
            try:
                slices[name] = (int(bounds["start"]), int(bounds["end"]))
            except (KeyError, TypeError, ValueError):
                continue
        return slices

    def _resolve_weights(self, weights):
        merged = {**DEFAULT_WEIGHTS, **(weights or {})}
        total = sum(merged.values())
        if total == 0:
            raise ValueError("Weights cannot all be zero.")
        return {k: v / total for k, v in merged.items()}
