#!/usr/bin/env python3
"""
Verify that Vowpal Wabbit model is learning by checking prediction changes.
"""

from skincarelib.ml_system.ml_feedback_model import ContextualBanditFeedback
import numpy as np


def verify_vw_learning():
    """Verify VW is learning by checking prediction changes."""
    
    bandit = ContextualBanditFeedback(dim=602)
    
    # Create a test product vector
    test_vector = np.random.randn(602)
    test_vector = test_vector / np.linalg.norm(test_vector)
    
    # Get initial prediction (before learning)
    initial_pred = bandit.predict_preference(test_vector)
    print(f"Initial prediction (random weights): {initial_pred:.4f}")
    
    # Simulate user interactions - LIKE (reward=1)
    print("\n--- User LIKES similar products ---")
    for i in range(5):
        similar_vector = test_vector + np.random.randn(602) * 0.1
        similar_vector = similar_vector / np.linalg.norm(similar_vector)
        
        bandit.update(similar_vector, reward=1)  # User liked it
        pred = bandit.predict_preference(test_vector)
        print(f"After like {i+1}: prediction = {pred:.4f}")
    
    # Simulate user interactions - DISLIKE (reward=0)
    print("\n--- User DISLIKES different products ---")
    for i in range(5):
        different_vector = np.random.randn(602)
        different_vector = different_vector / np.linalg.norm(different_vector)
        
        bandit.update(different_vector, reward=0)  # User disliked it
        pred = bandit.predict_preference(test_vector)
        print(f"After dislike {i+1}: prediction = {pred:.4f}")
    
    final_pred = bandit.predict_preference(test_vector)
    print(f"\nFinal prediction (after learning): {final_pred:.4f}")
    print(f"Prediction changed by: {abs(final_pred - initial_pred):.4f}")
    
    if abs(final_pred - initial_pred) > 0.05:
        print("✅ MODEL IS LEARNING - Predictions changed significantly!")
        return True
    else:
        print("❌ MODEL NOT LEARNING - Predictions unchanged")
        return False


if __name__ == "__main__":
    verify_vw_learning()
