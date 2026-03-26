"""
Logistic Regression-based feedback learning model.

Replaces the simple weighted average approach with a real ML model
that learns the relationship between product features and user preferences.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent.parent


class FeedbackLogisticRegression:
    """
    Trains a logistic regression model to predict user preference scores
    from product feature vectors and feedback history.
    
    Instead of using fixed weights (+2.0 for liked, -1.0 for disliked, -2.0 for irritation),
    this model learns optimal weights from observed feedback patterns.
    
    Approach:
    1. Convert feedback interactions into a classification problem:
       - Liked → class 1 (preference > threshold)
       - Disliked → class 0 (preference < threshold)
       - Irritation → class -1 (strong negative)
    2. Train logistic regression with product vectors as features
    3. Use model coefficients as learned preference weights
    4. Generate user vector by weighted average using learned coefficients
    """
    
    def __init__(self, dim: int = 534):
        """
        Initialize the feedback learning model.
        
        Args:
            dim: Feature dimension (should match product vector dimension)
        """
        self.dim = dim
        self.user_id: Optional[str] = None
        self.model: Optional[LogisticRegression] = None
        self.scaler: Optional[StandardScaler] = None
        self.feedback_history: List[Tuple[np.ndarray, int]] = []
        self.is_trained = False

    def bind_user(self, user_id: str):
        """Bind this model instance to a specific user to avoid cross-user leakage."""
        if self.user_id is None:
            self.user_id = str(user_id)
            return
        if self.user_id != str(user_id):
            raise ValueError(
                f"FeedbackLogisticRegression is already bound to user '{self.user_id}'. "
                f"Create a new instance for user '{user_id}'."
            )

    def reset_feedback_history(self):
        """Clear in-memory training history and reset fitted state."""
        self.feedback_history = []
        self.model = None
        self.scaler = None
        self.is_trained = False
        
    def add_feedback(self, product_vec: np.ndarray, feedback_label: int):
        """
        Record a feedback interaction for training.
        
        Args:
            product_vec: Product feature vector (shape: (dim,))
            feedback_label: 1 for liked, 0 for disliked, -1 for irritation
        """
        if len(product_vec) != self.dim:
            raise ValueError(f"Expected vector dim {self.dim}, got {len(product_vec)}")
        if feedback_label not in {1, 0, -1}:
            raise ValueError(f"feedback_label must be one of {{1, 0, -1}}, got {feedback_label}")
        self.feedback_history.append((product_vec.copy(), feedback_label))
    
    def train(self, min_samples: int = 3) -> bool:
        """
        Train the logistic regression model on accumulated feedback.
        
        Args:
            min_samples: Minimum number of interactions needed to train
            
        Returns:
            True if training succeeded, False if insufficient data
        """
        if len(self.feedback_history) < min_samples:
            self.is_trained = False
            return False
        
        # Convert feedback history to arrays
        X = np.array([vec for vec, _ in self.feedback_history], dtype=np.float32)
        y = np.array([label for _, label in self.feedback_history], dtype=np.int32)
        
        # Handle multi-class case (liked=1, disliked=0, irritation=-1)
        # Remap to 0,1,2 for sklearn
        y_remapped = np.zeros_like(y)
        y_remapped[y == 1] = 1      # liked -> class 1
        y_remapped[y == 0] = 0      # disliked -> class 0
        y_remapped[y == -1] = 2     # irritation -> class 2
        
        # Standardize features for better LR convergence
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train multi-class logistic regression
        self.model = LogisticRegression(
            solver='lbfgs',
            max_iter=1000,
            random_state=42,
            class_weight='balanced'  # Handle class imbalance
        )
        self.model.fit(X_scaled, y_remapped)
        self.is_trained = True
        return True
    
    def predict_preference_score(self, product_vec: np.ndarray) -> float:
        """
        Predict user preference score for a single product.
        
        Combines class probabilities weighted by preference direction:
        - If 3 classes present: score = P(liked) - P(disliked) - 2*P(irritation)
        - If 2 classes present: handles both (0,1) and (1,2) combinations
        - If 1 class: returns 0
        
        Args:
            product_vec: Product feature vector (shape: (dim,))
            
        Returns:
            Preference score 
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        
        if len(product_vec) != self.dim:
            raise ValueError(f"Expected vector dim {self.dim}, got {len(product_vec)}")
        
        X_scaled = self.scaler.transform([product_vec])
        probs = self.model.predict_proba(X_scaled)[0]
        n_classes = len(probs)
        
        # Handle different numbers of classes
        if n_classes == 3:
            # All classes present: disliked(0), liked(1), irritation(2)
            score = probs[1] - probs[0] - 2.0 * probs[2]
        elif n_classes == 2:
            # Check which classes are present based on model.classes_
            classes = self.model.classes_
            if 0 in classes and 1 in classes:
                # disliked(0) and liked(1)
                score = probs[1] - probs[0]
            elif 1 in classes and 2 in classes:
                # liked(1) and irritation(2)
                score = probs[0] - 2.0 * probs[1]
            else:
                # other combinations
                score = probs[1] - probs[0]
        else:
            # Only one class - neutral preference
            score = 0.0
        
        return float(score)
    
    def get_learned_weights(self) -> Optional[np.ndarray]:
        """
        Extract learned feature weights from the model.
        
        Returns the coefficient magnitude from the trained logistic regression
        as a proxy for feature importance in the preference model.
        
        Returns:
            Weight vector (shape: (dim,)) or None if not trained
        """
        if not self.is_trained or self.model is None:
            return None
        
        # Average absolute coefficients across classes
        weights = np.abs(self.model.coef_).mean(axis=0)
        # Normalize to [0, 1] for interpretability
        weights = weights / (np.max(weights) + 1e-9)
        return weights.astype(np.float32)
    
    def save(self, path: Path):
        """Save trained model with scaler to disk."""
        artifacts = {
            'model': self.model,
            'scaler': self.scaler,
            'dim': self.dim,
            'user_id': self.user_id,
            'is_trained': self.is_trained,
            'feedback_history': self.feedback_history,
        }
        joblib.dump(artifacts, path)
    
    @classmethod
    def load(cls, path: Path) -> 'FeedbackLogisticRegression':
        """Load a previously trained model from disk."""
        artifacts = joblib.load(path)
        instance = cls(dim=artifacts['dim'])
        instance.user_id = artifacts.get('user_id')
        instance.model = artifacts['model']
        instance.scaler = artifacts['scaler']
        instance.is_trained = artifacts['is_trained']
        instance.feedback_history = artifacts['feedback_history']
        return instance
