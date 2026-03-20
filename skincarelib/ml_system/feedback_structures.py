"""
Detailed Feedback Collector for swiping interface.

Captures structured feedback based on product category and user reaction.
This enables:
1. Better understanding of user preferences
2. Ingredient-level preference tracking
3. More informative model training
4. Richer user profile understanding
"""

from typing import Dict, List, Optional, Tuple


# Category-specific follow-up questions
FEEDBACK_QUESTIONS = {
    "Cleanser": {
        "like": [
            "Made my skin dry/tight",
            "Didn't clean well",
            "Irritated my skin",
            "Broke me out",
            "Price too high",
            "Other",
        ],
        "dislike": [
            "Not drying",
            "Very gentle",
            "Helped with oil control",
            "Good price to quality",
            "Other",
        ],
    },
    "Moisturizer": {
        "like": [
            "It hydrated well",
            "It absorbed quickly",
            "It felt lightweight",
            "It didn't irritate my skin",
            "Good price to quality",
            "Other",
        ],
        "dislike": [
            "Too greasy",
            "Not moisturizing enough",
            "Felt sticky",
            "Broke me out",
            "Price too high",
            "Other",
        ],
    },
    "Face Mask": {
        "like": [
            "Skin felt smoother",
            "More hydrated",
            "Skin looked brighter",
            "Helped with oil/acne",
            "Good price to quality",
            "Other",
        ],
        "dislike": [
            "Smelled bad",
            "Burned or stung",
            "Too drying",
            "Didn't see results",
            "Uncomfortable",
            "Price too high",
            "Other",
        ],
    },
    "Treatment": {
        "like": [
            "Helped with acne",
            "Helped with dark spots",
            "Helped with hydration",
            "Helped with skin texture",
            "Helped with wrinkles",
            "Good price to quality",
            "Other",
        ],
        "dislike": [
            "Irritated my skin",
            "Didn't work",
            "Too strong",
            "Broke me out",
            "Price too high",
            "Other",
        ],
    },
    "Eye Cream": {
        "like": [
            "Improved dryness",
            "Improved dark circles",
            "Improved puffiness",
            "Improved fine lines",
            "Improved eye bags",
            "Moisturizing",
            "Good price to quality",
            "Other",
        ],
        "dislike": [
            "Irritated my eyes",
            "Too heavy",
            "Didn't work",
            "Caused bumps",
            "Price too high",
            "Other",
        ],
    },
    "Sun Protect": {
        "like": [
            "Didn't irritate my skin",
            "Absorbed well",
            "Felt lightweight",
            "Didn't leave white cast",
            "Good price to quality",
            "Other",
        ],
        "dislike": [
            "Left white cast",
            "Felt greasy",
            "Broke me out",
            "Irritated my skin",
            "Caused sunburn",
            "Price too high",
            "Other",
        ],
    },
}

# Default questions for unknown categories
DEFAULT_QUESTIONS = {
    "like": ["Good quality", "Good price", "Good performance", "Other"],
    "dislike": ["Poor quality", "High price", "Didn't work", "Other"],
}

# Questions about why they haven't tried
TRIED_STATUS_QUESTIONS = {
    "yes": {"reaction": "What did you think of it?"},
    "no": {"reason": "Why haven't you tried it?"},
}


