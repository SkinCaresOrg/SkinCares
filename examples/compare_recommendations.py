#!/usr/bin/env python3
"""
Compare recommendations before and after the model learns user preferences.
"""

from skincarelib.ml_system.ml_feedback_model import ContextualBanditFeedback
from skincarelib.ml_system.simulation import load_metadata, load_tokens
from pathlib import Path
import numpy as np


def compare_recommendations_before_after():
    """Show how recommendations change as model learns."""
    
    bandit = ContextualBanditFeedback(dim=602)
    root = Path(__file__).parent.parent
    
    try:
        # Load real product data
        meta = load_metadata(root)
        tokens = load_tokens(root)
    except Exception as e:
        print(f"Could not load real data: {e}")
        print("Running synthetic example instead...\n")
        compare_recommendations_synthetic(bandit)
        return
    
    # Convert tokens DataFrame into a mapping from product_id to feature vector
    tokens_df = tokens
    if "product_id" in tokens_df.columns:
        tokens_df = tokens_df.set_index("product_id")
    tokens_by_product = {prod_id: row.values for prod_id, row in tokens_df.iterrows()}
    
    # Pick first 10 test products
    test_products = list(meta["product_id"].values)[:10]
    
    # Score all products BEFORE learning
    print("BEFORE LEARNING (Random Weights):")
    print("-" * 50)
    scores_before = {}
    for prod_id in test_products:
        if prod_id in tokens_by_product:
            score = bandit.predict_preference(tokens_by_product[prod_id])
            scores_before[prod_id] = score
            product_data = meta[meta["product_id"] == prod_id].iloc[0]
            print(f"{product_data['product_name'][:30]:30} | Score: {score:.4f}")
    
    # Simulate user liking expensive products
    print("\n--- Learning Phase: User likes expensive products ---")
    expensive_count = 0
    for prod_id in list(meta["product_id"].values):
        if prod_id in tokens_by_product:
            price = float(meta[meta["product_id"] == prod_id]["price"].values[0])
            if price > 50 and expensive_count < 5:  # Expensive products
                bandit.update(tokens_by_product[prod_id], reward=1)
                print(f"✓ Learned: User likes expensive products")
                expensive_count += 1
    
    # Score all products AFTER learning
    print("\nAFTER LEARNING (Updated Weights):")
    print("-" * 50)
    scores_after = {}
    for prod_id in test_products:
        if prod_id in tokens_by_product and prod_id in scores_before:
            score = bandit.predict_preference(tokens_by_product[prod_id])
            scores_after[prod_id] = score
            product_data = meta[meta["product_id"] == prod_id].iloc[0]
            price = float(product_data["price"])
            change = score - scores_before[prod_id]
            direction = "↑" if change > 0 else "↓"
            print(f"{product_data['product_name'][:30]:30} | ${price:.2f} | {direction} {abs(change):.4f}")
    
    print("\n✅ Learning verification complete!")


def compare_recommendations_synthetic(bandit):
    """Synthetic example when real data isn't available."""
    
    # Create synthetic product vectors
    products = {
        "Expensive Moisturizer": {"vector": np.ones(602) * 0.1, "price": 75},
        "Cheap Serum": {"vector": np.ones(602) * 0.05, "price": 15},
        "Mid-Range Cream": {"vector": np.ones(602) * 0.08, "price": 45},
    }
    
    # Score BEFORE learning
    print("BEFORE LEARNING (Random Weights):")
    print("-" * 50)
    scores_before = {}
    for name, data in products.items():
        score = bandit.predict_preference(data["vector"])
        scores_before[name] = score
        print(f"{name:30} | ${data['price']:6.2f} | Score: {score:.4f}")
    
    # Learn that user likes expensive products
    print("\n--- Learning Phase: User likes expensive products ---")
    expensive_vector = np.ones(602) * 0.1
    for _ in range(5):
        bandit.update(expensive_vector, reward=1)
    print("✓ Learned: User likes expensive products")
    
    # Score AFTER learning
    print("\nAFTER LEARNING (Updated Weights):")
    print("-" * 50)
    for name, data in products.items():
        score = bandit.predict_preference(data["vector"])
        change = score - scores_before[name]
        direction = "↑" if change > 0 else "↓"
        print(f"{name:30} | ${data['price']:6.2f} | {direction} {abs(change):.4f}")
    
    print("\n✅ If expensive product scores increased, model is learning!")


if __name__ == "__main__":
    compare_recommendations_before_after()
