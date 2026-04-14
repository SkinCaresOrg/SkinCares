from fastapi.testclient import TestClient
import importlib

from deployment.api import app


api_module = importlib.import_module("deployment.api.app")


client = TestClient(app)


def _ensure_catalog_for_tests() -> None:
    if api_module.PRODUCTS:
        return

    api_module.PRODUCTS[1] = api_module.ProductDetail(
        product_id=1,
        product_name="CI Fallback Moisturizer",
        brand="SkinCares",
        category="moisturizer",
        price=19.99,
        image_url="",
        short_description="",
        rating_count=0,
        wishlist_supported=True,
        ingredients=["water", "glycerin"],
        ingredient_highlights=["glycerin"],
        concerns_targeted=[],
        skin_types_supported=[],
    )


def _pick_existing_product_id() -> int:
    response = client.get("/api/products", params={"limit": 100})
    assert response.status_code == 200
    payload = response.json()
    products = payload.get("products", [])
    if not products:
        _ensure_catalog_for_tests()
        response = client.get("/api/products", params={"limit": 100})
        assert response.status_code == 200
        payload = response.json()
        products = payload.get("products", [])
    assert products, "Expected at least one product from /api/products"
    return int(products[0]["product_id"])




