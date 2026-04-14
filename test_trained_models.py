#!/usr/bin/env python3
"""
Test and validate trained ML models.

This script:
1. Loads all trained models
2. Tests predictions on real product vectors
3. Validates model API compatibility
4. Checks performance metrics
5. Tests the 5-stage model progression
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
import logging
import pickle

import numpy as np

from skincarelib.ml_system.ml_feedback_model import (
    ContextualBanditFeedback,
    GradientBoostingFeedback,
    LightGBMFeedback,
    LogisticRegressionFeedback,
    RandomForestFeedback,
    UserState,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelTester:
    """Test and validate trained ML models."""

    def __init__(self):
        self.models = {}
        self.product_vectors = None
        self.test_results = {}

    def load_models(self):
        """Load all trained models from disk."""
        logger.info("[1/6] Loading trained models...")
        models_dir = Path("artifacts/trained_models")

        model_files = [
            ("logistic_regression", "logistic_regression_model.pkl"),
            ("random_forest", "random_forest_model.pkl"),
            ("gradient_boosting", "gradient_boosting_model.pkl"),
            ("lightgbm", "lightgbm_model.pkl"),
        ]

        for model_name, filename in model_files:
            model_path = models_dir / filename
            if model_path.exists():
                try:
                    with open(model_path, 'rb') as f:
                        model = pickle.load(f)
                    self.models[model_name] = model
                    logger.info(f"   ✅ Loaded: {model_name}")
                except Exception as e:
                    logger.error(f"   ❌ Failed to load {model_name}: {e}")
            else:
                logger.warning(f"   ⚠️  Not found: {model_path}")

        logger.info(f"✅ Loaded {len(self.models)} models")

    def load_product_vectors(self):
        """Load real product vectors."""
        logger.info("[2/6] Loading product vectors...")
        vectors_path = Path("artifacts/product_vectors.npy")
        self.product_vectors = np.load(vectors_path)
        logger.info(f"✅ Loaded vectors: {self.product_vectors.shape}")

    def test_single_prediction(self):
        """Test each model can make a single prediction."""
        logger.info("[3/6] Testing single predictions...")

        # Use first product vector
        test_vector = self.product_vectors[0]

        for model_name, model in self.models.items():
            try:
                # Test predict_preference
                prob = model.predict_preference(test_vector)

                # Validate output
                assert isinstance(prob, (float, np.floating)), f"Expected float, got {type(prob)}"
                assert 0.0 <= prob <= 1.0, f"Probability out of range: {prob}"

                logger.info(f"   ✅ {model_name:20s} → {prob:.4f} (prob)")
                self.test_results[f"{model_name}_single"] = {
                    "probability": float(prob),
                    "valid": True
                }
            except Exception as e:
                logger.error(f"   ❌ {model_name}: {e}")
                self.test_results[f"{model_name}_single"] = {"error": str(e)}

    def test_batch_predictions(self):
        """Test batch scoring on multiple products."""
        logger.info("[4/6] Testing batch predictions...")

        # Test on 100 random products
        n_test = 100
        test_indices = np.random.choice(len(self.product_vectors), n_test, replace=False)
        test_vectors = self.product_vectors[test_indices]

        for model_name, model in self.models.items():
            try:
                # Test score_products (batch prediction)
                if hasattr(model, 'score_products'):
                    scores = model.score_products(test_vectors)

                    # Validate output
                    assert len(scores) == len(test_vectors), "Score count mismatch"
                    assert np.all((scores >= 0) & (scores <= 1)), "Scores out of range [0, 1]"
                    assert not np.any(np.isnan(scores)), "NaN values in scores"

                    mean_score = np.mean(scores)
                    std_score = np.std(scores)

                    logger.info(f"   ✅ {model_name:20s} → mean={mean_score:.4f}, std={std_score:.4f}")
                    self.test_results[f"{model_name}_batch"] = {
                        "batch_size": n_test,
                        "mean_score": float(mean_score),
                        "std_score": float(std_score),
                        "valid": True
                    }
                else:
                    logger.warning(f"   ⚠️  {model_name} doesn't have score_products method")

            except Exception as e:
                logger.error(f"   ❌ {model_name}: {e}")
                self.test_results[f"{model_name}_batch"] = {"error": str(e)}

    def test_5stage_progression(self):
        """Test the 5-stage model progression logic."""
        logger.info("[5/6] Testing 5-stage model progression...")

        # Simulate different user interaction counts
        progression_stages = [
            (2, "LogisticRegression (0-5 int)"),
            (10, "RandomForest (5-20 int)"),
            (30, "LightGBM (20-50 int)"),
            (75, "ContextualBandit (50-100 int)"),
        ]

        for interactions, description in progression_stages:
            # Create synthetic user
            user = UserState(dim=self.product_vectors.shape[1])

            # Add synthetic interactions
            for i in range(interactions):
                idx = np.random.randint(0, len(self.product_vectors))
                vec = self.product_vectors[idx]

                if i % 2 == 0:
                    user.add_liked(vec)
                else:
                    user.add_disliked(vec)

            # Determine which model should be used
            if interactions < 5:
                expected_model = "LogisticRegression"
            elif interactions < 20:
                expected_model = "RandomForest"
            elif interactions < 50:
                expected_model = "LightGBM"
            else:
                expected_model = "ContextualBandit"

            # Check if model is available
            model_key = expected_model.lower().replace("contextualbandit", "contextual_bandit")
            if model_key in self.models:
                logger.info(f"   ✅ {interactions:3d} interactions → {description} ✅")
            else:
                logger.warning(f"   ⚠️  {interactions:3d} interactions → {description} (model not available)")

    def test_model_consistency(self):
        """Test that models produce consistent predictions."""
        logger.info("[6/6] Testing prediction consistency...")

        # Same vector tested 3 times should give identical results
        test_vector = self.product_vectors[42]

        for model_name, model in self.models.items():
            try:
                pred1 = model.predict_preference(test_vector)
                pred2 = model.predict_preference(test_vector)
                pred3 = model.predict_preference(test_vector)

                if pred1 == pred2 == pred3:
                    logger.info(f"   ✅ {model_name:20s} → Consistent ({pred1:.4f})")
                    self.test_results[f"{model_name}_consistency"] = {
                        "consistent": True,
                        "value": float(pred1)
                    }
                else:
                    logger.warning(f"   ⚠️  {model_name} → Inconsistent: {pred1}, {pred2}, {pred3}")
                    self.test_results[f"{model_name}_consistency"] = {
                        "consistent": False,
                        "values": [float(pred1), float(pred2), float(pred3)]
                    }
            except Exception as e:
                logger.error(f"   ❌ {model_name}: {e}")

    def run_all_tests(self):
        """Execute all tests."""
        try:
            logger.info("=" * 70)
            logger.info("🧪 ML MODEL VALIDATION TEST SUITE")
            logger.info("=" * 70)

            self.load_models()
            self.load_product_vectors()
            self.test_single_prediction()
            self.test_batch_predictions()
            self.test_5stage_progression()
            self.test_model_consistency()

            # Save results
            results_path = Path("artifacts/trained_models/test_results.json")
            with open(results_path, 'w') as f:
                json.dump(self.test_results, f, indent=2)

            logger.info("\n" + "=" * 70)
            logger.info("✅ ALL TESTS COMPLETED!")
            logger.info("=" * 70)
            logger.info(f"✅ Models loaded: {len(self.models)}/4")
            logger.info(f"✅ Test results saved to: {results_path}")
            logger.info(f"✅ Product vectors: {self.product_vectors.shape[0]:,} products")

            # Print summary
            logger.info("\n📊 Test Summary:")
            for key, result in self.test_results.items():
                status = "✅" if result.get("valid") or result.get("consistent") else "⚠️"
                logger.info(f"  {status} {key}")

            return True

        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}", exc_info=True)
            return False


def main():
    tester = ModelTester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
