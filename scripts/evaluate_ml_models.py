#!/usr/bin/env python3
"""
Evaluate all ML models on test data and compare performance.

This script:
1. Trains all 4 models
2. Tests on synthetic user data
3. Computes accuracy, precision, recall, F1
4. Saves results to evaluation_report.json
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from skincarelib.ml_system.ml_feedback_model import (
    LogisticRegressionFeedback,
    RandomForestFeedback,
    GradientBoostingFeedback,
    ContextualBanditFeedback,
    UserState,
)

# Paths
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)
REPORT_PATH = ARTIFACTS_DIR / "evaluation_report.json"


def create_test_data(n_users=10, n_products=50, dim=534) -> Tuple[List[UserState], np.ndarray]:
    """Create synthetic test data"""
    np.random.seed(42)
    
    # Generate product vectors
    product_vectors = np.random.randn(n_products, dim).astype(np.float32)
    
    # Create test users with varied interaction patterns
    users = []
    for user_id in range(n_users):
        user = UserState(dim=dim)
        
        # User preference: like some products, dislike others
        liked_indices = np.random.choice(n_products, size=5, replace=False)
        disliked_indices = np.random.choice(n_products, size=3, replace=False)
        
        for idx in liked_indices:
            user.add_liked(product_vectors[idx], reasons=["good_ingredients"])
        
        for idx in disliked_indices:
            user.add_disliked(product_vectors[idx], reasons=["greasy"])
        
        users.append(user)
    
    return users, product_vectors


def evaluate_model(
    model_name: str,
    model_instance,
    train_users: List[UserState],
    test_users: List[UserState],
    product_vectors: np.ndarray,
) -> Dict:
    """Train and evaluate a single model"""
    
    print(f"\n{'='*60}")
    print(f"Evaluating: {model_name}")
    print(f"{'='*60}")
    
    # Train on training users
    for user in train_users:
        success = model_instance.fit(user)
        if success:
            print(f"  ✓ Trained on user (liked: {len(user.liked_vectors)}, disliked: {len(user.disliked_vectors)})")
    
    # Test on test users
    y_true = []
    y_pred = []
    
    for test_user in test_users:
        # Get test user's likes/dislikes
        liked_count = len(test_user.liked_vectors)
        disliked_count = len(test_user.disliked_vectors)
        
        if liked_count == 0 and disliked_count == 0:
            continue
        
        # Test on liked products
        for liked_vec in test_user.liked_vectors:
            score = model_instance.predict_preference(liked_vec)
            y_true.append(1)  # True label: liked
            y_pred.append(1 if score > 0.5 else 0)
        
        # Test on disliked products
        for disliked_vec in test_user.disliked_vectors:
            score = model_instance.predict_preference(disliked_vec)
            y_true.append(0)  # True label: disliked
            y_pred.append(1 if score > 0.5 else 0)
    
    if len(y_true) == 0:
        return {
            "model": model_name,
            "status": "no_test_data",
        }
    
    # Compute metrics
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    result = {
        "model": model_name,
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "test_samples": len(y_true),
        "correct_predictions": int(sum(1 for t, p in zip(y_true, y_pred) if t == p)),
    }
    
    # Print results
    print(f"Accuracy:  {accuracy:.2%}")
    print(f"Precision: {precision:.2%}")
    print(f"Recall:    {recall:.2%}")
    print(f"F1 Score:  {f1:.2%}")
    print(f"Tested on: {len(y_true)} samples")
    
    return result


def main():
    """Run full evaluation"""
    
    print("\n" + "="*60)
    print("ML Model Evaluation Pipeline")
    print("="*60)
    
    # Create test data
    print("\n[1/3] Creating synthetic test data...")
    users, products = create_test_data(n_users=10, n_products=50, dim=534)
    train_users = users[:7]
    test_users = users[7:]
    print(f"✓ Created {len(users)} test users, {len(products)} products")
    
    # Initialize models
    print("\n[2/3] Initializing ML models...")
    models = {
        "logistic_regression": LogisticRegressionFeedback(),
        "random_forest": RandomForestFeedback(),
        "gradient_boosting": GradientBoostingFeedback(),
        "vowpal_wabbit": ContextualBanditFeedback(dim=534),
    }
    print(f"✓ Initialized {len(models)} models")
    
    # Evaluate all models
    print("\n[3/3] Evaluating models...")
    results = []
    
    for model_name, model in models.items():
        result = evaluate_model(
            model_name,
            model,
            train_users,
            test_users,
            products,
        )
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for result in results:
        if "error" not in result and "status" not in result:
            print(f"\n{result['model']}:")
            print(f"  Accuracy:  {result['accuracy']:.2%}")
            print(f"  F1 Score:  {result['f1']:.2%}")
    
    # Find best model
    evaluated = [r for r in results if "error" not in r and "status" not in r]
    if evaluated:
        best = max(evaluated, key=lambda x: x["accuracy"])
        print(f"\n🏆 Best Model: {best['model']} ({best['accuracy']:.2%} accuracy)")
    
    # Save report
    report = {
        "timestamp": str(Path.cwd()),
        "test_users": len(test_users),
        "train_users": len(train_users),
        "products_tested": len(products),
        "results": results,
    }
    
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✓ Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
