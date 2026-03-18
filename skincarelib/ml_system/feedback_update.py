"""
Feedback update module - backward compatible wrapper.

This module now imports from ml_feedback_model for backward compatibility
while providing access to both legacy and ML-based feedback models.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Literal

import numpy as np

# Import new ML models
from skincarelib.ml_system.ml_feedback_model import (
    UserState,
    update_user_state,
    compute_user_vector,
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
    raise FileNotFoundError("Could not find project root (folder containing 'artifacts/').")


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


def create_feedback_model(
    model_type: Literal["logistic", "random_forest", "gradient_boosting", "contextual_bandit"] = "logistic",
    dim: Optional[int] = None,
    **kwargs
):
    """
    Factory function to create feedback models.
    
    Args:
        model_type: Type of model to create
        dim: Required for contextual_bandit, ignored for others
        **kwargs: Additional arguments for model constructors
    
    Returns:
        Feedback model instance
    """
    if model_type == "logistic":
        return LogisticRegressionFeedback(**kwargs)
    elif model_type == "random_forest":
        return RandomForestFeedback(**kwargs)
    elif model_type == "gradient_boosting":
        return GradientBoostingFeedback(**kwargs)
    elif model_type == "contextual_bandit":
        if dim is None:
            raise ValueError("dim is required for contextual_bandit")
        return ContextualBanditFeedback(dim=dim, **kwargs)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")