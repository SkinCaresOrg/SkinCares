"""Generates plain-English explanations for dupe finder results."""


def explain_dupe(source_row, candidate_row) -> str:
    """Return a natural-language explanation for a single dupe result.

    Combines ingredient similarity, functional group overlap, and price
    savings into a single coherent sentence rather than three separate
    data points. Avoids exposing internal metrics (cosine scores, group
    counts) that are meaningful to engineers but not to end users.
    """
    source_name = _short_name(source_row)
    source_price = float(source_row.get("price", 0.0))
    cand_price = float(candidate_row.get("price", 0.0))
    cosine = float(candidate_row.get("cosine_sim", 0.0))
    ig_score = float(candidate_row.get("ingredient_group_score", 0.0))

    # --- ingredient similarity phrase ---
    if cosine >= 0.90:
        similarity = "nearly identical ingredient profile to"
    elif cosine >= 0.78:
        similarity = "very similar ingredients to"
    elif cosine >= 0.65:
        similarity = "a closely matched formulation to"
    else:
        similarity = "a comparable formulation to"

    # --- functional group phrase ---
    if ig_score >= 0.80:
        function_phrase = "covering the same skin concerns"
    elif ig_score >= 0.60:
        function_phrase = "targeting most of the same skin concerns"
    elif ig_score >= 0.40:
        function_phrase = "addressing several of the same skin concerns"
    else:
        function_phrase = "with some overlapping skin benefits"

    # --- price phrase ---
    price_phrase = ""
    if source_price > 0 and cand_price > 0 and source_price > cand_price:
        savings_pct = (source_price - cand_price) / source_price
        savings_abs = source_price - cand_price

        if savings_pct >= 0.60:
            price_phrase = (
                f" — at ${cand_price:.2f} it saves you "
                f"${savings_abs:.2f} ({savings_pct:.0%} less)"
            )
        elif savings_pct >= 0.30:
            price_phrase = (
                f" at a significantly lower price "
                f"(${cand_price:.2f} vs ${source_price:.2f})"
            )
        elif savings_pct >= 0.10:
            price_phrase = f" for less (${cand_price:.2f} vs ${source_price:.2f})"

    return f"Has a {similarity} {source_name}, {function_phrase}{price_phrase}."


def _short_name(row) -> str:
    """Return a concise product identifier: 'Brand ProductName'."""
    name = str(row.get("product_name", row.get("name", "the original"))).strip()
    brand = str(row.get("brand", "")).strip()

    # strip brand prefix if already present in name
    if brand and name.lower().startswith(brand.lower()):
        name = name[len(brand) :].strip()

    # trim at first comma to remove size/variant suffixes
    if "," in name:
        name = name.split(",")[0].strip()

    if brand:
        return f"{brand} {name}"
    return name
