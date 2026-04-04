#!/usr/bin/env python3
"""
Test script to verify ModelMonitor real-time updates
Simulates user onboarding, providing feedback, and checking state changes
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
USER_ID = None  # Will be set after onboarding

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def onboard_user():
    """Create a new user via onboarding endpoint"""
    global USER_ID
    print_section("STEP 1: Onboard User")
    
    payload = {
        "skin_type": "dry",
        "concerns": ["dryness", "redness"],
        "sensitivity_level": "very_sensitive",
        "ingredient_exclusions": [],
        "price_range": "mid_range",
        "routine_size": "basic",
        "product_interests": ["moisturizer", "cleanser"]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/onboarding",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if response.status_code == 200:
        USER_ID = result["user_id"]
        print(f"\n✅ User created: {USER_ID}")
    
    return result

def get_model_state():
    """Fetch current model state from debug endpoint"""
    response = requests.get(f"{BASE_URL}/api/debug/user-state/{USER_ID}")
    if response.status_code == 200:
        return response.json()
    return None

def submit_feedback(product_id, reaction):
    """Submit feedback for a product"""
    payload = {
        "user_id": USER_ID,
        "product_id": product_id,
        "has_tried": True,
        "reaction": reaction,
        "reason_tags": [],
        "free_text": f"Test feedback for {reaction}"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/feedback",
        json=payload
    )
    
    return response.status_code == 200

def monitor_realtime():
    """Monitor real-time state changes as we submit feedback"""
    print_section("STEP 2: Get Initial Model State")
    
    initial_state = get_model_state()
    if not initial_state:
        print("❌ ERROR: Could not fetch initial model state")
        return False
    
    print("Initial Model State:")
    print(f"  Interactions: {initial_state['interactions']}")
    print(f"  Liked: {initial_state['liked_count']}")
    print(f"  Disliked: {initial_state['disliked_count']}")
    print(f"  Irritation: {initial_state['irritation_count']}")
    print(f"  Has Training Data: {initial_state['has_training_data']}")
    print(f"  Model Ready: {initial_state['model_ready']}")
    
    print_section("STEP 3: Submit Feedback & Monitor Real-time Updates")
    
    # Get some product IDs to test with
    response = requests.get(f"{BASE_URL}/api/products?limit=5")
    products = response.json()["products"][:5]
    
    if not products:
        print("❌ ERROR: Could not fetch products")
        return False
    
    test_cases = [
        (products[0]["product_id"], "like"),
        (products[1]["product_id"], "dislike"),
        (products[2]["product_id"], "like"),
        (products[3]["product_id"], "dislike"),
        (products[4]["product_id"], "irritation"),
    ]
    
    success = True
    for i, (product_id, reaction) in enumerate(test_cases, 1):
        print(f"\n📝 Feedback #{i}: {reaction.upper()} on product {product_id}")
        
        # Submit feedback
        if not submit_feedback(product_id, reaction):
            print("❌ Failed to submit feedback")
            success = False
            continue
        
        # Small delay to let backend process
        time.sleep(0.5)
        
        # Fetch updated state
        state = get_model_state()
        if not state:
            print("\u274c Failed to fetch updated state")
            success = False
            continue
        
        # Display changes
        print("  ✓ Feedback submitted")
        print(f"  Total Interactions: {state['interactions']}")
        print(f"  Liked Count: {state['liked_count']}")
        print(f"  Disliked Count: {state['disliked_count']}")
        print(f"  Irritation Count: {state['irritation_count']}")
        print(f"  Has Training Data: {state['has_training_data']}")
        print(f"  Model Ready: {state['model_ready']} {'✓' if state['model_ready'] else ''}")
    
    print_section("STEP 4: Verify Real-time Updates")
    
    final_state = get_model_state()
    if not final_state:
        print("❌ ERROR: Could not fetch final state")
        return False
    
    # Check expectations
    checks = [
        ("Interactions increased", final_state['interactions'] > 0, f"{final_state['interactions']} > 0"),
        ("Liked count updated", final_state['liked_count'] >= 2, f"{final_state['liked_count']} >= 2"),
        ("Disliked count updated", final_state['disliked_count'] >= 2, f"{final_state['disliked_count']} >= 2"),
        ("Irritation count updated", final_state['irritation_count'] >= 1, f"{final_state['irritation_count']} >= 1"),
        ("Training data available", final_state['has_training_data'] == True, "True"),
        ("Model ready flag set", final_state['model_ready'] == True, "True"),
    ]
    
    print("Verification Results:")
    for check_name, result, details in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}: {details}")
        if not result:
            success = False
    
    return success

def test_model_scoring():
    """Test that model can score products"""
    print_section("STEP 5: Test Model Scoring")
    
    response = requests.get(f"{BASE_URL}/api/products?limit=3")
    products = response.json()["products"][:3]
    
    for product in products:
        score_response = requests.get(
            f"{BASE_URL}/api/debug/product-score/{USER_ID}/{product['product_id']}"
        )
        
        if score_response.status_code == 200:
            score_data = score_response.json()
            print(f"Product {product['product_name']}:")
            print(f"  Score: {score_data.get('score', 'N/A')}")
            print(f"  Model Used: {score_data.get('model_used', 'N/A')}")
        else:
            error_detail = score_response.json() if score_response.text else "No error detail"
            print(f"❌ Failed to get score for product {product['product_id']}: {score_response.status_code}")
            print(f"   Error: {error_detail}")

if __name__ == "__main__":
    try:
        print("\n🚀 REAL-TIME MODEL MONITORING TEST")
        print(f"Testing user: {USER_ID}")
        
        onboard_user()
        success = monitor_realtime()
        test_model_scoring()
        
        print("\n" + "="*60)
        if success:
            print("✅ ALL CHECKS PASSED - Real-time monitoring is working!")
        else:
            print("⚠️  SOME CHECKS FAILED - See details above")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
