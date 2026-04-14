from skincarelib.ml_system.handler import _find_product_id, _get_metadata
from skincarelib.models.dupe_finder import find_dupes

# 🔍 STEP 1: find product id
query = "cerave cleanser"
product_id = _find_product_id(query)

print("Product ID:", product_id)

# 🔍 STEP 2: see the actual product
metadata = _get_metadata()
product = metadata[metadata["product_id"] == product_id]
print("\nFOUND PRODUCT:")
print(product[["product_name", "brand", "price"]])

# 🔍 STEP 3: run dupe finder
results = find_dupes(product_id)

print("\nDUPES:")
print(results[["product_name", "brand", "price"]].head(5))
