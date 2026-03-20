"""
ML-based feedback models for user preference learning.

Replaces simple weighted average with proper machine learning:
- Logistic Regression
- Random Forest Classifier
- Gradient Boosting Classifier
- Contextual Bandit (online learning)
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

try:
    import vowpalwabbit as vw
    VW_AVAILABLE = True
except ImportError:
    VW_AVAILABLE = False


class UserState:
    """Enhanced UserState tracking for ML models."""

    def __init__(self, dim: int):
        self.dim = dim
        
        # Raw interactions
        self.liked_vectors: List[np.ndarray] = []
        self.disliked_vectors: List[np.ndarray] = []
        self.irritation_vectors: List[np.ndarray] = []
        
        # Metadata for explanations
        self.liked_reasons: List[str] = []
        self.disliked_reasons: List[str] = []
        self.irritation_reasons: List[str] = []
        
        # Interaction counts
        self.interactions: int = 0
        self.liked_count: int = 0
        self.disliked_count: int = 0
        self.irritation_count: int = 0

    def add_liked(self, vec: np.ndarray, reasons: List[str] | None = None):
        self.liked_vectors.append(vec.astype(np.float32))
        if reasons:
            self.liked_reasons.extend(reasons)
        self.interactions += 1
        self.liked_count += 1

    def add_disliked(self, vec: np.ndarray, reasons: List[str] | None = None):
        self.disliked_vectors.append(vec.astype(np.float32))
        if reasons:
            self.disliked_reasons.extend(reasons)
        self.interactions += 1
        self.disliked_count += 1

    def add_irritation(self, vec: np.ndarray, reasons: List[str] | None = None):
        self.irritation_vectors.append(vec.astype(np.float32))
        if reasons:
            self.irritation_reasons.extend(reasons)
        self.interactions += 1
        self.irritation_count += 1

    def get_training_data(self) -> Tuple[np.ndarray, np.ndarray] | None:
        """
        Prepare training data for ML models.
        
        Returns:
            (X, y) where X is feature matrix and y is binary preference labels
            None if insufficient data
        """
        if not self.liked_vectors and not self.disliked_vectors and not self.irritation_vectors:
            return None
        
        X_list = []
        y_list = []
        
        # Liked samples (label=1)
        for vec in self.liked_vectors:
            X_list.append(vec)
            y_list.append(1)
        
        # Disliked samples (label=0)
        for vec in self.disliked_vectors:
            X_list.append(vec)
            y_list.append(0)
        
        # Irritation samples are also disliked (label=0) with stronger weight
        for vec in self.irritation_vectors:
            X_list.append(vec)
            y_list.append(0)
        
        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.int32)
        
        if len(X) < 2:
            return None
        
        return X, y


class LogisticRegressionFeedback:
    """Logistic Regression model for user preference prediction."""
    
    def __init__(self, max_iter: int = 1000):
        self.model = LogisticRegression(
            max_iter=max_iter,
            solver="lbfgs",
            random_state=42,
            warm_start=True
        )
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def fit(self, user_state: UserState):
        """Train logistic regression on user interactions."""
        data = user_state.get_training_data()
        if data is None:
            return False
        
        X, y = data
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        return True
    
    def predict_preference(self, product_vector: np.ndarray) -> float:
        """
        Predict preference for a product.
        
        Args:
            product_vector: Feature vector of the product
            
        Returns:
            Probability of liking (0.0 to 1.0)
        """
        if not self.is_trained:
            return 0.5
        
        X = product_vector.reshape(1, -1).astype(np.float32)
        X_scaled = self.scaler.transform(X)
        return float(self.model.predict_proba(X_scaled)[0, 1])
    
    def score_products(self, product_vectors: np.ndarray) -> np.ndarray:
        """
        Score multiple products.
        
        Args:
            product_vectors: Array of product vectors (N, dim)
            
        Returns:
            Array of preference scores (N,)
        """
        if not self.is_trained:
            return np.ones(len(product_vectors)) * 0.5
        
        X_scaled = self.scaler.transform(product_vectors.astype(np.float32))
        return self.model.predict_proba(X_scaled)[:, 1].astype(np.float32)
    
    def save(self, path: Path):
        """Save model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler}, f)
    
    def load(self, path: Path):
        """Load model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.is_trained = True


class RandomForestFeedback:
    """Random Forest model for user preference prediction."""
    
    def __init__(self, n_estimators: int = 100, max_depth: int = 10):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def fit(self, user_state: UserState):
        """Train random forest on user interactions."""
        data = user_state.get_training_data()
        if data is None:
            return False
        
        X, y = data
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        return True
    
    def predict_preference(self, product_vector: np.ndarray) -> float:
        """Predict preference for a product (0.0 to 1.0)."""
        if not self.is_trained:
            return 0.5
        
        X = product_vector.reshape(1, -1).astype(np.float32)
        X_scaled = self.scaler.transform(X)
        return float(self.model.predict_proba(X_scaled)[0, 1])
    
    def score_products(self, product_vectors: np.ndarray) -> np.ndarray:
        """Score multiple products."""
        if not self.is_trained:
            return np.ones(len(product_vectors)) * 0.5
        
        X_scaled = self.scaler.transform(product_vectors.astype(np.float32))
        return self.model.predict_proba(X_scaled)[:, 1].astype(np.float32)
    
    def get_feature_importance(self) -> np.ndarray:
        """Get feature importance scores."""
        if not self.is_trained:
            return np.array([])
        return self.model.feature_importances_.astype(np.float32)
    
    def save(self, path: Path):
        """Save model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler}, f)
    
    def load(self, path: Path):
        """Load model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.is_trained = True


class GradientBoostingFeedback:
    """Gradient Boosting model for user preference prediction."""
    
    def __init__(self, n_estimators: int = 100, learning_rate: float = 0.1, max_depth: int = 5):
        self.model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def fit(self, user_state: UserState):
        """Train gradient boosting on user interactions."""
        data = user_state.get_training_data()
        if data is None:
            return False
        
        X, y = data
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        return True
    
    def predict_preference(self, product_vector: np.ndarray) -> float:
        """Predict preference for a product (0.0 to 1.0)."""
        if not self.is_trained:
            return 0.5
        
        X = product_vector.reshape(1, -1).astype(np.float32)
        X_scaled = self.scaler.transform(X)
        return float(self.model.predict_proba(X_scaled)[0, 1])
    
    def score_products(self, product_vectors: np.ndarray) -> np.ndarray:
        """Score multiple products."""
        if not self.is_trained:
            return np.ones(len(product_vectors)) * 0.5
        
        X_scaled = self.scaler.transform(product_vectors.astype(np.float32))
        return self.model.predict_proba(X_scaled)[:, 1].astype(np.float32)
    
    def get_feature_importance(self) -> np.ndarray:
        """Get feature importance scores."""
        if not self.is_trained:
            return np.array([])
        return self.model.feature_importances_.astype(np.float32)
    
    def save(self, path: Path):
        """Save model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler}, f)
    
    def load(self, path: Path):
        """Load model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.is_trained = True


class ContextualBanditFeedback:
    """
    Contextual multi-armed bandit using Vowpal Wabbit for online learning.
    
    Uses VW's logistic regression with adaptive learning for preference prediction.
    Learns incrementally from user feedback without retraining.
    """
    
    def __init__(self, dim: int, learning_rate: float = 0.01, explore_rate: float = 0.1):
        if not VW_AVAILABLE:
            raise ImportError("vowpalwabbit is required for ContextualBanditFeedback. Install with: pip install vowpalwabbit")
        
        self.dim = dim
        self.learning_rate = learning_rate
        self.explore_rate = explore_rate
        
        # Initialize Vowpal Wabbit model with configured learning rate
        vw_args = f"--loss_function logistic --link logistic --adaptive --quiet --learning_rate {self.learning_rate}"
        self.vw = vw.Workspace(vw_args)
        self.total_updates = 0
    
    def fit(self, user_state: UserState) -> bool:
        """For simulation: update from user interactions."""
        # Update from liked
        for vec in user_state.liked_vectors:
            self.update(vec, reward=1)
        # Update from disliked and irritation
        for vec in user_state.disliked_vectors + user_state.irritation_vectors:
            self.update(vec, reward=0)
        return True
    
    def predict_preference(self, product_vector: np.ndarray) -> float:
        """Predict preference probability using VW."""
        example = " | " + " ".join(f"{i}:{v}" for i, v in enumerate(product_vector) if v != 0)
        return self.vw.predict(example)
    
    def score_products(self, product_vectors: np.ndarray) -> np.ndarray:
        """Score multiple products using VW, with optional exploration noise."""
        scores = []
        for vec in product_vectors:
            example = " | " + " ".join(f"{i}:{v}" for i, v in enumerate(vec) if v != 0)
            score = self.vw.predict(example)
            scores.append(score)
        scores_array = np.array(scores, dtype=np.float32)
        # Simple epsilon-style exploration: blend predictions with random noise
        if self.explore_rate > 0.0:
            noise = np.random.uniform(low=0.0, high=1.0, size=scores_array.shape).astype(np.float32)
            scores_array = (1.0 - self.explore_rate) * scores_array + self.explore_rate * noise
        return scores_array
    
    def update(self, product_vector: np.ndarray, reward: int):
        """
        Incrementally update VW model based on feedback.
        
        Args:
            product_vector: Feature vector of the product
            reward: 1 for liked/good, 0 for disliked/bad
        """
        assert reward in [0, 1], "reward must be 0 (dislike) or 1 (like)"
        
        # VW uses 1 for positive, -1 for negative
        label = 1 if reward == 1 else -1
        example = f"{label} | " + " ".join(f"{i}:{v}" for i, v in enumerate(product_vector) if v != 0)
        self.vw.learn(example)
        self.total_updates += 1
    
    def get_uncertainty(self) -> np.ndarray:
        """
        Get uncertainty estimates per feature for exploration.
        VW handles exploration internally, so return zeros.
        """
        return np.zeros(self.dim, dtype=np.float32)
    
    def save(self, path: Path):
        """Save VW model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.vw.save(str(path))
    
    def load(self, path: Path):
        """Load VW model from disk."""
        if not VW_AVAILABLE:
            raise RuntimeError("Vowpal Wabbit is not available; cannot load contextual bandit model.")
        if not path.exists():
            raise FileNotFoundError(f"VW model file not found: {path}")

        # Clean up any existing VW workspace, if present
        vw_obj = getattr(self, "vw", None)
        if vw_obj is not None:
            finish = getattr(vw_obj, "finish", None)
            if callable(finish):
                try:
                    finish()
                except Exception:
                    # Ignore cleanup errors; we'll overwrite self.vw anyway
                    pass

        # Recreate VW workspace, loading the saved model.
        # This is equivalent to passing "-i <model>" on the VW command line.
        # We keep it quiet to avoid logging on load.
        try:
            self.vw = vw.Workspace(quiet=True, initial_regressor=str(path))
        except TypeError:
            # Fallback for older VW Python APIs that may not support Workspace
            # or 'initial_regressor' kwarg; use argument string instead.
            self.vw = vw.vw(f"-i {str(path)} --quiet")


