"""Pytest configuration and fixtures for tests."""

import csv
from pathlib import Path
import pytest


@pytest.fixture(scope="session", autouse=True)
def ensure_test_products_csv():
    """Ensure products CSV exists with minimal test data for CI environments."""
    csv_path = Path(__file__).parent.parent / "data" / "processed" / "products_with_signals.csv"
    
    # If CSV already exists, don't overwrite it
    if csv_path.exists():
        return
    
    # Create directories if needed
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate minimal test products (30 products)
    products_data = []
    for i in range(1, 31):
        product_type = ["cleanser", "moisturizer", "treatment", "sunscreen", "serum", "mask"][i % 6]
        
        # Add fragrance to half of them for testing
        has_fragrance = "fragrance" if i % 2 == 0 else ""
        
        ingredients = ["water", "glycerin", "hyaluronic acid"]
        if has_fragrance:
            ingredients.append("fragrance")
        ingredients.extend(["niacinamide", "cetyl alcohol"][:3])  # Max 5
        
        products_data.append({
            "product_name": f"Test {product_type.title()} {i}",
            "brand": f"TestBrand{i % 3 + 1}",
            "usage_type": "skincare",
            "category": product_type,
            "price": 15 + (i % 50),
            "image_url": f"https://example.com/product{i}.jpg",
            "ingredients": ",".join(ingredients),
        })
    
    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "product_name", "brand", "usage_type", "category", "price", "image_url", "ingredients"
        ])
        writer.writeheader()
        writer.writerows(products_data)
    
    print(f"✓ Generated test products CSV at {csv_path}")


@pytest.fixture(scope="session", autouse=True)
def ensure_test_vectors():
    """Ensure product vectors exist for CI environments."""
    import numpy as np
    
    vectors_path = Path(__file__).parent.parent / "artifacts" / "product_vectors.npy"
    
    # If vectors already exist, don't overwrite them
    if vectors_path.exists():
        return
    
    # Create directories if needed
    vectors_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate minimal test vectors (30 products, 128 dimensions)
    # This matches what the app expects
    np.random.seed(42)
    test_vectors = np.random.randn(30, 128).astype(np.float32)
    
    np.save(vectors_path, test_vectors)
    print(f"✓ Generated test vectors at {vectors_path}")
