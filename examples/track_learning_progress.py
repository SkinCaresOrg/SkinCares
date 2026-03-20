#!/usr/bin/env python3
"""
Track learning progress across multiple user sessions.
"""

from skincarelib.ml_system.ml_feedback_model import ContextualBanditFeedback
import numpy as np


def track_learning_sessions():
    """Simulate multiple user sessions and track learning progress."""
    
    bandit = ContextualBanditFeedback(dim=602)
    
    # Simulate 3 user sessions
    sessions = 3
    interactions_per_session = 10
    
    print("Tracking VW Learning Across Sessions\n")
    print(f"{'Session':<10} {'Interaction':<15} {'Avg Prediction':<20} {'Variance':<15}")
    print("-" * 60)
    
    for session_num in range(sessions):
        predictions = []
        
        for interaction in range(interactions_per_session):
            # Generate user interaction
            if interaction % 2 == 0:
                # Like - positive signal
                vector = np.random.randn(602) * 0.5  # Clustered around origin
                reward = 1
            else:
                # Dislike - negative signal
                vector = np.random.randn(602) * 1.5  # Spread out
                reward = 0
            
            vector = vector / np.linalg.norm(vector)
            bandit.update(vector, reward=reward)
            
            # Get predictions on properly normalized test vectors
            test_vectors = []
            for _ in range(5):
                v = np.random.randn(602)
                v = v / np.linalg.norm(v)
                test_vectors.append(v)
            preds = [bandit.predict_preference(v) for v in test_vectors]
            predictions.extend(preds)
        
        avg_pred = np.mean(predictions)
        var_pred = np.var(predictions)
        
        print(f"Session {session_num+1:<6} {'-':<14} {avg_pred:<20.4f} {var_pred:<15.6f}")
    
    print("\n✅ If variance DECREASES across sessions, the model is learning!")


if __name__ == "__main__":
    track_learning_sessions()