def update_user_state(
    user: UserState,
    reaction: str,
    product_vec: np.ndarray,
    reason_tags: Optional[List[str]] = None,
) -> UserState:
    """
    Update user state based on a single interaction.
    
    Args:
        user: UserState object to update
        reaction: "like", "dislike", or "irritation"
        product_vec: Feature vector of the product
        reason_tags: Optional list of reason tags
    """
    if reason_tags is None:
        reason_tags = []
    
    reaction = (reaction or "").lower().strip()
    
    if reaction == "like":
        user.add_liked(product_vec, reason_tags)
    elif reaction == "dislike":
        user.add_disliked(product_vec, reason_tags)
    elif reaction == "irritation":
        user.add_disliked(product_vec, reason_tags)
        user.add_irritation(product_vec, reason_tags)
    
    return user


def compute_user_vector(user: UserState, schema: Optional[Dict] = None) -> np.ndarray:
    """
    LEGACY: Simple weighted average (kept for backward compatibility).
    
    New code should use ML model predict_preference() instead.
    """
    user_vec = np.zeros(user.dim, dtype=np.float32)
    
    if user.liked_vectors:
        liked_avg = np.mean(user.liked_vectors, axis=0)
        user_vec += 2.0 * liked_avg
    
    if user.disliked_vectors:
        disliked_avg = np.mean(user.disliked_vectors, axis=0)
        user_vec -= 1.0 * disliked_avg
    
    if user.irritation_vectors:
        irritation_avg = np.mean(user.irritation_vectors, axis=0)
        user_vec -= 2.0 * irritation_avg
    
    norm = np.linalg.norm(user_vec)
    if norm > 1e-9:
        user_vec = user_vec / norm
    
    return user_vec
