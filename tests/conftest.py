"""Pytest configuration and fixtures for tests."""

import csv
from pathlib import Path
import numpy as np


def _create_test_data():
    """Create test data files at module import time.
    
    This runs BEFORE test modules are imported, so the app sees fresh data.
    """
    
    # Generate products CSV
    csv_path = Path(__file__).parent.parent / "data" / "processed" / "products_with_signals.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate 50 test products (tests use IDs up to ~24)
    products_data = []
    for i in range(1, 51):
        product_type = ["cleanser", "moisturizer", "treatment", "sunscreen", "serum", "mask", "repair"][i % 7]
        
        # Add fragrance to even-numbered products
        has_fragrance = "fragrance" if i % 2 == 0 else ""
        
        ingredients = ["water", "glycerin", "hyaluronic acid"]
        if has_fragrance:
            ingredients.append("fragrance")
        ingredients.extend(["niacinamide", "cetyl alcohol"][:3])
        
        products_data.append({
            "product_name": f"Test {product_type.title()} {i}",
            "brand": f"TestBrand{i % 5 + 1}",
            "usage_type": "skincare",
            "category": product_type,
            "price": 15 + (i % 50),
            "image_url": f"https://example.com/product{i}.jpg",
            "ingredients": ",".join(ingredients),
        })
    
    # Always overwrite to ensure fresh state for CI
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "product_name", "brand", "usage_type", "category", "price", "image_url", "ingredients"
        ])
        writer.writeheader()
        writer.writerows(products_data)
    
    # Generate product vectors
    vectors_path = Path(__file__).parent.parent / "artifacts" / "product_vectors.npy"
    vectors_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate 50 test vectors (128 dimensions, to match PRODUCTS)
    np.random.seed(42)
    test_vectors = np.random.randn(50, 128).astype(np.float32)
    np.save(vectors_path, test_vectors)


# Execute at conftest module import time - runs BEFORE test modules import the app
_create_test_data()