class DetailedFeedbackCollector:
    """
    Collects detailed structured feedback from users based on product type.
    
    Flow:
    1. User sees product
    2. "Have you tried this?" → Yes/No
    3. If Yes: "Did you like it?" → Like/Dislike/Neutral
    4. If Like/Dislike: Category-specific follow-up: "What did you like most?"
    5. User selects reason(s) → Feedback recorded
    
    Output: Rich user preference signal linked to product attributes
    """
    
    def __init__(self):
        self.feedback_history: List[Dict] = []
    
    def get_tried_status_questions(self) -> Dict[str, str]:
        """Initial question about whether user has tried the product."""
        return TRIED_STATUS_QUESTIONS
    
    def get_reaction_options(self) -> List[str]:
        """Options for product reaction (for users who have tried it)."""
        return ["Like it", "Dislike it", "Neutral"]
    
    def get_followup_questions(
        self,
        category: str,
        reaction: str,
    ) -> Tuple[str, List[str]]:
        """
        Get category-specific follow-up questions based on reaction.
        
        Args:
            category: Product category (Cleanser, Moisturizer, etc.)
            reaction: User's reaction (like, dislike)
            
        Returns:
            (question_text, list_of_options)
        """
        category = category.strip().title()
        reaction = reaction.lower().strip()
        
        if reaction not in ["like", "dislike"]:
            return "Not applicable", []
        
        if category in FEEDBACK_QUESTIONS:
            questions = FEEDBACK_QUESTIONS[category]
            options = questions.get(reaction, [])
        else:
            options = DEFAULT_QUESTIONS.get(reaction, [])
        
        # Build question text
        if reaction == "like":
            question_text = f"What did you like most about this {category.lower()}?"
        else:
            question_text = f"What did you dislike about this {category.lower()}?"
        
        return question_text, options
    
    def record_feedback(
        self,
        product_id: str,
        category: str,
        tried_status: str,
        reaction: Optional[str] = None,
        reasons: Optional[List[str]] = None,
    ) -> Dict:
        """
        Record user feedback for a product.
        
        Args:
            product_id: Product identifier
            category: Product category
            tried_status: "yes" or "no" (have you tried this)
            reaction: "like", "dislike", or "neutral" (if tried)
            reasons: List of reasons selected from follow-up questions
            
        Returns:
            Feedback record dict
        """
        feedback = {
            "product_id": product_id,
            "category": category,
            "tried_status": tried_status,
            "reaction": reaction,
            "reasons": reasons or [],
        }
        
        self.feedback_history.append(feedback)
        return feedback
    
    def get_feedback_summary(self) -> Dict:
        """Get summary of feedback collected so far."""
        if not self.feedback_history:
            return {"total_products": 0, "feedback_count": 0}
        
        total = len(self.feedback_history)
        tried = sum(1 for f in self.feedback_history if f["tried_status"] == "yes")
        liked = sum(1 for f in self.feedback_history if f["reaction"] == "like")
        disliked = sum(1 for f in self.feedback_history if f["reaction"] == "dislike")
        
        return {
            "total_products_seen": total,
            "products_tried": tried,
            "products_liked": liked,
            "products_disliked": disliked,
            "engagement_rate": tried / total if total > 0 else 0,
        }


class InitialUserQuestionnaire:
    """
    Captures user's initial preferences before swiping starts.
    
    This helps the model start with better cold-start recommendations.
    """
    
    SKIN_TYPES = ["Dry", "Oily", "Sensitive", "Combination", "Normal"]
    
    SKIN_CONCERNS = [
        "Acne",
        "Dark spots",
        "Dryness",
        "Oiliness",
        "Sensitivity",
        "Wrinkles",
        "Dull skin",
    ]
    
    BUDGET_RANGES = [
        ("0-20", 20),
        ("20-50", 50),
        ("50-100", 100),
        ("100+", 999),
    ]
    
    def __init__(self):
        self.user_profile: Dict = {}
    
    def get_skin_type_options(self) -> List[str]:
        """Available skin type options."""
        return self.SKIN_TYPES
    
    def get_skin_concerns_options(self) -> List[str]:
        """Available skin concern options."""
        return self.SKIN_CONCERNS
    
    def get_budget_options(self) -> List[Tuple[str, float]]:
        """Available budget ranges."""
        return self.BUDGET_RANGES
    
    def set_user_profile(
        self,
        skin_type: str,
        skin_concerns: List[str],
        budget_range: Tuple[str, float],
        preferred_categories: Optional[List[str]] = None,
    ) -> Dict:
        """
        Set user's initial profile from questionnaire responses.
        
        Args:
            skin_type: One of the SKIN_TYPES
            skin_concerns: List of concerns from SKIN_CONCERNS
            budget_range: One of the BUDGET_RANGES tuples
            preferred_categories: Optional list of preferred product categories
            
        Returns:
            User profile dict
        """
        self.user_profile = {
            "skin_type": skin_type,
            "skin_concerns": skin_concerns,
            "budget": budget_range[1],  # Max budget
            "budget_label": budget_range[0],
            "preferred_categories": preferred_categories or [],
        }
        
        return self.user_profile
    
    def get_user_profile(self) -> Dict:
        """Get the user's profile."""
        return self.user_profile
    
    def get_context_features(self) -> Dict:
        """Convert profile to features for model context."""
        profile = self.user_profile
        context = {}
        
        if profile.get("skin_type"):
            context["skin_type"] = profile["skin_type"]
        
        if profile.get("budget"):
            context["budget"] = profile["budget"]
        
        if profile.get("skin_concerns"):
            # Convert concerns to features
            concern_str = "|".join(
                c.lower().replace(" ", "_") for c in profile["skin_concerns"]
            )
            context["concerns"] = concern_str
        
        return context


