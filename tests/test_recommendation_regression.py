from typing import Optional, List, Tuple
from fastapi.testclient import TestClient

from deployment.api import app


client = TestClient(app)


def _onboard_user(payload: Optional[dict] = None) -> str:
    payload = payload or {
        "skin_type": "oily",
        "concerns": ["acne", "dark_spots"],
        "sensitivity_level": "very_sensitive",
        "ingredient_exclusions": ["fragrance", "alcohol"],
        "price_range": "affordable",
        "routine_size": "basic",
        "product_interests": ["cleanser", "treatment", "sunscreen"],
    }
    response = client.post("/api/onboarding", json=payload)
    assert response.status_code == 200
    return response.json()["user_id"]


def _rank_and_score(products: List[dict], product_id: int) -> Tuple[Optional[int], Optional[float]]:
    for idx, product in enumerate(products, start=1):
        if product.get("product_id") == product_id:
            return idx, product.get("recommendation_score")
    return None, None


def _get_recommendations(
    user_id: str,
    limit: int = 60,
    category: str = "sunscreen",
) -> list[dict]:
    response = client.get(
        f"/api/recommendations/{user_id}",
        params={"category": category, "limit": limit},
    )
    assert response.status_code == 200
    return response.json().get("products", [])


def test_onboarding_profile_changes_recommendations_regression() -> None:
    oily_payload = {
        "skin_type": "oily",
        "concerns": ["acne", "dark_spots"],
        "sensitivity_level": "very_sensitive",
        "ingredient_exclusions": ["fragrance", "alcohol"],
        "price_range": "affordable",
        "routine_size": "basic",
        "product_interests": ["cleanser", "treatment", "sunscreen"],
    }
    dry_payload = {
        "skin_type": "dry",
        "concerns": ["dryness", "redness"],
        "sensitivity_level": "very_sensitive",
        "ingredient_exclusions": [],
        "price_range": "premium",
        "routine_size": "basic",
        "product_interests": ["moisturizer", "face_mask"],
    }

    oily_user_id = _onboard_user(oily_payload)
    dry_user_id = _onboard_user(dry_payload)

    oily_recs = _get_recommendations(oily_user_id, limit=15, category="moisturizer")
    dry_recs = _get_recommendations(dry_user_id, limit=15, category="moisturizer")

    assert len(oily_recs) >= 10
    assert len(dry_recs) >= 10

    oily_top10 = [p["product_id"] for p in oily_recs[:10]]
    dry_top10 = [p["product_id"] for p in dry_recs[:10]]

    overlap = len(set(oily_top10).intersection(dry_top10))
    assert overlap <= 8


def test_repeated_dislikes_demote_product_regression() -> None:
    user_id = _onboard_user()

    before = _get_recommendations(user_id)
    assert len(before) >= 3
    target_id = before[0]["product_id"]
    before_rank, before_score = _rank_and_score(before, target_id)

    for _ in range(10):
        response = client.post(
            "/api/feedback",
            json={
                "user_id": user_id,
                "product_id": target_id,
                "has_tried": True,
                "reaction": "dislike",
                "reason_tags": ["felt_greasy", "broke_me_out"],
                "free_text": "Too greasy",
            },
        )
        assert response.status_code == 200

    after = _get_recommendations(user_id)
    after_rank, after_score = _rank_and_score(after, target_id)

    demoted_by_rank = (
        before_rank is not None
        and after_rank is not None
        and after_rank >= (before_rank + 3)
    )
    dropped_from_window = after_rank is None
    lowered_score = (
        before_score is not None
        and after_score is not None
        and after_score <= (before_score - 0.08)
    )

    assert demoted_by_rank or dropped_from_window or lowered_score


def test_repeated_likes_boost_product_regression() -> None:
    user_id = _onboard_user()

    before = _get_recommendations(user_id)
    assert len(before) >= 12

    target = before[9]
    target_id = target["product_id"]
    before_rank, before_score = _rank_and_score(before, target_id)

    for _ in range(10):
        response = client.post(
            "/api/feedback",
            json={
                "user_id": user_id,
                "product_id": target_id,
                "has_tried": True,
                "reaction": "like",
                "reason_tags": ["hydrating", "non_irritating"],
                "free_text": "Hydrating and gentle",
            },
        )
        assert response.status_code == 200

    after = _get_recommendations(user_id)
    after_rank, after_score = _rank_and_score(after, target_id)

    improved_rank = (
        before_rank is not None
        and after_rank is not None
        and after_rank <= (before_rank - 2)
    )
    improved_score = (
        before_score is not None
        and after_score is not None
        and after_score >= (before_score + 0.06)
    )

    assert improved_rank or improved_score
