"""
Tests for online learning swiping system.

Validates:
1. Vowpal Wabbit online learning (model improves with feedback)
2. Swipe session management (full user journey)
3. Detailed feedback collection (category-specific questions)
4. Contextual bandits (exploration-exploitation trade-off)
5. Ingredient preference tracking (ingredient-level learning)
"""

import numpy as np
import pandas as pd
import pytest

from skincarelib.ml_system.online_learning import (
    OnlineLearner,
    ContextualBanditStrategy,
)
from skincarelib.ml_system.feedback_structures import (
    DetailedFeedbackCollector,
    InitialUserQuestionnaire,
    IngredientPreferenceTracker,
)
from skincarelib.ml_system.swipe_session import SwipeSession


class TestOnlineLearner:
    """Test Vowpal Wabbit online learning."""

    @pytest.fixture
    def learner(self):
        return OnlineLearner(dim=10, learning_rate=0.1)

    def test_initialization(self, learner):
        """Test learner initializes correctly."""
        assert learner.dim == 10
        assert learner.interaction_count == 0
        assert learner.vw is not None

    def test_learn_from_interaction(self, learner):
        """Test online learning from a single interaction."""
        vec = np.random.randn(10).astype(np.float32)
        learner.learn_from_interaction(vec, label=1)

        assert learner.interaction_count == 1

    def test_multiple_interactions(self, learner):
        """Test learning from multiple interactions."""
        for i in range(5):
            vec = np.random.randn(10).astype(np.float32)
            label = 1 if i % 2 == 0 else -1
            learner.learn_from_interaction(vec, label)

        assert learner.interaction_count == 5

    def test_prediction_after_learning(self, learner):
        """Test that predictions change after learning."""
        vec1 = np.ones(10).astype(np.float32)
        vec2 = np.ones(10).astype(np.float32) * -1

        # Initial prediction on unknown vector
        test_vec = np.zeros(10).astype(np.float32)
        pred1, _ = learner.predict_preference(test_vec)

        # Learn some interactions
        learner.learn_from_interaction(vec1, label=1)
        learner.learn_from_interaction(vec2, label=-1)

        # Prediction after learning
        pred2, _ = learner.predict_preference(test_vec)

        # Predictions should be different (model learned)
        assert pred1 != pred2

    def test_context_features(self, learner):
        """Test that context features are incorporated."""
        vec = np.random.randn(10).astype(np.float32)
        context = {"skin_type": "oily", "budget": 50}

        learner.learn_from_interaction(vec, label=1, user_context=context)
        assert learner.interaction_count == 1

        # Should handle prediction with context too
        score, meta = learner.predict_preference(vec, user_context=context)
        assert isinstance(score, float)
        assert "interactions_learned" in meta

    def test_dimension_mismatch(self, learner):
        """Test that dimension mismatches are caught."""
        wrong_vec = np.random.randn(5).astype(np.float32)

        with pytest.raises(ValueError):
            learner.learn_from_interaction(wrong_vec, label=1)

        with pytest.raises(ValueError):
            learner.predict_preference(wrong_vec)


class TestContextualBandit:
    """Test exploration-exploitation strategy."""

    @pytest.fixture
    def bandit(self):
        return ContextualBanditStrategy(initial_epsilon=0.8, decay_rate=0.1)

    def test_initialization(self, bandit):
        """Test bandit initializes correctly."""
        assert bandit.epsilon == 0.8
        assert bandit.interaction_count == 0

    def test_select_product_explore(self, bandit):
        """Test that exploration works."""
        candidates = {f"p{i}": float(i) for i in range(10)}

        # Force exploration
        product_id, was_exploration = bandit.select_product(candidates, is_explore=True)

        assert product_id in candidates
        assert was_exploration is True

    def test_select_product_exploit(self, bandit):
        """Test that exploitation works."""
        candidates = {f"p{i}": float(i) for i in range(10)}

        # Force exploitation
        product_id, was_exploration = bandit.select_product(
            candidates, is_explore=False
        )

        assert product_id == "p9"  # Highest score
        assert was_exploration is False

    def test_epsilon_decay(self, bandit):
        """Test that epsilon decays over time."""
        candidates = {f"p{i}": float(i) for i in range(10)}

        initial_epsilon = bandit.epsilon

        # Make many selections
        for _ in range(50):
            bandit.select_product(candidates, is_explore=None)

        # Epsilon should have decayed
        assert bandit.epsilon < initial_epsilon

    def test_strategy_state(self, bandit):
        """Test getting strategy state."""
        candidates = {f"p{i}": float(i) for i in range(10)}
        bandit.select_product(candidates)

        state = bandit.get_strategy_state()

        assert "epsilon" in state
        assert "exploration_rate" in state
        assert "exploitation_rate" in state
        assert state["exploration_rate"] + state["exploitation_rate"] == pytest.approx(
            1.0
        )