class IngredientPreferenceTracker:
    """
    Tracks which ingredients users like/dislike.
    
    Enables the model to learn patterns at the ingredient level:
    - "This user dislikes products with alcohol"
    - "This user loves products with hyaluronic acid"
    
    This is more interpretable than raw embedding similarities.
    """
    
    def __init__(self):
        self.ingredient_ratings: Dict[str, Dict] = {}
        self.co_occurrence: Dict[Tuple[str, str], int] = {}
    
    def record_ingredient_feedback(
        self,
        ingredients: List[str],
        rating: int,
        product_id: str,
    ):
        """
        Record feedback for product with specific ingredients.
        
        Args:
            ingredients: List of ingredient names in the product
            rating: 1 for like, -1 for dislike, 0 for neutral
            product_id: Product identifier for traceability
        """
        ingredients = [ing.lower().strip() for ing in ingredients]
        
        for ing in ingredients:
            if ing not in self.ingredient_ratings:
                self.ingredient_ratings[ing] = {
                    "likes": 0,
                    "dislikes": 0,
                    "neutral": 0,
                    "products": [],
                }
            
            if rating > 0:
                self.ingredient_ratings[ing]["likes"] += 1
            elif rating < 0:
                self.ingredient_ratings[ing]["dislikes"] += 1
            else:
                self.ingredient_ratings[ing]["neutral"] += 1
            
            self.ingredient_ratings[ing]["products"].append(product_id)
        
        # Track ingredient co-occurrence
        for i, ing1 in enumerate(ingredients):
            for ing2 in ingredients[i + 1 :]:
                key = tuple(sorted([ing1, ing2]))
                self.co_occurrence[key] = self.co_occurrence.get(key, 0) + 1
    
    def get_ingredient_preference_scores(self) -> Dict[str, float]:
        """
        Calculate preference score for each ingredient.
        
        Score = (likes - dislikes) / (total occurrences)
        Range: [-1, 1]
        
        Returns:
            Dict mapping ingredient → preference_score
        """
        scores = {}
        for ing, data in self.ingredient_ratings.items():
            total = data["likes"] + data["dislikes"] + data["neutral"]
            if total > 0:
                score = (data["likes"] - data["dislikes"]) / total
                scores[ing] = score
        
        return scores
    
    def get_disliked_ingredients(self, threshold: float = -0.5) -> List[str]:
        """
        Get ingredients user likely dislikes.
        
        Args:
            threshold: Score below which ingredient is considered disliked
            
        Returns:
            List of disliked ingredients
        """
        scores = self.get_ingredient_preference_scores()
        return [ing for ing, score in scores.items() if score < threshold]
    
    def get_liked_ingredients(self, threshold: float = 0.5) -> List[str]:
        """
        Get ingredients user likely likes.
        
        Args:
            threshold: Score above which ingredient is considered liked
            
        Returns:
            List of liked ingredients
        """
        scores = self.get_ingredient_preference_scores()
        return [ing for ing, score in scores.items() if score > threshold]
    
    def get_ingredient_summary(self) -> Dict:
        """Get summary of ingredient preferences."""
        scores = self.get_ingredient_preference_scores()
        
        if not scores:
            return {"total_ingredients": 0}
        
        return {
            "total_ingredients": len(scores),
            "top_3_liked": sorted(
                scores.items(), key=lambda x: x[1], reverse=True
            )[:3],
            "top_3_disliked": sorted(scores.items(), key=lambda x: x[1])[:3],
            "mean_preference": float(np.mean(list(scores.values()))),
        }


import numpy as np
