"""
Swipe Session Manager for real-time online learning recommendations.

Manages the complete user journey:
1. Initial questionnaire (skin type, concerns, budget)
2. For each swipe:
   - Show product (using current model predictions)
   - Collect feedback (like/dislike/skip + detailed reasons)
   - Update model immediately (Vowpal Wabbit online learning)
   - Rank next products based on updated model
3. Track learning progress (how personalized the recommendations become)
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from skincarelib.ml_system.online_learning import OnlineLearner, ContextualBanditStrategy
from skincarelib.ml_system.feedback_structures import (
    DetailedFeedbackCollector,
    InitialUserQuestionnaire,
    IngredientPreferenceTracker,
)


class SwipeSession:
    """
    Manages a complete user swiping session with online learning.
    
    Flow:
    1. User completes onboarding (skin type, concerns, budget)
    2. System shows products using contextual bandits:
       - Early: explore (show diverse products)
       - Later: exploit (show personalized products)
    3. User swipes (like/dislike/skip) + provides detailed feedback
    4. Model updates immediately based on feedback
    5. Next product is ranked using updated model
    6. Repeat until user stops
    """
    
    def __init__(
        self,
        user_id: str,
        product_vectors: np.ndarray,
        product_metadata: pd.DataFrame,
        product_index: Dict[str, int],
        learning_rate: float = 0.1,
        initial_epsilon: float = 0.8,
    ):
        """
        Initialize a new swipe session.
        
        Args:
            user_id: Unique user identifier
            product_vectors: N x D matrix of product embeddings (534-dim)
            product_metadata: DataFrame with columns [product_id, category, ingredients...]
            product_index: Dict mapping product_id → row index in product_vectors
            learning_rate: VW learning rate
            initial_epsilon: Initial exploration probability
        """
        self.user_id = user_id
        self.product_vectors = product_vectors
        self.product_metadata = product_metadata
        self.product_index = product_index
        
        # Initialize components
        self.questionnaire = InitialUserQuestionnaire()
        self.feedback_collector = DetailedFeedbackCollector()
        self.ingredient_tracker = IngredientPreferenceTracker()
        self.online_learner = OnlineLearner(dim=product_vectors.shape[1], learning_rate=learning_rate)
        self.bandit_strategy = ContextualBanditStrategy(initial_epsilon=initial_epsilon)
        
        # Session state
        self.session_started = False
        self.products_shown: List[str] = []
        self.products_rated: Dict[str, Dict] = {}
        self.swipe_history: List[Dict] = []
    
    def complete_onboarding(
        self,
        skin_type: str,
        skin_concerns: List[str],
        budget_range: Tuple[str, float],
        preferred_categories: Optional[List[str]] = None,
    ) -> Dict:
        """
        Complete initial questionnaire to establish user profile.
        
        Args:
            skin_type: One of InitialUserQuestionnaire.SKIN_TYPES
            skin_concerns: List of skin concerns
            budget_range: Budget range tuple (label, max_value)
            preferred_categories: Optional product categories to focus on
            
        Returns:
            User profile dict
        """
        profile = self.questionnaire.set_user_profile(
            skin_type=skin_type,
            skin_concerns=skin_concerns,
            budget_range=budget_range,
            preferred_categories=preferred_categories or [],
        )
        
        self.session_started = True
        
        # Pre-seed models with onboarding data (cold-start boost)
        self._seed_models_from_onboarding(skin_type, skin_concerns)
        
        return profile
    
    def _seed_models_from_onboarding(self, skin_type: str, skin_concerns: List[str]):
        """
        Pre-train models with pseudo-feedback derived from onboarding answers.
        
        Improves cold-start: models learn from skin type + concerns BEFORE first swipe.
        
        Strategy:
        1. Find products suitable for user's skin type & concerns
        2. Add them as pseudo-likes (strength: 50% of real like)
        3. Find products NOT suitable (opposite profile)
        4. Add them as pseudo-dislikes
        5. This gives models initial training data for better Day 1 recommendations
        
        Args:
            skin_type: User's skin type (Dry, Oily, Sensitive, etc.)
            skin_concerns: List of user's skin concerns (Acne, Dryness, etc.)
        """
        if self.product_metadata.empty:
            return  # No metadata to work with
        
        user_context = self.questionnaire.get_context_features()
        skin_type_lower = skin_type.lower()
        concerns_lower = [c.lower() for c in skin_concerns]
        
        # Score products based on metadata match
        suited_products = []  # Good for this user
        unsuited_products = []  # Bad for this user
        
        for idx, row in self.product_metadata.iterrows():
            product_id = str(row.get("product_id", ""))
            if product_id not in self.product_index:
                continue
            
            # Check if product metadata mentions skin type or concerns
            product_name = str(row.get("name", "")).lower()
            product_category = str(row.get("category", "")).lower()
            product_description = str(row.get("description", "")).lower()
            product_text = f"{product_name} {product_category} {product_description}"
            
            # Match score: how many keywords match
            match_count = sum(1 for concern in concerns_lower if concern in product_text)
            match_count += sum(1 for concern in concerns_lower if any(
                keyword in product_text for keyword in 
                ["acne", "oil control", "hydrat", "moistur", "sensitive", "gentle", "anti-aging", "wrinkle"]
            ))
            
            if match_count > 0:
                suited_products.append((product_id, match_count))
            else:
                unsuited_products.append(product_id)
        
        # Add top-matched products as pseudo-likes (to seed the model)
        if suited_products:
            # Sort by match count and take top 30%
            suited_products.sort(key=lambda x: x[1], reverse=True)
            top_count = max(1, len(suited_products) // 3)
            
            for product_id, _ in suited_products[:top_count]:
                if product_id in self.product_index:
                    idx = self.product_index[product_id]
                    vec = self.product_vectors[idx]
                    
                    # Add as pseudo-like to online learner (seed VW model)
                    self.online_learner.learn_from_interaction(
                        product_vec=vec,
                        label=1,  # Like
                        user_context=user_context,
                    )
        
        # Add unsuitable products as pseudo-dislikes
        if unsuited_products:
            dislike_count = max(1, len(unsuited_products) // 4)
            for product_id in unsuited_products[:dislike_count]:
                if product_id in self.product_index:
                    idx = self.product_index[product_id]
                    vec = self.product_vectors[idx]
                    
                    self.online_learner.learn_from_interaction(
                        product_vec=vec,
                        label=-1,  # Dislike
                        user_context=user_context,
                    )
    
    def get_next_product(self) -> Optional[Tuple[str, Dict]]:
        """
        Get the next product to show to the user.
        
        Uses contextual bandits to balance exploration/exploitation:
        - Early in session: show diverse products (exploration)
        - As session progresses: show personalized products (exploitation)
        
        Returns:
            (product_id, product_metadata_dict) or None if no valid candidates
        """
        if not self.session_started:
            return None
        
        # Get available products (exclude already shown)
        candidate_ids = [
            pid for pid in self.product_index.keys()
            if pid not in self.products_shown
        ]
        
        if not candidate_ids:
            return None
        
        # Get user context from questionnaire
        user_context = self.questionnaire.get_context_features()
        
        # Score all candidates using current model
        candidate_scores = {}
        for product_id in candidate_ids:
            if product_id not in self.product_index:
                continue
            
            idx = self.product_index[product_id]
            product_vec = self.product_vectors[idx]
            score, _ = self.online_learner.predict_preference(product_vec, user_context)
            candidate_scores[product_id] = float(score)
        
        if not candidate_scores:
            return None
        
        # Use contextual bandit to select next product
        selected_product_id, was_exploration = self.bandit_strategy.select_product(
            candidate_scores
        )
        
        # Track that we showed this product
        self.products_shown.append(selected_product_id)
        
        # Get product metadata
        product_meta = self.product_metadata[
            self.product_metadata["product_id"] == selected_product_id
        ].to_dict("records")[0] if not self.product_metadata[
            self.product_metadata["product_id"] == selected_product_id
        ].empty else {}
        
        product_meta["exploration_action"] = was_exploration
        product_meta["confidence_score"] = candidate_scores[selected_product_id]
        
        return selected_product_id, product_meta
    
    def record_swipe(
        self,
        product_id: str,
        tried_status: str,  # "yes" or "no"
        reaction: Optional[str] = None,  # "like", "dislike", "neutral"
        feedback_reasons: Optional[List[str]] = None,
    ) -> Dict:
        """
        Record user's swipe and update model online.
        
        This is the key part: immediately after user swipes, we:
        1. Record their feedback
        2. Extract ingredients from product
        3. Update online learning model (Vowpal Wabbit)
        4. Track ingredient preferences
        5. Next product recommendation uses updated model
        
        Args:
            product_id: Product that was swiped
            tried_status: "yes" (they've tried it) or "no"
            reaction: "like", "dislike", or "neutral" (if tried_status=="yes")
            feedback_reasons: Detailed feedback reasons selected
            
        Returns:
            Swipe record dict with learning update info
        """
        if product_id not in self.product_index:
            raise ValueError(f"Unknown product: {product_id}")
        
        # Record feedback
        self.feedback_collector.record_feedback(
            product_id=product_id,
            category=self.product_metadata.loc[
                self.product_metadata["product_id"] == product_id, "category"
            ].values[0] if product_id in self.product_metadata["product_id"].values else "Unknown",
            tried_status=tried_status,
            reaction=reaction,
            reasons=feedback_reasons or [],
        )
        
        swipe_record = {
            "product_id": product_id,
            "tried_status": tried_status,
            "reaction": reaction,
            "feedback_reasons": feedback_reasons or [],
            "model_update": None,
        }
        
        # If user tried the product, update the model
        if tried_status == "yes" and reaction:
            # Convert reaction to label: like=1, dislike=-1, neutral=0
            label_map = {"like": 1, "dislike": -1, "neutral": 0}
            label = label_map.get(reaction, 0)
            
            # Get product vector
            idx = self.product_index[product_id]
            product_vec = self.product_vectors[idx]
            
            # Get user context
            user_context = self.questionnaire.get_context_features()
            
            # ONLINE LEARNING: Update model based on this interaction
            self.online_learner.learn_from_interaction(
                product_vec=product_vec,
                label=label,
                user_context=user_context,
            )
            
            swipe_record["model_update"] = {
                "label": label,
                "interactions_learned": self.online_learner.interaction_count,
            }
            
            # Track ingredient preferences
            if "ingredients" in self.product_metadata.columns:
                product_row = self.product_metadata[
                    self.product_metadata["product_id"] == product_id
                ]
                if not product_row.empty:
                    ingredients_str = product_row["ingredients"].values[0]
                    if isinstance(ingredients_str, str):
                        ingredients = [ing.strip() for ing in ingredients_str.split(",")]
                        self.ingredient_tracker.record_ingredient_feedback(
                            ingredients=ingredients,
                            rating=label,
                            product_id=product_id,
                        )
        
        self.products_rated[product_id] = swipe_record
        self.swipe_history.append(swipe_record)
        
        return swipe_record
    
    def get_session_state(self) -> Dict:
        """
        Get current session state and learning progress.
        
        Returns:
            Dict with session metrics and learning progress
        """
        feedback_summary = self.feedback_collector.get_feedback_summary()
        ingredient_summary = self.ingredient_tracker.get_ingredient_summary()
        bandit_state = self.bandit_strategy.get_strategy_state()
        
        return {
            "user_id": self.user_id,
            "session_started": self.session_started,
            "total_products_shown": len(self.products_shown),
            "products_rated": len(self.products_rated),
            "feedback_summary": feedback_summary,
            "ingredient_preferences": ingredient_summary,
            "model_interactions_learned": self.online_learner.interaction_count,
            "exploration_exploitation": bandit_state,
            "user_profile": self.questionnaire.get_user_profile(),
        }
    
    def get_recommendations(self, top_n: int = 5) -> pd.DataFrame:
        """
        Get top N personalized recommendations based on current model.
        
        This shows what the model currently predicts the user will like,
        based on what they've swiped so far.
        
        Args:
            top_n: Number of recommendations to return
            
        Returns:
            DataFrame with top products and confidence scores
        """
        # Get user context
        user_context = self.questionnaire.get_context_features()
        
        # Score all products
        scores = []
        for product_id in self.product_index.keys():
            if product_id in self.products_shown:
                continue  # Skip already shown
            
            idx = self.product_index[product_id]
            product_vec = self.product_vectors[idx]
            score, metadata = self.online_learner.predict_preference(
                product_vec, user_context
            )
            scores.append({
                "product_id": product_id,
                "preference_score": score,
                "confidence": metadata["confidence"],
                "interactions_learned_from": metadata["interactions_learned"],
            })
        
        # Sort by score and get top N
        recommendations = pd.DataFrame(scores).nlargest(top_n, "preference_score")
        
        # Merge with product metadata
        recommendations = recommendations.merge(
            self.product_metadata,
            on="product_id",
            how="left"
        )
        
        return recommendations
    
    def get_learning_curves(self) -> Dict:
        """
        Get metrics showing how model is improving over time.
        
        Shows:
        - How engagement is changing (more likes as model learns?)
        - Ingredient preference convergence
        - Model confidence growth
        
        Returns:
            Dict with learning curves data
        """
        if not self.swipe_history:
            return {}
        
        # Engagement trend (moving average of like rate)
        interactions = [
            s for s in self.swipe_history if s["reaction"] in ["like", "dislike"]
        ]
        
        if not interactions:
            return {}
        
        like_count = sum(1 for s in interactions if s["reaction"] == "like")
        total_rated = len(interactions)
        
        return {
            "total_interactions": total_rated,
            "like_rate": like_count / total_rated if total_rated > 0 else 0,
            "exploration_rate": self.bandit_strategy.epsilon,
            "exploitation_rate": 1 - self.bandit_strategy.epsilon,
            "ingredients_tracked": len(self.ingredient_tracker.ingredient_ratings),
        }