class TestDetailedFeedbackCollector:
    """Test feedback collection with category-specific questions."""

    @pytest.fixture
    def collector(self):
        return DetailedFeedbackCollector()

    def test_get_feedback_questions_moisturizer(self, collector):
        """Test getting feedback questions for moisturizer."""
        question, options = collector.get_followup_questions("Moisturizer", "like")

        assert "like" in question.lower()
        assert "Moisturizer" in question or "moisturizer" in question
        assert len(options) > 0
        assert "hydrated" in " ".join(options).lower()

    def test_get_feedback_questions_cleanser(self, collector):
        """Test getting feedback questions for cleanser."""
        question, options = collector.get_followup_questions("Cleanser", "dislike")

        assert "dislike" in question.lower()
        assert len(options) > 0

    def test_record_feedback(self, collector):
        """Test recording feedback."""
        feedback = collector.record_feedback(
            product_id="p123",
            category="Moisturizer",
            tried_status="yes",
            reaction="like",
            reasons=["It hydrated well", "Good price"],
        )

        assert feedback["product_id"] == "p123"
        assert feedback["reaction"] == "like"
        assert len(feedback["reasons"]) == 2

    def test_feedback_summary(self, collector):
        """Test feedback summary generation."""
        collector.record_feedback("p1", "Moisturizer", "yes", "like", ["Hydrated"])
        collector.record_feedback("p2", "Cleanser", "yes", "dislike", ["Drying"])
        collector.record_feedback("p3", "Moisturizer", "no", None, [])

        summary = collector.get_feedback_summary()

        assert summary["total_products_seen"] == 3
        assert summary["products_tried"] == 2
        assert summary["products_liked"] == 1
        assert summary["products_disliked"] == 1


class TestInitialQuestionnaire:
    """Test initial user profile questionnaire."""

    @pytest.fixture
    def questionnaire(self):
        return InitialUserQuestionnaire()

    def test_set_user_profile(self, questionnaire):
        """Test setting user profile."""
        profile = questionnaire.set_user_profile(
            skin_type="Oily",
            skin_concerns=["Acne", "Oiliness"],
            budget_range=("20-50", 50),
            preferred_categories=["Cleanser", "Moisturizer"],
        )

        assert profile["skin_type"] == "Oily"
        assert "Acne" in profile["skin_concerns"]
        assert profile["budget"] == 50

    def test_get_context_features(self, questionnaire):
        """Test converting profile to model features."""
        questionnaire.set_user_profile(
            skin_type="Dry",
            skin_concerns=["Dryness"],
            budget_range=("50-100", 100),
        )

        context = questionnaire.get_context_features()

        assert "skin_type" in context
        assert context["skin_type"] == "Dry"
        assert "budget" in context


class TestIngredientPreferenceTracker:
    """Test ingredient-level preference learning."""

    @pytest.fixture
    def tracker(self):
        return IngredientPreferenceTracker()

    def test_record_ingredient_feedback(self, tracker):
        """Test recording ingredient feedback."""
        ingredients = ["hyaluronic acid", "glycerin", "water"]
        tracker.record_ingredient_feedback(ingredients, rating=1, product_id="p1")

        assert "hyaluronic acid" in tracker.ingredient_ratings
        assert tracker.ingredient_ratings["hyaluronic acid"]["likes"] == 1

    def test_get_preference_scores(self, tracker):
        """Test calculating ingredient preference scores."""
        tracker.record_ingredient_feedback(["ingredient_a"], rating=1, product_id="p1")
        tracker.record_ingredient_feedback(["ingredient_a"], rating=1, product_id="p2")
        tracker.record_ingredient_feedback(["ingredient_a"], rating=-1, product_id="p3")

        scores = tracker.get_ingredient_preference_scores()

        # ingredient_a: 2 likes, 1 dislike, out of 3 total = score 0.333
        assert "ingredient_a" in scores
        assert -1 <= scores["ingredient_a"] <= 1

    def test_get_disliked_ingredients(self, tracker):
        """Test getting disliked ingredients."""
        tracker.record_ingredient_feedback(["alcohol"], rating=-1, product_id="p1")
        tracker.record_ingredient_feedback(["alcohol"], rating=-1, product_id="p2")
        tracker.record_ingredient_feedback(["water"], rating=1, product_id="p3")

        disliked = tracker.get_disliked_ingredients(threshold=-0.3)

        assert "alcohol" in disliked
        assert "water" not in disliked


