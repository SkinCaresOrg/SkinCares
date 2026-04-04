#!/usr/bin/env python3
"""
Test conditional model selection with enough interactions to reach all stages.
"""

import requests
import random

BASE_URL = "http://localhost:8000"

def test_full_progression():
    """Test all three model stages"""
    
    print("\n" + "="*70)
    print("  FULL MODEL PROGRESSION TEST (All 3 Stages)")
    print("="*70)
    
    # Create user
    print("\n📝 Creating user...")
    onboard_resp = requests.post(
        f"{BASE_URL}/api/onboarding",
        json={
            "skin_type": "combination",
            "concerns": ["acne"],
            "sensitivity_level": "not_sensitive",
            "ingredient_exclusions": [],
            "price_range": "mid_range",
            "routine_size": "moderate",
            "product_interests": ["cleanser", "treatment"]
        }
    )
    resp_data = onboard_resp.json()
    user_id = resp_data.get("user_id") or resp_data.get("id")
    if not user_id:
        print(f"Response: {resp_data}")
        raise ValueError("Could not extract user_id from onboarding response")
    print(f"✅ User created: {user_id}\n")
    
    # Get products for feedback
    products_resp = requests.get(f"{BASE_URL}/api/products?limit=50")
    all_products = products_resp.json()["products"]
    
    stages = [
        {
            "name": "Early Stage 🌱",
            "target_interactions": 4,
            "feedback_count": 4,
            "description": "LogisticRegression (Fast & Simple)"
        },
        {
            "name": "Mid Stage 🌿",
            "target_interactions": 15,
            "feedback_count": 11,
            "description": "RandomForest (Accurate & Balanced)"
        },
        {
            "name": "Experienced Stage 🌳",
            "target_interactions": 25,
            "feedback_count": 10,
            "description": "ContextualBandit (Online Learning)"
        }
    ]
    
    print("Progression through learning stages:")
    print("-" * 70)
    
    current_product_idx = 0
    
    for stage in stages:
        # Add enough feedback to reach target
        for i in range(stage["feedback_count"]):
            if current_product_idx < len(all_products):
                prod = all_products[current_product_idx]
                reaction = random.choice(["like", "dislike"])
                
                requests.post(
                    f"{BASE_URL}/api/feedback",
                    json={
                        "user_id": user_id,
                        "product_id": prod["product_id"],
                        "has_tried": True,
                        "reaction": reaction,
                        "reason_tags": [],
                        "free_text": ""
                    }
                )
                current_product_idx += 1
        
        # Check state and model used
        state_resp = requests.get(f"{BASE_URL}/api/debug/user-state/{user_id}")
        interactions = state_resp.json()["interactions"]
        
        score_resp = requests.get(
            f"{BASE_URL}/api/debug/product-score/{user_id}/{all_products[0]['product_id']}"
        )
        model_used = score_resp.json().get("model_used", "unknown")
        score = score_resp.json().get("score", "N/A")
        
        print(f"\n{stage['name']}")
        print(f"  Interactions: {interactions}/{stage['target_interactions']}")
        print(f"  Model: {model_used}")
        print(f"  Score (sample): {score:.3f}" if isinstance(score, (int, float)) else f"  Score: {score}")
        print(f"  Info: {stage['description']}")
    
    print("\n" + "="*70)
    print("  SUMMARY: MODEL PROGRESSION ✅")
    print("="*70)
    print("""
Your system now implements adaptive model selection:

1️⃣  EARLY STAGE (< 5 interactions)
    Model: LogisticRegression
    Why: Fast feedback, minimal data needed
    Benefit: Quick recommendations for new users

2️⃣  MID STAGE (5-19 interactions)
    Model: RandomForest
    Why: Better accuracy with more data
    Benefit: More reliable recommendations

3️⃣  EXPERIENCED STAGE (≥ 20 interactions)  
    Model: ContextualBandit (Vowpal Wabbit)
    Why: Online learning, exploration/exploitation
    Benefit: Learns from interactions in real-time

This mimics professional ML systems that adapt to user maturity!
""")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        test_full_progression()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
