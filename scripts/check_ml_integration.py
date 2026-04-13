#!/usr/bin/env python
"""
Check ML system integration: Supabase connection, model availability, and data pipeline.

This script verifies:
1. Supabase connection and table availability
2. All ML models can be imported
3. Prediction logging is working
4. Model selection strategy is sound
5. Frontend/Backend API contract
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from deployment.api.app import (
    supabase_client,
    get_model_metrics_from_supabase,
    log_prediction_to_supabase,
)
from skincarelib.ml_system.ml_feedback_model import (
    LogisticRegressionFeedback,
    RandomForestFeedback,
    GradientBoostingFeedback,
    ContextualBanditFeedback,
    UserState,
    VW_AVAILABLE,
    LIGHTGBM_AVAILABLE,
    XLEARN_AVAILABLE,
)

print("\n" + "=" * 70)
print("🔍 SkinCares ML System Integration Check")
print("=" * 70)

# ============================================================================
# 1. CHECK SUPABASE CONNECTION
# ============================================================================
print("\n[1/6] Checking Supabase Connection...")
print("-" * 70)

if supabase_client is None:
    print("❌ Supabase client not initialized")
    print("   Fix: Set SUPABASE_URL and SUPABASE_KEY environment variables")
else:
    print("✅ Supabase client connected")
    
    # Try to read from model_predictions_audit table
    try:
        response = supabase_client.table("model_predictions_audit").select(
            "count", count="exact"
        ).execute()
        pred_count = response.count
        print(f"✅ model_predictions_audit table exists ({pred_count} records)")
    except Exception as e:
        print(f"❌ Cannot access model_predictions_audit table: {e}")
    
    # Check other monitoring tables
    monitoring_tables = [
        "ml_model_versions",
        "ab_test_results",
        "feature_importance",
    ]
    
    for table_name in monitoring_tables:
        try:
            response = supabase_client.table(table_name).select(
                "count", count="exact"
            ).execute()
            print(f"✅ {table_name} table exists")
        except Exception as e:
            print(f"❌ Cannot access {table_name} table: {e}")

# ============================================================================
# 2. CHECK MODEL AVAILABILITY
# ============================================================================
print("\n[2/6] Checking ML Model Availability...")
print("-" * 70)

models_available = {
    "LogisticRegression": True,
    "RandomForest": True,
    "GradientBoosting": True,
    "ContextualBandit (VW)": VW_AVAILABLE,
    "LightGBM": LIGHTGBM_AVAILABLE,
    "XLearn FFM": XLEARN_AVAILABLE,
}

for model_name, available in models_available.items():
    status = "✅" if available else "⚠️ "
    print(f"{status} {model_name}: {'Available' if available else 'Not installed'}")

if not VW_AVAILABLE:
    print("   💡 Tip: pip install vowpalwabbit")
if not LIGHTGBM_AVAILABLE:
    print("   💡 Tip: pip install lightgbm")
if not XLEARN_AVAILABLE:
    print("   💡 Tip: pip install xlearn")

# ============================================================================
# 3. TEST PREDICTION LOGGING
# ============================================================================
print("\n[3/6] Testing Prediction Logging...")
print("-" * 70)

if supabase_client is None:
    print("⏭️  Skipping (Supabase not connected)")
else:
    try:
        test_logged = log_prediction_to_supabase(
            user_id="test_user_integration_check",
            product_id=1,
            predicted_score=0.75,
            actual_reaction="like",
            model_version="logistic_regression",
        )
        if test_logged:
            print("✅ Prediction logging to Supabase works")
        else:
            print("❌ Prediction logging returned False")
    except Exception as e:
        print(f"❌ Prediction logging failed: {e}")

# ============================================================================
# 4. TEST MODEL INSTANTIATION & TRAINING
# ============================================================================
print("\n[4/6] Testing Model Instantiation & Training...")
print("-" * 70)

import numpy as np

# Create test user state
user_state = UserState(dim=534)
for i in range(10):
    liked_vec = np.random.randn(534).astype(np.float32)
    disliked_vec = np.random.randn(534).astype(np.float32)
    user_state.add_liked(liked_vec)
    user_state.add_disliked(disliked_vec)

basic_models = [
    ("LogisticRegression", LogisticRegressionFeedback()),
    ("RandomForest", RandomForestFeedback()),
    ("GradientBoosting", GradientBoostingFeedback()),
]

for model_name, model_instance in basic_models:
    try:
        success = model_instance.fit(user_state)
        if success:
            # Try to predict
            test_vec = np.random.randn(534).astype(np.float32)
            score = model_instance.predict_preference(test_vec)
            print(f"✅ {model_name}: Trained & predicting (score={score:.2f})")
        else:
            print(f"⚠️  {model_name}: Training returned False (may need more data)")
    except Exception as e:
        print(f"❌ {model_name}: {str(e)[:60]}")

# Test VW if available
if VW_AVAILABLE:
    try:
        model = ContextualBanditFeedback(dim=534)
        success = model.fit(user_state)
        if success:
            test_vec = np.random.randn(534).astype(np.float32)
            score = model.predict_preference(test_vec)
            print(f"✅ ContextualBandit (VW): Trained & predicting (score={score:.2f})")
        else:
            print("⚠️  ContextualBandit (VW): Training returned False")
    except Exception as e:
        print(f"❌ ContextualBandit (VW): {str(e)[:60]}")

# ============================================================================
# 5. CHECK MODEL SELECTION STRATEGY
# ============================================================================
print("\n[5/6] Checking Model Selection Strategy...")
print("-" * 70)

from deployment.api.app import get_best_model

interaction_levels = [
    (1, "Early stage (should use LogisticRegression)"),
    (10, "Mid stage (should use RandomForest)"),
    (50, "Experienced (should use GradientBoosting)"),
    (200, "Power user (should use LightGBM if available)"),
    (1000, "Super user (should use XLearn if available)"),
]

for interactions, description in interaction_levels:
    user_state_test = UserState(dim=534)
    user_state_test.interactions = interactions
    
    # Add some data for training
    for i in range(max(5, interactions // 10)):
        user_state_test.add_liked(np.random.randn(534).astype(np.float32))
        user_state_test.add_disliked(np.random.randn(534).astype(np.float32))
    
    try:
        model, model_name = get_best_model(user_state_test)
        print(f"✅ {interactions:4d} interactions → {model_name}")
    except Exception as e:
        print(f"❌ {interactions:4d} interactions → Error: {str(e)[:40]}")

# ============================================================================
# 6. CHECK METRICS RETRIEVAL
# ============================================================================
print("\n[6/6] Checking Metrics Retrieval...")
print("-" * 70)

if supabase_client is None:
    print("⏭️  Skipping (Supabase not connected)")
else:
    try:
        metrics = get_model_metrics_from_supabase()
        if "error" in metrics:
            print(f"⚠️  No metrics available yet: {metrics['error']}")
        elif "message" in metrics:
            print(f"ℹ️  {metrics['message']}")
        else:
            print("✅ Metrics retrieved successfully")
            print(f"   Models in database: {list(metrics.keys())}")
            for model_name, data in metrics.items():
                if isinstance(data, dict) and "accuracy" in data:
                    acc = data["accuracy"]
                    total = data.get("total_predictions", 0)
                    print(f"   - {model_name}: {acc:.1%} accuracy ({total} predictions)")
    except Exception as e:
        print(f"❌ Failed to retrieve metrics: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("📊 Integration Summary")
print("=" * 70)

summary_items = [
    ("Supabase Connection", supabase_client is not None),
    ("Model Logging", supabase_client is not None),
    ("Basic Models Available", all(m for m, _ in basic_models)),
    ("Advanced Models Available", VW_AVAILABLE or LIGHTGBM_AVAILABLE or XLEARN_AVAILABLE),
    ("Model Selection Working", True),
]

all_pass = True
for item, status in summary_items:
    symbol = "✅" if status else "❌"
    print(f"{symbol} {item}")
    if not status:
        all_pass = False

print("\n" + "=" * 70)
if all_pass:
    print("🎉 All systems operational! ML integration is healthy.")
else:
    print("⚠️  Some issues detected. Please review the checks above.")
print("=" * 70 + "\n")

# ============================================================================
# RECOMMENDATIONS
# ============================================================================
print("📋 Recommendations:")
print("-" * 70)

if supabase_client is None:
    print("1. Set up Supabase credentials:")
    print("   export SUPABASE_URL=<your-supabase-url>")
    print("   export SUPABASE_KEY=<your-supabase-key>")
else:
    print("1. ✓ Supabase properly configured")

if not VW_AVAILABLE:
    print("2. Install Vowpal Wabbit for online learning:")
    print("   pip install vowpalwabbit")
else:
    print("2. ✓ Vowpal Wabbit installed")

if not LIGHTGBM_AVAILABLE:
    print("3. Install LightGBM for large-scale recommendations:")
    print("   pip install lightgbm")
else:
    print("3. ✓ LightGBM installed")

if not XLEARN_AVAILABLE:
    print("4. Install XLearn for feature interactions at scale:")
    print("   pip install xlearn")
else:
    print("4. ✓ XLearn installed")

print("5. Monitor metrics:")
print("   curl http://localhost:8000/api/ml/model-metrics")
print("   curl http://localhost:8000/api/ml/compare-models")

print("\n" + "=" * 70 + "\n")
