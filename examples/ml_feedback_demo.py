#!/usr/bin/env python3
"""
Example script demonstrating ML-based feedback models.

BEFORE: Simple weighted average
AFTER: Logistic Regression, Random Forest, Gradient Boosting, Contextual Bandit

Usage:
    # Run with logistic regression
    python examples/ml_feedback_demo.py --model logistic
    
    # Run with gradient boosting
    python examples/ml_feedback_demo.py --model gradient_boosting
    
    # Compare all models
    python examples/ml_feedback_demo.py --compare
"""

import argparse
import sys
from pathlib import Path

import numpy as np

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from skincarelib.ml_system.feedback_update import (
    UserState,
    update_user_state,
    compute_user_vector,
    create_feedback_model,
)


def create_sample_data(n_products=100, dim=50):
    """Create sample product vectors."""
    np.random.seed(42)
    vectors = np.random.randn(n_products, dim).astype(np.float32)
    # Normalize
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors


def demo_single_model(model_type, product_vectors):
    """Demonstrate a single model."""
    dim = product_vectors.shape[1]
    
    print(f"\n{'='*60}")
    print(f"Demo: {model_type.upper()}")
    print(f"{'='*60}")
    
    # Create user and add interactions
    user = UserState(dim=dim)
    
    interactions = [
        ("like", 0, ["hydrating", "lightweight"]),
        ("like", 5, ["absorbs_quickly"]),
        ("dislike", 15, ["too_greasy"]),
        ("irritation", 25, ["caused_rash"]),
        ("like", 35, ["good_value"]),
    ]
    
    print("\nUser interactions:")
    for reaction, prod_idx, reasons in interactions:
        print(f"  {reaction.upper():<10} Product {prod_idx:3d} | {', '.join(reasons)}")
        update_user_state(user, reaction, product_vectors[prod_idx], reasons)
    
    print(f"\nUser Summary:")
    print(f"  Total interactions: {user.interactions}")
    print(f"  Liked: {len(user.liked_vectors)}")
    print(f"  Disliked: {len(user.disliked_vectors)}")
    print(f"  Irritation: {len(user.irritation_vectors)}")
    
    # Score products with selected model
    if model_type == "weighted_avg":
        # Use legacy method
        user_vec = compute_user_vector(user)
        scores = np.dot(product_vectors, user_vec)
        # Convert to probabilities
        scores = (scores + 1) / 2  # Simple scaling to [0, 1]
    elif model_type == "contextual_bandit":
        # Bandit learns incrementally
        from skincarelib.ml_system.ml_feedback_model import ContextualBanditFeedback
        model = ContextualBanditFeedback(dim=dim, learning_rate=0.01)
        
        # Train on liked/disliked interactions
        for vec in user.liked_vectors:
            model.update(vec, reward=1)
        for vec in user.disliked_vectors:
            model.update(vec, reward=0)
        
        print(f"\n  ✓ Bandit trained with {user.interactions} interactions")
        print(f"  Total updates: {model.total_updates}")
        
        # Score all products
        scores = model.score_products(product_vectors)
    else:
        # Train ML model
        model = create_feedback_model(model_type=model_type, dim=dim)
        success = model.fit(user)
        
        if not success:
            print("  ⚠️  Insufficient data to train model")
            return
        
        print(f"\n  ✓ Model trained successfully")
        
        # Score all products
        scores = model.score_products(product_vectors)
        
        # Show feature importance if available
        if hasattr(model, 'get_feature_importance'):
            importance = model.get_feature_importance()
            top_indices = np.argsort(importance)[-3:][::-1]
            print(f"\n  Top 3 important features:")
            for i, idx in enumerate(top_indices, 1):
                print(f"    {i}. Feature {idx}: {importance[idx]:.4f}")
    
    # Show top recommendations
    top_indices = np.argsort(scores)[-10:][::-1]
    print(f"\nTop 10 recommended products:")
    for rank, idx in enumerate(top_indices, 1):
        score = scores[idx]
        print(f"  {rank:2d}. Product {idx:3d} | Score: {score:.4f}")
    
    return scores


def compare_models(product_vectors):
    """Compare all models on same data."""
    print(f"\n{'='*60}")
    print("MODEL COMPARISON")
    print(f"{'='*60}")
    
    dim = product_vectors.shape[1]
    n_products = len(product_vectors)
    
    # Create user with standard interactions
    user = UserState(dim=dim)
    
    interactions = [
        ("like", 0, ["hydrating"]),
        ("like", 10, ["absorbs_quickly"]),
        ("dislike", 30, ["greasy"]),
        ("like", 50, ["good_value"]),
    ]
    
    for reaction, prod_idx, reasons in interactions:
        update_user_state(user, reaction, product_vectors[prod_idx], reasons)
    
    print(f"\nScenario: User with {len(interactions)} interactions")
    
    # Score with each model
    model_types = ["weighted_avg", "logistic", "random_forest", "gradient_boosting", "contextual_bandit"]
    scores_dict = {}
    
    for model_type in model_types:
        try:
            if model_type == "weighted_avg":
                user_vec = compute_user_vector(user)
                scores = np.dot(product_vectors, user_vec)
                scores = (scores + 1) / 2
            elif model_type == "contextual_bandit":
                # Bandit requires incremental updates, not batch training
                from skincarelib.ml_system.ml_feedback_model import ContextualBanditFeedback
                bandit = ContextualBanditFeedback(dim=dim)
                # Train on user interactions
                for vec in user.liked_vectors:
                    bandit.update(vec, reward=1)
                for vec in user.disliked_vectors:
                    bandit.update(vec, reward=0)
                scores = bandit.score_products(product_vectors)
            else:
                model = create_feedback_model(model_type=model_type, dim=dim)
                if not model.fit(user):
                    scores = np.ones(n_products) * 0.5
                else:
                    scores = model.score_products(product_vectors)
            
            scores_dict[model_type] = scores
            print(f"  ✓ {model_type:<20} Mean score: {np.mean(scores):.4f}")
        except Exception as e:
            print(f"  ✗ {model_type:<20} Error: {str(e)[:50]}")
    
    # Show correlation between models
    if len(scores_dict) > 1:
        print(f"\nTop products by model (Top 5):")
        for model_type, scores in scores_dict.items():
            top_indices = np.argsort(scores)[-5:][::-1]
            top_str = ", ".join(f"{idx}" for idx in top_indices)
            print(f"  {model_type:<20} Products: [{top_str}]")


def main():
    parser = argparse.ArgumentParser(
        description="Demonstrate ML-based feedback models vs weighted average"
    )
    parser.add_argument(
        "--model",
        choices=["weighted_avg", "logistic", "random_forest", "gradient_boosting", "contextual_bandit"],
        default="logistic",
        help="Model to demonstrate (default: logistic)"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare all models"
    )
    parser.add_argument(
        "--n_products",
        type=int,
        default=100,
        help="Number of products (default: 100)"
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=50,
        help="Feature dimension (default: 50)"
    )
    
    args = parser.parse_args()
    
    # Create sample data
    print("Creating sample data...")
    product_vectors = create_sample_data(args.n_products, args.dim)
    print(f"  Generated {args.n_products} products with {args.dim} features")
    
    if args.compare:
        compare_models(product_vectors)
    else:
        demo_single_model(args.model, product_vectors)
    
    print(f"\n{'='*60}")
    print("Demo completed!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
