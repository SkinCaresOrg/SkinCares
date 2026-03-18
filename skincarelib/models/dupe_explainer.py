"""Generates plain-English explanations for dupe finder results."""


_COSINE_LABELS = [
    (0.90, "Excellent ingredient match"),
    (0.75, "Strong ingredient match"),
    (0.60, "Good ingredient match"),
    (0.00, "Moderate ingredient match"),
]

_SAVINGS_LABELS = [
    (0.50, "significantly cheaper"),
    (0.25, "notably cheaper"),
    (0.10, "slightly cheaper"),
    (0.00, "marginally cheaper"),
]

_IG_LABELS = [
    (0.80, "Shares nearly all functional ingredient groups."),
    (0.60, "Shares most functional ingredient groups."),
    (0.40, "Shares several functional ingredient groups."),
    (0.20, "Some overlap in functional ingredient groups."),
    (0.01, "Limited overlap in functional ingredient groups."),
]


def explain_dupe(source_row, candidate_row):
    """Return a plain-English explanation for a single dupe result.

    Surfaces the two or three most relevant signals: ingredient similarity,
    price savings, and functional group overlap.
    """
    parts = []

    cosine = float(candidate_row.get("cosine_sim", 0.0))
    parts.append(f"{_label(cosine, _COSINE_LABELS)} (cosine {cosine:.2f}).")

    source_price = float(source_row.get("price", 0.0))
    cand_price   = float(candidate_row.get("price", 0.0))

    if source_price > 0 and (source_price - cand_price) >= 3.00:
        savings = (source_price - cand_price) / source_price
        parts.append(
            f"{_label(savings, _SAVINGS_LABELS).capitalize()} than the original "
            f"(${cand_price:.2f} vs ${source_price:.2f}, {savings:.0%} savings)."
        )

    ig = float(candidate_row.get("ingredient_group_score", 0.0))
    ig_sentence = _label(ig, _IG_LABELS, default="")
    if ig_sentence:
        parts.append(ig_sentence)

    return " ".join(parts)


def _label(value, thresholds, default=None):
    for threshold, label in thresholds:
        if value >= threshold:
            return label
    return default if default is not None else thresholds[-1][1]