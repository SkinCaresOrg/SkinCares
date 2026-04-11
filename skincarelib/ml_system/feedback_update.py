import json
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np

from skincarelib.ml_system.feedback_lr_model import FeedbackLogisticRegression
from skincarelib.ml_system.ml_feedback_model import (
    LogisticRegressionFeedback,
    RandomForestFeedback,
    GradientBoostingFeedback,
    ContextualBanditFeedback,
)


def find_project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here] + list(here.parents):
        if (p / "artifacts").exists():
            return p
    raise FileNotFoundError(
        "Could not find project root (folder containing 'artifacts/')."
    )


def load_artifacts():
    root = find_project_root()

    vectors = np.load(root / "artifacts" / "product_vectors.npy")

    with open(root / "artifacts" / "product_index.json", "r", encoding="utf-8") as f:
        product_index = json.load(f)

    schema = None
    schema_path = root / "artifacts" / "feature_schema.json"
    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

    index_to_id = {v: k for k, v in product_index.items()}
    return vectors, product_index, index_to_id, schema


class UserState:
    """Tracks user interactions and preferences."""

    def __init__(self, dim: int):
        self.dim = dim

        self.liked_vectors: List[np.ndarray] = []
        self.disliked_vectors: List[np.ndarray] = []
        self.irritation_vectors: List[np.ndarray] = []

        self.liked_reasons: List[str] = []
        self.disliked_reasons: List[str] = []
        self.irritation_reasons: List[str] = []

        self.interactions: int = 0
        self.liked_count: int = 0
        self.disliked_count: int = 0
        self.irritation_count: int = 0

    def add_liked(self, vec: np.ndarray, reasons: List[str]):
        self.liked_vectors.append(vec)
        self.liked_reasons.extend(reasons)
        self.interactions += 1
        self.liked_count += 1

    def add_disliked(self, vec: np.ndarray, reasons: List[str]):
        self.disliked_vectors.append(vec)
        self.disliked_reasons.extend(reasons)
        self.interactions += 1
        self.disliked_count += 1

    def add_irritation(self, vec: np.ndarray, reasons: List[str]):
        self.irritation_vectors.append(vec)
        self.irritation_reasons.extend(reasons)
        self.interactions += 1
        self.irritation_count += 1

    def get_training_data(self):
        if (
            not self.liked_vectors
            and not self.disliked_vectors
            and not self.irritation_vectors
        ):
            return None
        X_list, y_list = [], []
        for vec in self.liked_vectors:
            X_list.append(vec)
            y_list.append(1)
        for vec in self.disliked_vectors:
            X_list.append(vec)
            y_list.append(0)
        for vec in self.irritation_vectors:
            X_list.append(vec)
            y_list.append(0)
        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.int32)
        if len(X) < 2:
            return None
        return X, y


def update_user_state(
    user: UserState,
    reaction: str,
    product_vec: np.ndarray,
    reason_tags: Optional[List[str]] = None,
    irritation_counts_as_dislike: bool = True,
):
    """
    Update user state based on a single interaction.

        Design choice:
        - "irritation" is treated as a strong negative and can optionally also be counted
            as a dislike to preserve legacy behavior in summaries and metrics.
    """
    if reason_tags is None:
        reason_tags = []

    reaction = (reaction or "").lower().strip()

    if reaction == "like":
        user.add_liked(product_vec, reason_tags)

    elif reaction == "dislike":
        user.add_disliked(product_vec, reason_tags)

    elif reaction == "irritation":
        if irritation_counts_as_dislike:
            user.add_disliked(product_vec, reason_tags)
        user.add_irritation(product_vec, reason_tags)

    else:
        return user

    return user


def compute_user_vector(user: UserState, schema: Optional[Dict] = None) -> np.ndarray:
    """
    Compute user preference vector from feedback.

    Current weighting:
      +2.0 * mean(liked vectors)
      -1.0 * mean(disliked vectors)
      -2.0 * mean(irritation vectors)

    Note: Because irritation is also counted in disliked_vectors, it contributes to both
    the general negative signal and the stronger irritation-specific penalty.
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


def compute_user_vector_lr(
    user: UserState,
    schema: Optional[Dict] = None,
    use_cache: bool = True,
    model_user_id: Optional[str] = None,
) -> np.ndarray:
    """
    Compute user preference vector using Logistic Regression feedback learning.

    This is a machine learning approach that:
    1. Trains a logistic regression classifier on feedback history
    2. Uses the learned model to determine feature importance
    3. Generates a preference vector from weighted average using learned importance

    Compared to compute_user_vector:
    - Learns weights from feedback patterns instead of using fixed weights
    - Scales better with more feedback (model converges with data)
    - Handles preference intensity (strong vs weak likes/dislikes)

    Args:
        user: UserState with interaction history
        schema: Optional feature schema (unused, kept for API compatibility)
        use_cache: Whether to cache model in-memory

    Returns:
        np.ndarray: Normalized user preference vector (shape: (dim,))
    """
    # Initialize logistic regression model
    lr_model = FeedbackLogisticRegression(dim=user.dim)
    if model_user_id:
        lr_model.bind_user(model_user_id)

    # Add all feedback interactions to the model
    for vec in user.liked_vectors:
        lr_model.add_feedback(vec, feedback_label=1)
    for vec in user.disliked_vectors:
        lr_model.add_feedback(vec, feedback_label=0)
    for vec in user.irritation_vectors:
        lr_model.add_feedback(vec, feedback_label=-1)

    # Train the model (requires min 3 samples)
    if not lr_model.train(min_samples=3):
        # Fallback to weighted average if not enough feedback
        return compute_user_vector(user, schema)

    # Build user vector using learned preference weights
    learned_weights = lr_model.get_learned_weights()  # shape: (dim,)
    if learned_weights is None:
        return compute_user_vector(user, schema)

    user_vec = np.zeros(user.dim, dtype=np.float32)

    # Weighted average using learned importance
    if user.liked_vectors:
        liked_avg = np.mean(user.liked_vectors, axis=0)
        # Weight liked products by learned feature importance
        user_vec += 1.5 * learned_weights * liked_avg

    if user.disliked_vectors:
        disliked_avg = np.mean(user.disliked_vectors, axis=0)
        # Negative weight for disliked
        user_vec -= 0.8 * learned_weights * disliked_avg

    if user.irritation_vectors:
        irritation_avg = np.mean(user.irritation_vectors, axis=0)
        # Stronger negative weight for irritation
        user_vec -= 2.0 * learned_weights * irritation_avg

    # Normalize
    norm = np.linalg.norm(user_vec)
    if norm > 1e-9:
        user_vec = user_vec / norm
    else:
        # If result is zero vector, fallback to simple weighted average
        return compute_user_vector(user, schema)

    return user_vec


def create_feedback_model(model_type: str, dim: int):
    """Factory that returns a feedback model for the given model_type."""
    if model_type == "logistic":
        return LogisticRegressionFeedback()
    elif model_type == "random_forest":
        return RandomForestFeedback()
    elif model_type == "gradient_boosting":
        return GradientBoostingFeedback()
    elif model_type == "contextual_bandit":
        return ContextualBanditFeedback(dim=dim)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")
