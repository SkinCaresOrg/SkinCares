#!/usr/bin/env python3
"""
Train ML models with real product signals and vectors.

This script:
1. Loads products_with_signals.csv
2. Loads real product vectors from artifacts/
3. Creates synthetic training data based on signal strengths
4. Trains all 5-stage ML models
5. Validates model performance
6. Saves trained models
"""

import os
import sys
from pathlib import Path

# Add root to path
sys.path.insert(0, str(Path(__file__).parent))

import logging
import pickle
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from skincarelib.ml_system.ml_feedback_model import (
    LIGHTGBM_AVAILABLE,
    XLEARN_AVAILABLE,
    ContextualBanditFeedback,
    GradientBoostingFeedback,
    LightGBMFeedback,
    LogisticRegressionFeedback,
    RandomForestFeedback,
    UserState,
    XLearnFeedback,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelTrainer:
    """Train and validate ML models with real product signals."""

    def __init__(self):
        self.products_df = None
        self.product_vectors = None
        self.signal_data = None
        self.trained_models = {}
        self.validation_results = {}

    def load_data(self):
        """Load products with signals and vectors."""
        logger.info("[1/5] Loading data...")

        # Load products with signals
        path = Path("data/processed/products_with_signals.csv")
        logger.info(f"Loading products from: {path}")
        self.products_df = pd.read_csv(path)
        logger.info(f"✅ Loaded {len(self.products_df)} products")

        # Load product vectors
        vectors_path = Path("artifacts/product_vectors.npy")
        logger.info(f"Loading vectors from: {vectors_path}")
        self.product_vectors = np.load(vectors_path)
        logger.info(f"✅ Loaded vectors shape: {self.product_vectors.shape}")

        # Verify dimensions match
        if len(self.products_df) != len(self.product_vectors):
            raise ValueError(
                f"Product count mismatch: {len(self.products_df)} vs {len(self.product_vectors)}"
            )

        # Extract signal columns
        signal_cols = [
            'hydration', 'barrier', 'acne_control',
            'soothing', 'exfoliation', 'antioxidant', 'irritation_risk'
        ]
        self.signal_data = self.products_df[signal_cols].values
        logger.info(f"✅ Extracted signal data: {self.signal_data.shape}")

    def create_training_data(self, n_users: int = 500):
        """Create synthetic training data based on signal strengths."""
        logger.info(f"[2/5] Creating synthetic training data ({n_users} users)...")

        # Use different random seed for each call to vary data
        import random
        seed = random.randint(0, 10000)
        np.random.seed(seed)
        training_users = []

        for user_id in range(n_users):
            user = UserState(dim=self.product_vectors.shape[1])

            # Randomly select user preferences (signal preferences)
            # User cares about 2-4 signals most
            user_preferences = np.random.rand(7) * 0.3  # Base preference
            top_signals = np.random.choice(7, np.random.randint(2, 4), replace=False)
            user_preferences[top_signals] = np.random.rand(len(top_signals))
            user_preferences = user_preferences / (user_preferences.sum() + 1e-6)

            # Select products to interact with
            n_interactions = np.random.randint(8, 30)
            selected_indices = np.random.choice(
                len(self.products_df), min(n_interactions, len(self.products_df)), replace=False
            )

            for idx in selected_indices:
                product_vec = self.product_vectors[idx]
                signals = self.signal_data[idx]

                # Calculate preference score: dot product of user prefs with signals
                preference_score = np.dot(user_preferences, signals)

                # Add noise and use more balanced thresholds
                noisy_score = preference_score + np.random.normal(0, 0.15)

                # 40% base chance of like to start, adjusted by score
                like_prob = 0.4 + (noisy_score - 0.5) * 0.5
                like_prob = np.clip(like_prob, 0.1, 0.9)

                rand_val = np.random.rand()
                if rand_val < like_prob * 0.85:
                    # Like
                    user.add_liked(product_vec)
                elif rand_val < like_prob + (1 - like_prob) * 0.8:
                    # Dislike
                    user.add_disliked(product_vec)
                else:
                    # Irritation
                    user.add_irritation(product_vec)

            if user.liked_count >= 2 and user.disliked_count >= 2:  # Ensure balanced
                training_users.append(user)

        logger.info(f"✅ Created {len(training_users)} training users")
        if training_users:
            total_interactions = sum(u.interactions for u in training_users)
            total_liked = sum(u.liked_count for u in training_users)
            total_disliked = sum(u.disliked_count for u in training_users)
            logger.info(f"   Total interactions: {total_interactions}")
            logger.info(f"   Total liked: {total_liked} ({total_liked/total_interactions*100:.1f}%)")
            logger.info(f"   Total disliked: {total_disliked} ({total_disliked/total_interactions*100:.1f}%)")

        return training_users

    def train_models(self, training_users):
        """Train all 5 models."""
        logger.info("[3/5] Training models...")

        # Aggregate training data from all users first
        all_X = []
        all_y = []

        for user in training_users:
            training_data = user.get_training_data()
            if training_data is not None:
                X, y = training_data
                all_X.append(X)
                all_y.append(y)

        if not all_X:
            logger.error("❌ No training data available!")
            return

        X_train = np.vstack(all_X).astype(np.float32)
        y_train = np.hstack(all_y).astype(np.int32)

        logger.info(f"   Aggregated training samples: {len(X_train)}")
        logger.info(f"   Feature dimension: {X_train.shape[1]}")
        logger.info(f"   Class distribution: {np.bincount(y_train)}")

        # Train models using a combined UserState with all data
        combined_user = UserState(dim=X_train.shape[1])
        for X_sample, y_sample in zip(X_train, y_train):
            if y_sample == 1:
                combined_user.add_liked(X_sample)
            else:
                combined_user.add_disliked(X_sample)

        # 1. Logistic Regression
        logger.info("\n   Training: LogisticRegression...")
        try:
            lr_model = LogisticRegressionFeedback()
            lr_model.fit(combined_user)
            self.trained_models['logistic_regression'] = lr_model
            logger.info("   ✅ LogisticRegression trained")
        except Exception as e:
            logger.error(f"   ❌ LogisticRegression failed: {e}")

        # 2. Random Forest
        logger.info("   Training: RandomForest...")
        try:
            rf_model = RandomForestFeedback()
            rf_model.fit(combined_user)
            self.trained_models['random_forest'] = rf_model
            logger.info("   ✅ RandomForest trained")
        except Exception as e:
            logger.error(f"   ❌ RandomForest failed: {e}")

        # 3. Gradient Boosting
        logger.info("   Training: GradientBoosting...")
        try:
            gb_model = GradientBoostingFeedback()
            gb_model.fit(combined_user)
            self.trained_models['gradient_boosting'] = gb_model
            logger.info("   ✅ GradientBoosting trained")
        except Exception as e:
            logger.error(f"   ❌ GradientBoosting failed: {e}")

        # 4. LightGBM (if available)
        if LIGHTGBM_AVAILABLE:
            logger.info("   Training: LightGBM...")
            try:
                lgb_model = LightGBMFeedback()
                lgb_model.fit(combined_user)
                self.trained_models['lightgbm'] = lgb_model
                logger.info("   ✅ LightGBM trained")
            except Exception as e:
                logger.error(f"   ❌ LightGBM failed: {e}")
        else:
            logger.warning("   ⚠️  LightGBM not available")

        # 5. XLearn (if available)
        if XLEARN_AVAILABLE:
            logger.info("   Training: XLearn...")
            try:
                xl_model = XLearnFeedback()
                xl_model.fit(combined_user)
                self.trained_models['xlearn'] = xl_model
                logger.info("   ✅ XLearn trained")
            except Exception as e:
                logger.error(f"   ❌ XLearn failed: {e}")
        else:
            logger.info("   ℹ️  XLearn not available (optional)")

        # 6. Contextual Bandit (uses VW - should be available)
        logger.info("   Training: ContextualBandit...")
        try:
            dim = X_train.shape[1]
            cb_model = ContextualBanditFeedback(dim=dim)
            cb_model.fit(combined_user)
            self.trained_models['contextual_bandit'] = cb_model
            logger.info("   ✅ ContextualBandit trained")
        except Exception as e:
            logger.error(f"   ❌ ContextualBandit failed: {e}")

        logger.info(f"\n✅ Successfully trained {len(self.trained_models)} models")

    def validate_models(self, test_users):
        """Validate model predictions on test data."""
        logger.info("[4/5] Validating models...")

        for model_name, model in self.trained_models.items():
            logger.info(f"\n   Validating: {model_name}")
            correct = 0
            total = 0
            errors = 0

            for user in test_users:
                training_data = user.get_training_data()
                if training_data is not None:
                    X, y = training_data
                    # Get predictions for each sample
                    for i, (sample, label) in enumerate(zip(X, y)):
                        try:
                            pred_prob = model.predict_preference(sample)
                            # Convert probability to binary prediction (>0.5 = like)
                            pred = 1 if pred_prob > 0.5 else 0
                            if pred == label:
                                correct += 1
                            total += 1
                        except Exception as e:
                            errors += 1
                            logger.debug(f"      Prediction error for model {model_name}: {e}")

            accuracy = (correct / total * 100) if total > 0 else 0
            self.validation_results[model_name] = {
                'accuracy': accuracy,
                'total_predictions': total,
                'errors': errors,
            }
            logger.info(f"   ✅ Accuracy: {accuracy:.2f}% ({correct}/{total})")
            if errors > 0:
                logger.info(f"   ⚠️  Errors: {errors}")

    def save_models(self):
        """Save trained models to artifacts."""
        logger.info("[5/5] Saving models...")

        models_dir = Path("artifacts/trained_models")
        models_dir.mkdir(exist_ok=True)

        for model_name, model in self.trained_models.items():
            model_path = models_dir / f"{model_name}_model.pkl"
            logger.info(f"   Saving: {model_name} → {model_path}")

            try:
                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)
                logger.info(f"   ✅ Saved: {model_name}")
            except Exception as e:
                logger.error(f"   ❌ Failed to save {model_name}: {e}")

        # Save validation results
        results_path = models_dir / "validation_results.json"
        import json
        with open(results_path, 'w') as f:
            json.dump(self.validation_results, f, indent=2)
        logger.info(f"✅ Validation results saved to: {results_path}")

    def run(self):
        """Execute full training pipeline."""
        try:
            logger.info("=" * 70)
            logger.info("🚀 MODEL TRAINING WITH REAL PRODUCT SIGNALS")
            logger.info("=" * 70)

            # Load data
            self.load_data()

            # Create synthetic training data
            training_users = self.create_training_data(n_users=500)

            # Split for validation
            test_users = self.create_training_data(n_users=100)

            # Train all models
            self.train_models(training_users)

            # Validate
            self.validate_models(test_users)

            # Save models
            self.save_models()

            logger.info("\n" + "=" * 70)
            logger.info("✅ TRAINING COMPLETE!")
            logger.info("=" * 70)
            logger.info(f"✅ Trained models: {list(self.trained_models.keys())}")
            logger.info(f"✅ Models saved to: artifacts/trained_models/")
            logger.info("\nValidation Results Summary:")
            for model_name, results in self.validation_results.items():
                logger.info(f"  {model_name}: {results['accuracy']:.2f}% accuracy")

            return True

        except Exception as e:
            logger.error(f"❌ Training failed: {e}", exc_info=True)
            return False


def main():
    trainer = ModelTrainer()
    success = trainer.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
