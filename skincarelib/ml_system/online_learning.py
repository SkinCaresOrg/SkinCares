"""
Online Learning Engine using Vowpal Wabbit for real-time personalization.

Unlike batch learning (fit then predict), online learning:
1. Observes one user interaction at a time
2. Updates model immediately based on that interaction
3. Makes next prediction using updated model
4. This creates a feedback loop: swipe → learn → recommend → swipe

Vowpal Wabbit is ideal for this because:
- Fast incremental updates (no retraining from scratch)
- Handles high-dimensional sparse features well
- Built-in contextual bandits for exploration/exploitation
- Efficient streaming processing
"""

import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import vowpalwabbit


class OnlineLearner:
    """
    Real-time online learning model using Vowpal Wabbit.

    Updates after each user interaction (swipe) to personalize recommendations.

    Features represent:
    - Product: TF-IDF + group + category embeddings (534-dim)
    - User context: Skin type, preferences, learning objective
    - Interaction: Like/dislike/skip signals

    Labels (what we predict):
    - 1: User will like this product
    - -1: User will dislike this product
    - 0: User will skip/didn't try
    """

    def __init__(self, dim: int = 534, learning_rate: float = 0.1):
        """
        Initialize online learning model.

        Args:
            dim: Feature dimension (product embedding size)
            learning_rate: VW learning rate for updates
        """
        self.dim = dim
        self.learning_rate = learning_rate
        self.interaction_count = 0

        # Vowpal Wabbit model stored as temporary file
        self.model_file = None
        self.vw = None
        self._init_vw()

    def _init_vw(self):
        """Initialize or load Vowpal Wabbit model."""
        if self.model_file is None:
            self.model_file = tempfile.NamedTemporaryFile(delete=False, suffix=".vw")
            self.model_file.close()

        # Create VW instance with appropriate settings for online learning
        # --loss_function=logistic: learns preference scores
        # --power_t=0: no power-scaling of learning rate
        # --adaptive: adapts learning rate per feature
        # --invert_hash: easier debugging
        vw_params = [
            "--loss_function=logistic",
            f"-d {self.model_file.name}",
            f"-f {self.model_file.name}",
            "--power_t=0",
            "--adaptive",
            f"--learning_rate={self.learning_rate}",
        ]

        try:
            self.vw = vowpalwabbit.Workspace(" ".join(vw_params), quiet=True)
        except Exception:
            # Fallback: try simpler initialization
            self.vw = vowpalwabbit.Workspace(
                f"-d {self.model_file.name} -f {self.model_file.name}", quiet=True
            )

    def learn_from_interaction(
        self,
        product_vec: np.ndarray,
        label: int,
        user_context: Optional[Dict] = None,
    ):
        """
        Learn from a single user interaction (online update).

        This updates the model based on what just happened:
        - User swiped product → like (label=1), dislike (label=-1), or skip (label=0)
        - Model immediately updates to reflect this feedback
        - Next prediction uses the updated model

        Args:
            product_vec: Product embedding (534-dim)
            label: 1 for like, -1 for dislike, 0 for skip
            user_context: Optional dict with skin type, preferences, etc.
        """
        if len(product_vec) != self.dim:
            raise ValueError(f"Expected {self.dim}-dim vector, got {len(product_vec)}")

        # Build VW feature string
        features = self._build_feature_string(product_vec, user_context)

        # Normalize label: VW expects {1, -1} for logistic
        vw_label = 1 if label > 0 else -1 if label < 0 else 0

        # Create VW example string format: "label |features"
        example = f"{vw_label} |product {features}"

        # Learn: VW updates its internal model based on this example
        self.vw.learn(example)
        self.interaction_count += 1

    def predict_preference(
        self,
        product_vec: np.ndarray,
        user_context: Optional[Dict] = None,
    ) -> Tuple[float, Dict]:
        """
        Predict user preference for a product given current model state.

        Output is a preference score that reflects:
        - What the model has learned from this user's swipes so far
        - With more swipes, predictions become more personalized

        Args:
            product_vec: Product embedding (534-dim)
            user_context: Optional user context (skin type, etc.)

        Returns:
            (preference_score, metadata_dict)

            preference_score: Float in range [-1, 1]
                1.0 = model predicts user will like
                0.0 = model is uncertain
                -1.0 = model predicts user will dislike
        """
        if len(product_vec) != self.dim:
            raise ValueError(f"Expected {self.dim}-dim vector, got {len(product_vec)}")

        features = self._build_feature_string(product_vec, user_context)
        example = f"|product {features}"

        # Predict but don't learn (no label)
        prediction = self.vw.predict(example)

        return float(prediction), {
            "interactions_learned": self.interaction_count,
            "confidence": abs(prediction),  # How confident is the model
        }

    def _build_feature_string(
        self,
        product_vec: np.ndarray,
        user_context: Optional[Dict] = None,
    ) -> str:
        """
        Build VW-format feature string from product vector and user context.

        VW format: "feature_name:feature_value feature_name:feature_value ..."
        Example: "prod_0:0.5 prod_1:-0.2 skin_type:oily budget:50"

        Args:
            product_vec: 534-dimensional product embedding
            user_context: Optional user metadata

        Returns:
            VW feature string
        """
        features = []

        # Product embedding features (sparse representation)
        for i, val in enumerate(product_vec):
            if val != 0:  # Only include non-zero features (sparsity)
                features.append(f"p{i}:{val:.4f}")

        # User context features
        if user_context:
            if "skin_type" in user_context:
                skin = user_context["skin_type"].lower().replace(" ", "_")
                features.append(f"skin_{skin}")

            if "budget" in user_context:
                features.append(f"budget:{user_context['budget']:.1f}")

            if "category_pref" in user_context:
                cat = user_context["category_pref"].lower().replace(" ", "_")
                features.append(f"cat_pref_{cat}")

            if "irritant_severity" in user_context:
                features.append(f"irritant:{user_context['irritant_severity']}")

        return " ".join(features) if features else ""

    def get_feature_importance(self, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Extract learned feature importance from the model.

        Shows which features (ingredients, attributes) the model learned
        are most important for predicting this user's preferences.

        Args:
            top_k: Number of top features to return

        Returns:
            List of (feature_name, importance_score) tuples
        """
        # Note: VW doesn't expose weights easily, this is a placeholder
        # In production, could save weights to file and parse
        return [
            ("learning_interactions", float(self.interaction_count)),
            ("model_state", "active"),
        ]

    def save(self, path: Path):
        """Save the model to disk."""
        if self.model_file:
            import shutil

            shutil.copy(self.model_file.name, path)

    def __del__(self):
        """Cleanup VW model file."""
        if self.model_file:
            try:
                Path(self.model_file.name).unlink()
            except:
                pass
        if self.vw:
            self.vw.finish()


class ContextualBanditStrategy:
    """
    Exploration-Exploitation strategy for online learning.

    Problem: Early on, model hasn't learned much. Should we:
    - Exploit: Show products model thinks user will like
    - Explore: Show diverse products to learn preferences

    This implements epsilon-greedy contextual bandits:
    - With probability epsilon: show random product (explore)
    - With probability (1-epsilon): show highest scored (exploit)
    - Epsilon decays over time: more explore early, more exploit later
    """

    def __init__(self, initial_epsilon: float = 0.8, decay_rate: float = 0.02):
        """
        Initialize contextual bandit strategy.

        Args:
            initial_epsilon: Probability of exploration (0-1)
            decay_rate: How fast epsilon decays (per interaction)
        """
        self.initial_epsilon = initial_epsilon
        self.decay_rate = decay_rate
        self.epsilon = initial_epsilon
        self.interaction_count = 0

    def select_product(
        self,
        candidate_scores: Dict[str, float],
        is_explore: Optional[bool] = None,
    ) -> Tuple[str, bool]:
        """
        Select which product to show next using epsilon-greedy strategy.

        Args:
            candidate_scores: Dict mapping product_id → model prediction score
            is_explore: Force explore/exploit, or None to use epsilon

        Returns:
            (product_id_to_show, was_exploration)
        """
        if not candidate_scores:
            raise ValueError("No candidates to select from")

        if is_explore is None:
            # Decide based on epsilon
            is_explore = np.random.random() < self.epsilon

        if is_explore:
            # Random product (exploration)
            product_id = np.random.choice(list(candidate_scores.keys()))
            was_exploration = True
        else:
            # Best product (exploitation)
            product_id = max(candidate_scores, key=candidate_scores.get)
            was_exploration = False

        # Update epsilon (decay over time)
        self.interaction_count += 1
        self.epsilon = self.initial_epsilon * np.exp(
            -self.decay_rate * self.interaction_count
        )

        return product_id, was_exploration

    def get_strategy_state(self) -> Dict:
        """Get current exploration/exploitation state."""
        return {
            "epsilon": float(self.epsilon),
            "interaction_count": self.interaction_count,
            "exploration_rate": float(self.epsilon),
            "exploitation_rate": float(1 - self.epsilon),
        }
