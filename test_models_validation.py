#!/usr/bin/env python
"""
Comprehensive test of LightGBM and XLearn models with real product data
"""
import numpy as np
from deployment.api.app import PRODUCT_VECTORS, get_best_model
from skincarelib.ml_system.ml_feedback_model import (
    UserState,
    LightGBMFeedback,
    XLearnFeedback,
    LogisticRegressionFeedback,
    RandomForestFeedback,
)

print("=" * 60)
print("COMPREHENSIVE MODEL VALIDATION")
print("=" * 60)

# Setup test data
dim = PRODUCT_VECTORS.shape[1]

# If PRODUCT_VECTORS is empty, create synthetic test data
if PRODUCT_VECTORS.shape[0] == 0:
    print("⚠️  PRODUCT_VECTORS is empty, using synthetic test data")
    sample_products = np.random.randn(100, dim).astype(np.float32)
else:
    sample_products = PRODUCT_VECTORS[:100]

print("\n📊 Test Setup:")
print(f"   - Product vector dimension: {dim}")
print(f"   - Sample products: {sample_products.shape[0]}")

# Create user state with diverse feedback
user = UserState(dim)
for i in range(10):
    user.add_liked(sample_products[i * 5], reasons=[f"reason_{i}"])
    user.add_disliked(sample_products[i * 5 + 1], reasons=[f"reason_{i}"])
    user.add_irritation(sample_products[i * 5 + 2], reasons=[f"reason_{i}"])

print("\n👤 User Feedback Summary:")
print(f"   - Total interactions: {user.interactions}")
print(f"   - Liked products: {user.liked_count}")
print(f"   - Disliked products: {user.disliked_count}")
print(f"   - Irritation triggers: {user.irritation_count}")

# Test each model
models_to_test = [
    ("LogisticRegression", LogisticRegressionFeedback()),
    ("RandomForest", RandomForestFeedback()),
    ("LightGBM", LightGBMFeedback()),
]

# Try to add XLearn if available
try:
    models_to_test.append(("XLearn", XLearnFeedback(model_type="linear")))
except ImportError:
    print("ℹ️  XLearn not installed - skipping from test")
    print("   Install with: pip install xlearn\n")

print("\n🤖 Model Testing:\n")
results = []

for name, model in models_to_test:
    try:
        fit_success = model.fit(user)
        if not fit_success:
            print(f"   ❌ {name:20s} - Training failed (insufficient data)")
            continue
            
        test_vec = sample_products[50]
        single_pred = model.predict_preference(test_vec)
        batch_preds = model.score_products(sample_products[:10])
        
        assert 0.0 <= single_pred <= 1.0, f"Single prediction out of range: {single_pred}"
        assert len(batch_preds) == 10, "Batch predictions length mismatch"
        assert all(0.0 <= p <= 1.0 for p in batch_preds), "Some batch predictions out of range"
        
        if hasattr(model, 'get_feature_importance'):
            importance = model.get_feature_importance()
            has_importance = len(importance) > 0
        else:
            has_importance = False
        
        print(f"   ✅ {name:20s} - Trained & Validated")
        print(f"      • Single prediction: {single_pred:.4f}")
        print(f"      • Batch predictions: min={batch_preds.min():.4f}, max={batch_preds.max():.4f}, mean={batch_preds.mean():.4f}")
        print(f"      • Feature importance: {'Yes' if has_importance else 'N/A'}")
        
        results.append((name, True, single_pred, batch_preds))
        
    except ImportError as e:
        print(f"   ⚠️  {name:20s} - Not installed: {str(e)[:50]}")
    except Exception as e:
        print(f"   ❌ {name:20s} - Error: {str(e)[:50]}")
        results.append((name, False, None, None))

print(f"\n{'=' * 60}")
working_count = sum(1 for _, success, _, _ in results if success)
print(f"SUMMARY: {working_count}/{len(results)} models working")
print(f"{'=' * 60}\n")

# Test model selection with different user stages
print("🎯 Model Selection by User Stage:\n")
stages = [
    (0, "Early"),
    (3, "Early"),
    (5, "Mid"),
    (15, "Mid"),
    (25, "Advanced"),
    (75, "Experienced"),
    (150, "Expert"),
]

for interactions, expected_stage in stages:
    test_user = UserState(dim)
    test_user.interactions = interactions
    model, stage_name = get_best_model(test_user)
    status = "✅" if expected_stage in stage_name else "⚠️"
    print(f"   {status} {interactions:3d} interactions → {stage_name}")

print("\n✅ All model validation complete!")
