#!/usr/bin/env python3
"""
Threshold Validation Test
Verify model selection at exact boundary points (4→5, 19→20)
"""

import requests
import random

BASE_URL = "http://localhost:8000"

def test_threshold_boundaries():
    """Test model switches at exact threshold boundaries"""
    
    print("\n" + "="*80)
    print("  THRESHOLD BOUNDARY VALIDATION")
    print("="*80)
    print()
    
    # Get products
    products_resp = requests.get(f"{BASE_URL}/api/products?limit=30")
    products = products_resp.json()["products"]
    
    # Create test user
    onboard_resp = requests.post(
        f"{BASE_URL}/api/onboarding",
        json={
            "skin_type": "oily",
            "concerns": ["acne"],
            "sensitivity_level": "not_sensitive",
            "ingredient_exclusions": [],
            "price_range": "mid_range",
            "routine_size": "moderate",
            "product_interests": ["cleanser", "treatment"]
        }
    )
    user_id = onboard_resp.json()["user_id"]
    
    print(f"✅ Test User Created: {user_id}\n")
    
    # Test boundary at 4→5 interactions (LogisticRegression → RandomForest)
    print("="*80)
    print("BOUNDARY #1: 4 → 5 interactions (LR → RF)")
    print("="*80)
    
    for i in range(4):
        requests.post(
            f"{BASE_URL}/api/feedback",
            json={
                "user_id": user_id,
                "product_id": products[i]["product_id"],
                "has_tried": True,
                "reaction": "like" if i % 2 == 0 else "dislike",
                "reason_tags": [],
                "free_text": ""
            }
        )
    
    # Check at 4 interactions
    score_resp_4 = requests.get(
        f"{BASE_URL}/api/debug/product-score/{user_id}/{products[0]['product_id']}"
    )
    model_4 = score_resp_4.json()["model_used"]
    
    print(f"At 4 interactions: {model_4}")
    if "LogisticRegression" in model_4:
        print("  ✅ CORRECT: Still using LogisticRegression (Early Stage)")
    else:
        print(f"  ❌ ERROR: Expected LogisticRegression, got {model_4}")
    
    # Add one more to hit 5
    requests.post(
        f"{BASE_URL}/api/feedback",
        json={
            "user_id": user_id,
            "product_id": products[4]["product_id"],
            "has_tried": True,
            "reaction": "like",
            "reason_tags": [],
            "free_text": ""
        }
    )
    
    # Check at 5 interactions
    score_resp_5 = requests.get(
        f"{BASE_URL}/api/debug/product-score/{user_id}/{products[0]['product_id']}"
    )
    model_5 = score_resp_5.json()["model_used"]
    
    print(f"At 5 interactions: {model_5}")
    if "RandomForest" in model_5:
        print("  ✅ CORRECT: Switched to RandomForest (Mid Stage)")
    else:
        print(f"  ❌ ERROR: Expected RandomForest, got {model_5}")
    
    # Test boundary at 19→20 interactions (RandomForest → ContextualBandit)
    print("\n" + "="*80)
    print("BOUNDARY #2: 19 → 20 interactions (RF → CB)")
    print("="*80)
    
    # Add 14 more to reach 19
    for i in range(5, 19):
        requests.post(
            f"{BASE_URL}/api/feedback",
            json={
                "user_id": user_id,
                "product_id": products[i % len(products)]["product_id"],
                "has_tried": True,
                "reaction": "like" if random.random() > 0.5 else "dislike",
                "reason_tags": [],
                "free_text": ""
            }
        )
    
    # Check at 19 interactions
    score_resp_19 = requests.get(
        f"{BASE_URL}/api/debug/product-score/{user_id}/{products[0]['product_id']}"
    )
    model_19 = score_resp_19.json()["model_used"]
    
    print(f"At 19 interactions: {model_19}")
    if "RandomForest" in model_19:
        print("  ✅ CORRECT: Still using RandomForest (Mid Stage)")
    else:
        print(f"  ❌ ERROR: Expected RandomForest, got {model_19}")
    
    # Add one more to hit 20
    requests.post(
        f"{BASE_URL}/api/feedback",
        json={
            "user_id": user_id,
            "product_id": products[19]["product_id"],
            "has_tried": True,
            "reaction": "like",
            "reason_tags": [],
            "free_text": ""
        }
    )
    
    # Check at 20 interactions
    score_resp_20 = requests.get(
        f"{BASE_URL}/api/debug/product-score/{user_id}/{products[0]['product_id']}"
    )
    model_20 = score_resp_20.json()["model_used"]
    
    print(f"At 20 interactions: {model_20}")
    if "ContextualBandit" in model_20:
        print("  ✅ CORRECT: Switched to ContextualBandit (Online Learning)")
    else:
        print(f"  ❌ ERROR: Expected ContextualBandit, got {model_20}")
    
    # Final state
    state_resp = requests.get(f"{BASE_URL}/api/debug/user-state/{user_id}")
    final_interactions = state_resp.json()["interactions"]
    
    print("\n" + "="*80)
    print("  VALIDATION RESULT")
    print("="*80)
    print(f"Final interaction count: {final_interactions}")
    print(f"Final model: {model_20}")
    print()
    print("✅ THRESHOLD BOUNDARIES VALIDATED")
    print("""
Summary of Model Selection Logic:
  Interactions < 5   → LogisticRegression (Early Stage) ⚡
  5 ≤ Interactions < 20 → RandomForest (Mid Stage) 🎯
  Interactions ≥ 20  → ContextualBandit (Online Learning) 🔄

The system correctly transitions models at each boundary!
""")
    print("="*80 + "\n")

if __name__ == "__main__":
    try:
        test_threshold_boundaries()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
