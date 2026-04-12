#!/usr/bin/env python3
"""
Verification script to check the API response format for the products endpoint.
This script tests the /api/products endpoint directly without needing Docker.
"""

import sys
import json
from pathlib import Path

# Add the deployment directory to the path
sys.path.insert(0, str(Path(__file__).parent / "deployment"))

# Import the FastAPI app
from api.app import app, PRODUCTS

# Test the products endpoint
print("=" * 80)
print("SkinCares API Response Verification")
print("=" * 80)

# Check if products loaded
print(f"\n1. Products Data Status:")
print(f"   - Total products loaded: {len(PRODUCTS)}")
if PRODUCTS:
    first_product = list(PRODUCTS.values())[0]
    print(f"   - First product ID: {first_product.product_id}")
    print(f"   - Product name: {first_product.product_name}")
    print(f"\n2. First Product Fields (ProductDetail):")
    for field, value in first_product.__dict__.items():
        if isinstance(value, list) and len(value) > 5:
            print(f"   - {field}: [{value[0]}, ...] (length: {len(value)})")
        else:
            print(f"   - {field}: {value}")
else:
    print("   WARNING: No products loaded! Check the CSV file path.")
    sys.exit(1)

# Test the endpoint using TestClient
from fastapi.testclient import TestClient

client = TestClient(app)

print(f"\n3. Testing GET /api/products endpoint:")
response = client.get("/api/products?page=1&limit=5")
print(f"   - Response status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"   - Response keys: {list(data.keys())}")
    print(f"   - Items count: {len(data.get('items', []))}")
    print(f"   - Products count: {len(data.get('products', []))}")
    print(f"   - Total: {data.get('total')}")
    print(f"   - Has more: {data.get('hasMore')}")
    print(f"   - Page: {data.get('page')}")
    
    # Check first item structure
    items = data.get("items", [])
    if items:
        print(f"\n4. First Product Response (ProductCard):")
        first_item = items[0]
        for key, value in first_item.items():
            print(f"   - {key}: {value}")
        
        # Verify required fields
        required_fields = [
            "product_id",
            "product_name",
            "brand",
            "category",
            "price",
            "image_url"
        ]
        missing_fields = [f for f in required_fields if f not in first_item]
        if missing_fields:
            print(f"\n   WARNING: Missing fields: {missing_fields}")
        else:
            print(f"\n   ✓ All required fields present")
            
        # Check field types
        print(f"\n5. Field Type Verification:")
        expected_types = {
            "product_id": int,
            "product_name": str,
            "brand": str,
            "category": str,
            "price": (int, float),
            "image_url": str,
        }
        for field, expected_type in expected_types.items():
            actual_type = type(first_item[field])
            is_correct = isinstance(first_item[field], expected_type)
            status = "✓" if is_correct else "✗"
            print(f"   {status} {field}: {actual_type.__name__} (expected: {expected_type})")
    
    print(f"\n6. Response Format Check:")
    print(f"   ✓ Response has both 'items' and 'products': {'items' in data and 'products' in data}")
    print(f"   ✓ Both contain same data: {data.get('items') == data.get('products')}")
    
    # Show formatted response
    print(f"\n7. Full Response (shortened):")
    print(json.dumps({
        "items_count": len(data.get("items", [])),
        "products_count": len(data.get("products", [])),
        "total": data.get("total"),
        "hasMore": data.get("hasMore"),
        "page": data.get("page"),
        "first_item_keys": list(items[0].keys()) if items else []
    }, indent=2))
    
else:
    print(f"   ERROR: Got status code {response.status_code}")
    print(f"   Response: {response.text}")
    sys.exit(1)

print("\n" + "=" * 80)
print("✓ API response format verification complete!")
print("=" * 80)
