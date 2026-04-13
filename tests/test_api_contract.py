from fastapi.testclient import TestClient

from deployment.api import app


client = TestClient(app)


def _pick_existing_product_id() -> int:
    response = client.get("/api/products", params={"limit": 100})
    assert response.status_code == 200
    payload = response.json()
    products = payload.get("products", [])
    assert products, "Expected at least one product from /api/products"
    return int(products[0]["product_id"])


def test_api_contract_endpoints_smoke() -> None:
    onboarding_payload = {
        "skin_type": "oily",
        "concerns": ["acne", "dark_spots"],
        "sensitivity_level": "very_sensitive",
        "ingredient_exclusions": ["fragrance", "alcohol"],
        "price_range": "affordable",
        "routine_size": "basic",
        "product_interests": ["cleanser", "treatment", "sunscreen"],
    }

    response = client.post("/api/onboarding", json=onboarding_payload)
    assert response.status_code == 200
    body = response.json()
    assert "user_id" in body
    user_id = body["user_id"]

    response = client.get(
        "/api/products",
        params={
            "category": "moisturizer",
            "sort": "price_asc",
            "search": "cera",
            "min_price": 10,
            "max_price": 40,
        },
    )
    assert response.status_code == 200
    product_list = response.json()
    assert "products" in product_list
    assert "total" in product_list

    selected_product_id = _pick_existing_product_id()

    response = client.get(f"/api/products/{selected_product_id}")
    assert response.status_code == 200
    detail = response.json()
    for field in [
        "product_id",
        "product_name",
        "brand",
        "category",
        "price",
        "image_url",
        "ingredients",
    ]:
        assert field in detail

    response = client.get(
        f"/api/recommendations/{user_id}",
        params={"category": "sunscreen", "limit": 12},
    )
    assert response.status_code == 200
    recommendations = response.json()
    assert "products" in recommendations

    response = client.get(f"/api/dupes/{selected_product_id}")
    assert response.status_code == 200
    dupes = response.json()
    assert "source_product_id" in dupes
    assert "dupes" in dupes

    response = client.post(
        "/api/feedback",
        json={
            "user_id": user_id,
            "product_id": selected_product_id,
            "has_tried": False,
        },
    )
    assert response.status_code == 200
    feedback_not_tried = response.json()
    assert feedback_not_tried["success"] is True

    response = client.post(
        "/api/feedback",
        json={
            "user_id": user_id,
            "product_id": selected_product_id,
            "has_tried": True,
            "reaction": "dislike",
            "reason_tags": ["felt_greasy", "broke_me_out"],
            "free_text": "Too greasy",
        },
    )
    assert response.status_code == 200


def test_feedback_requires_reaction_when_has_tried_true() -> None:
    onboarding_payload = {
        "skin_type": "oily",
        "concerns": ["acne"],
        "sensitivity_level": "very_sensitive",
        "ingredient_exclusions": ["fragrance"],
        "price_range": "affordable",
        "routine_size": "basic",
        "product_interests": ["sunscreen"],
    }
    onboarding = client.post("/api/onboarding", json=onboarding_payload)
    user_id = onboarding.json()["user_id"]
    selected_product_id = _pick_existing_product_id()

    invalid_feedback = client.post(
        "/api/feedback",
        json={
            "user_id": user_id,
            "product_id": selected_product_id,
            "has_tried": True,
        },
    )

    assert invalid_feedback.status_code == 422
