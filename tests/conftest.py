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
    
    # Generate 300+ test products to ensure enough diversity and coverage
    products_data = []
    for i in range(1, 301):
        # Distribute across 7 categories evenly: each gets ~28 products
        product_type = ["cleanser", "moisturizer", "treatment", "sunscreen", "serum", "mask", "repair"][i % 7]
        
        # Base ingredients - use benign ingredients for most products
        ingredients = ["water", "glycerin", "hyaluronic acid"]
        
        # Add fragrance only to even-numbered products (for fragrance exclusion testing)
        if i % 2 == 0:
            ingredients.append("fragrance")
        
        # Add other ingredients varied by product
        if i % 3 == 0:
            ingredients.append("niacinamide")
        if i % 5 == 0:
            ingredients.append("squalane")
        if i % 7 == 0:
            ingredients.append("peptides")
        
        products_data.append({
            "product_name": f"Test {product_type.title()} {i}",
            "brand": f"TestBrand{i % 10 + 1}",
            "usage_type": "skincare",
            "category": product_type,
            "price": 15 + (i % 80),
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
    
    # Generate 300 test vectors (128 dimensions, to match PRODUCTS)
    np.random.seed(42)
    test_vectors = np.random.randn(300, 128).astype(np.float32)
    np.save(vectors_path, test_vectors)


# Execute at conftest module import time - runs BEFORE test modules import the app
_create_test_data()