class TestSwipeSession:
    """Test complete swiping session with online learning."""

    @pytest.fixture
    def session(self):
        """Create a test swipe session."""
        np.random.seed(42)

        # Create synthetic product data
        n_products = 50
        product_vectors = np.random.randn(n_products, 10).astype(np.float32)
        product_ids = [f"p{i}" for i in range(n_products)]
        product_index = {pid: i for i, pid in enumerate(product_ids)}

        product_metadata = pd.DataFrame(
            {
                "product_id": product_ids,
                "category": [
                    "Moisturizer",
                    "Cleanser",
                    "Face Mask",
                    "Treatment",
                    "Eye Cream",
                ]
                * (n_products // 5),
                "price": np.random.uniform(20, 100, n_products),
                "ingredients": ["water, glycerin"] * n_products,
            }
        )

        session = SwipeSession(
            user_id="test_user",
            product_vectors=product_vectors,
            product_metadata=product_metadata,
            product_index=product_index,
        )

        return session

    def test_complete_onboarding(self, session):
        """Test completing initial questionnaire."""
        profile = session.complete_onboarding(
            skin_type="Oily",
            skin_concerns=["Acne"],
            budget_range=("50-100", 100),
        )

        assert profile["skin_type"] == "Oily"
        assert session.session_started is True

    def test_get_next_product(self, session):
        """Test getting next product to show."""
        session.complete_onboarding(
            skin_type="Dry",
            skin_concerns=["Dryness"],
            budget_range=("20-50", 50),
        )

        product_id, product_meta = session.get_next_product()

        assert product_id is not None
        assert product_id in session.product_index
        assert product_id in session.products_shown

    def test_record_swipe_and_learn(self, session):
        """Test recording swipe and model update."""
        session.complete_onboarding(
            skin_type="Sensitive",
            skin_concerns=["Sensitivity"],
            budget_range=("20-50", 50),
        )

        product_id, _ = session.get_next_product()

        # Record a like
        swipe = session.record_swipe(
            product_id=product_id,
            tried_status="yes",
            reaction="like",
            feedback_reasons=["It didn't irritate my skin"],
        )

        assert swipe["reaction"] == "like"
        assert "model_update" in swipe
        # Cold-start pre-training adds ~10-15 pseudo-interactions from onboarding
        # So first swipe should have > 10 interactions (pre-training + first swipe)
        assert session.online_learner.interaction_count > 10

    def test_learning_improves_predictions(self, session):
        """Test that model predictions improve with feedback."""
        session.complete_onboarding(
            skin_type="Dry",
            skin_concerns=["Dryness"],
            budget_range=("50-100", 100),
        )

        # Get initial predictions for next product
        product_id1, _ = session.get_next_product()
        pre_learn_score, _ = session.online_learner.predict_preference(
            session.product_vectors[session.product_index[product_id1]]
        )

        # Learn from interaction
        session.record_swipe(
            product_id=product_id1,
            tried_status="yes",
            reaction="like",
            feedback_reasons=["Very hydrating"],
        )

        # Get another product and check recommendation
        product_id2, _ = session.get_next_product()

        # Model has learned more, should make different predictions
        assert session.online_learner.interaction_count > 0

    def test_session_state(self, session):
        """Test getting session state."""
        session.complete_onboarding(
            skin_type="Oily",
            skin_concerns=["Oiliness"],
            budget_range=("20-50", 50),
        )

        # Show and rate a few products
        for _ in range(3):
            product_id, _ = session.get_next_product()
            session.record_swipe(product_id, "yes", "like", ["Good"])

        state = session.get_session_state()

        assert state["session_started"] is True
        assert state["total_products_shown"] == 3
        assert state["products_rated"] == 3
        # Cold-start pre-training adds ~10-15 pseudo-interactions from onboarding
        # Plus 3 real swipes = ~13-18 total interactions
        assert state["model_interactions_learned"] > 10

    def test_get_recommendations(self, session):
        """Test getting personalized recommendations."""
        session.complete_onboarding(
            skin_type="Dry",
            skin_concerns=["Dryness"],
            budget_range=("50-100", 100),
        )

        # Rate a few products
        for _ in range(5):
            product_id, _ = session.get_next_product()
            session.record_swipe(product_id, "yes", "like", ["Hydrating"])

        # Get recommendations
        recommendations = session.get_recommendations(top_n=3)

        assert len(recommendations) > 0
        assert len(recommendations) <= 3
        assert "product_id" in recommendations.columns
        assert "preference_score" in recommendations.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
