#!/usr/bin/env python3
"""
Test conditional model selection across learning stages.
Shows which model is used at each interaction level.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_model_progression():
    """Test model selection at different interaction levels"""
    
    print("\n" + "="*70)
    print("  CONDITIONAL MODEL SELECTION TEST")
    print("="*70)
    
    # Onboard user
    print("\n📝 Creating user...")
    onboard_resp = requests.post(
        f"{BASE_URL}/api/onboarding",
        json={
            "skin_type": "dry",
            "concerns": ["dryness"],
            "sensitivity_level": "somewhat_sensitive",
            "ingredient_exclusions": [],
            "price_range": "mid_range",
            "routine_size": "basic",
            "product_interests": ["moisturizer"]
        }
    )
    user_id = onboard_resp.json()["user_id"]
    print(f"✅ User created: {user_id}")
    
    # Get products
    products_resp = requests.get(f"{BASE_URL}/api/products?limit=10")
    products = products_resp.json()["products"]
    
    # Test scenarios: different interaction levels
    test_cases = [
        ("Early Stage", 1, [(products[0]["product_id"], "like")]),
        ("Early Stage", 3, [(products[1]["product_id"], "dislike"), (products[2]["product_id"], "like")]),
        ("Mid Stage", 10, [(products[3+i]["product_id"], "like" if i % 2 == 0 else "dislike") for i in range(7)]),
        ("Experienced", 25, []),  # Will be fed 15 more total
    ]
    
    print("\n" + "="*70)
    print("  MODEL SELECTION ACROSS LEARNING STAGES")
    print("="*70)
    print(f"{'Stage':<15} {'Interactions':<15} {'Model Used':<30}")
    print("-" * 70)
    
    for stage_name, target_interactions, feedbacks in test_cases:
        # Submit feedbacks to reach target interaction count
        for prod_id, reaction in feedbacks:
            requests.post(
                f"{BASE_URL}/api/feedback",
                json={
                    "user_id": user_id,
                    "product_id": prod_id,
                    "has_tried": True,
                    "reaction": reaction,
                    "reason_tags": [],
                    "free_text": ""
                }
            )
        
        # Get current state
        state_resp = requests.get(f"{BASE_URL}/api/debug/user-state/{user_id}")
        current_interactions = state_resp.json()["interactions"]
        
        # Get a product score to see which model is used
        if current_interactions > 0:
            score_resp = requests.get(
                f"{BASE_URL}/api/debug/product-score/{user_id}/{products[0]['product_id']}"
            )
            model_used = score_resp.json()["model_used"]
        else:
            model_used = "default"
        
        print(f"{stage_name:<15} {current_interactions:<15} {model_used:<30}")
    
    print("\n" + "="*70)
    print("  MODEL PROGRESSION SUMMARY")
    print("="*70)
    print("""
Stage Configuration:
├─ Interactions < 5:    LogisticRegression (Early Stage)
├─ Interactions 5-19:   RandomForest (Mid Stage)  
└─ Interactions >= 20:  ContextualBandit (Online Learning)

✅ Benefits:
  • Early: Fast feedback for new users
  • Mid: Better accuracy with more data
  • Experienced: Exploration + exploitation balance
""")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        test_model_progression()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
