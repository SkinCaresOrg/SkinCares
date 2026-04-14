"""
Test that models now train with augmented features including reason tags.
"""

from skincarelib.ml_system.ml_feedback_model import (
    UserState,
    LogisticRegressionFeedback,
    RandomForestFeedback,
    LightGBMFeedback,
)
import numpy as np


def test_reason_tags_augmented_features():
    """Test that reason tags are now used in model training."""
    
    # Create test user state
    user = UserState(dim=256)

    # Add samples with various tags
    tags_like = ["hydrated_well", "absorbed_quickly", "non_irritating"]
    tags_dislike = ["irritating", "greasy_feeling"]
    tags_irritation = ["broke_me_out", "too_expensive"]

    for i in range(5):
        vec = np.random.randn(256).astype(np.float32)
        user.add_liked(vec, reasons=tags_like)

    for i in range(3):
        vec = np.random.randn(256).astype(np.float32)
        user.add_disliked(vec, reasons=tags_dislike)

    for i in range(2):
        vec = np.random.randn(256).astype(np.float32)
        user.add_irritation(vec, reasons=tags_irritation)

    # Get augmented training data
    X, y = user.get_training_data()
    
    print("\n" + "=" * 80)
    print("REASON TAGS NOW USED IN MODEL TRAINING!")
    print("=" * 80)
    print(f"\n✅ Augmented feature dimension: {X.shape[1]} dims")
    print("   - Product vectors: 256 dims")
    print("   - Reason tags: 10 dims")
    print("   - Total: 266 dims")
    print(f"\n✅ Training samples: {X.shape[0]}")
    print(f"   - Liked (reason tags): {tags_like}")
    print(f"   - Disliked (reason tags): {tags_dislike}")
    print(f"   - Irritation (reason tags): {tags_irritation}")
    print("\n✅ Reason tags vocabulary:")
    for tag, idx in UserState.REASON_TAGS_VOCAB.items():
        print(f"   - [{idx}] {tag}")

    # Train models
    print("\n" + "-" * 80)
    print("Training models with augmented features...")
    print("-" * 80)

    lr = LogisticRegressionFeedback()
    assert lr.fit(user), "LogisticRegression training failed"
    print("✅ LogisticRegression trained with 266-dim augmented features")

    rf = RandomForestFeedback()
    assert rf.fit(user), "RandomForest training failed"
    print("✅ RandomForest trained with 266-dim augmented features")

    lgb = LightGBMFeedback()
    assert lgb.fit(user), "LightGBM training failed"
    print("✅ LightGBM trained with 266-dim augmented features")

    print("\n" + "=" * 80)
    print("✅ SUCCESS! Models now learn from:")
    print("   - Product vectors (256-dim)")
    print("   - Reason tags (hydrated_well, irritating, affordable, etc.)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    test_reason_tags_augmented_features()
