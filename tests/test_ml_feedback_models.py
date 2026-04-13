"""
Tests for ML-based feedback models.
"""

import numpy as np
import pytest

from skincarelib.ml_system.ml_feedback_model import (
    UserState,
    VW_AVAILABLE,
    update_user_state,
    compute_user_vector,
    LogisticRegressionFeedback,
    RandomForestFeedback,
    GradientBoostingFeedback,
    ContextualBanditFeedback,
)


@pytest.fixture
def sample_vectors():
    """Create sample product vectors."""
    np.random.seed(42)
    return np.random.randn(10, 50).astype(np.float32)


@pytest.fixture
def user_with_interactions(sample_vectors):
    """Create user with some interactions."""
    user = UserState(dim=50)

    # Add liked products
    user.add_liked(sample_vectors[0], reasons=["good_ingredients"])
    user.add_liked(sample_vectors[1], reasons=["hydrating"])

    # Add disliked
    user.add_disliked(sample_vectors[5], reasons=["greasy"])

    # Add irritation
    user.add_irritation(sample_vectors[8], reasons=["caused_rash"])

    return user


class TestUserState:
    """Tests for UserState class."""

    def test_user_state_initialization(self):
        user = UserState(dim=50)
        assert user.dim == 50
        assert user.interactions == 0
        assert len(user.liked_vectors) == 0

    def test_add_liked(self, sample_vectors):
        user = UserState(dim=50)
        user.add_liked(sample_vectors[0], reasons=["tag1", "tag2"])

        assert user.liked_count == 1
        assert user.interactions == 1
        assert len(user.liked_reasons) == 2

    def test_add_disliked(self, sample_vectors):
        user = UserState(dim=50)
        user.add_disliked(sample_vectors[0])

        assert user.disliked_count == 1
        assert user.interactions == 1

    def test_add_irritation(self, sample_vectors):
        user = UserState(dim=50)
        user.add_irritation(sample_vectors[0])

        assert user.irritation_count == 1
        assert user.interactions == 1

    def test_get_training_data(self, user_with_interactions):
        """Test that training data is properly formatted."""
        X, y = user_with_interactions.get_training_data()

        # 2 liked + 1 disliked + 1 irritation = 4 samples
        assert len(X) == 4
        assert len(y) == 4

        # Liked should be 1, disliked/irritation should be 0
        assert y[0] == 1  # liked
        assert y[1] == 1  # liked
        assert y[2] == 0  # disliked
        assert y[3] == 0  # irritation

    def test_get_training_data_insufficient(self):
        """Test that insufficient data returns None."""
        user = UserState(dim=50)
        result = user.get_training_data()
        assert result is None

        # Add only one sample
        user.add_liked(np.random.randn(50).astype(np.float32))
        result = user.get_training_data()
        assert result is None


class TestLogisticRegressionFeedback:
    """Tests for LogisticRegressionFeedback model."""

    def test_initialization(self):
        model = LogisticRegressionFeedback()
        assert model.is_trained is False

    def test_fit_and_predict(self, user_with_interactions, sample_vectors):
        model = LogisticRegressionFeedback()
        success = model.fit(user_with_interactions)

        assert success is True
        assert model.is_trained is True

        # Predict on a new vector
        score = model.predict_preference(sample_vectors[2])
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_score_products(self, user_with_interactions, sample_vectors):
        model = LogisticRegressionFeedback()
        model.fit(user_with_interactions)

        scores = model.score_products(sample_vectors)
        assert len(scores) == len(sample_vectors)
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_predict_before_training(self, sample_vectors):
        model = LogisticRegressionFeedback()
        # Should return 0.5 (neutral) before training
        score = model.predict_preference(sample_vectors[0])
        assert score == 0.5

    def test_insufficient_data_fit(self):
        """Test that fit fails gracefully with insufficient data."""
        user = UserState(dim=50)
        user.add_liked(np.random.randn(50).astype(np.float32))

        model = LogisticRegressionFeedback()
        success = model.fit(user)
        assert success is False
        assert model.is_trained is False


class TestRandomForestFeedback:
    """Tests for RandomForestFeedback model."""

    def test_initialization(self):
        model = RandomForestFeedback(n_estimators=10)
        assert model.is_trained is False

    def test_fit_and_predict(self, user_with_interactions, sample_vectors):
        model = RandomForestFeedback(n_estimators=5)
        success = model.fit(user_with_interactions)

        assert success is True
        assert model.is_trained is True

        score = model.predict_preference(sample_vectors[2])
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_feature_importance(self, user_with_interactions):
        model = RandomForestFeedback(n_estimators=5)
        model.fit(user_with_interactions)

        importance = model.get_feature_importance()
        assert len(importance) == 50  # dim=50
        assert all(i >= 0 for i in importance)

    def test_score_products(self, user_with_interactions, sample_vectors):
        model = RandomForestFeedback(n_estimators=5)
        model.fit(user_with_interactions)

        scores = model.score_products(sample_vectors)
        assert len(scores) == len(sample_vectors)
        assert all(0.0 <= s <= 1.0 for s in scores)


class TestGradientBoostingFeedback:
    """Tests for GradientBoostingFeedback model."""

    def test_initialization(self):
        model = GradientBoostingFeedback(n_estimators=10)
        assert model.is_trained is False

    def test_fit_and_predict(self, user_with_interactions, sample_vectors):
        model = GradientBoostingFeedback(n_estimators=5)
        success = model.fit(user_with_interactions)

        assert success is True
        assert model.is_trained is True

        score = model.predict_preference(sample_vectors[2])
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_feature_importance(self, user_with_interactions):
        model = GradientBoostingFeedback(n_estimators=5)
        model.fit(user_with_interactions)

        importance = model.get_feature_importance()
        assert len(importance) == 50  # dim=50
        assert all(i >= 0 for i in importance)


@pytest.mark.skipif(not VW_AVAILABLE, reason="vowpalwabbit is not installed")
class TestContextualBanditFeedback:
    """Tests for ContextualBanditFeedback model."""

    def test_initialization(self):
        model = ContextualBanditFeedback(dim=50)
        assert hasattr(model, "vw")
        assert model.total_updates == 0
        assert model.dim == 50

    def test_predict_preference(self, sample_vectors):
        model = ContextualBanditFeedback(dim=50)

        score = model.predict_preference(sample_vectors[0])
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_update_learning(self, sample_vectors):
        """Test that bandit learns from feedback."""
        model = ContextualBanditFeedback(dim=50, learning_rate=0.1)

        # Get initial scores
        initial_scores = [model.predict_preference(sample_vectors[i]) for i in range(3)]

        # Update with likes for first vector
        for _ in range(5):
            model.update(sample_vectors[0], reward=1)

        # First vector should now get higher score
        new_score = model.predict_preference(sample_vectors[0])
        assert new_score > initial_scores[0]

    def test_update_dislikes(self, sample_vectors):
        """Test learning from dislikes."""
        model = ContextualBanditFeedback(dim=50, learning_rate=0.1)

        # Update with dislikes
        for _ in range(5):
            model.update(sample_vectors[0], reward=0)

        # Score should decrease
        score = model.predict_preference(sample_vectors[0])
        assert score < 0.5

    def test_score_products(self, sample_vectors):
        model = ContextualBanditFeedback(dim=50)

        scores = model.score_products(sample_vectors)
        assert len(scores) == len(sample_vectors)
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_get_uncertainty(self):
        model = ContextualBanditFeedback(dim=50)

        # VW handles exploration internally, returns zeros
        uncertainty = model.get_uncertainty()
        assert len(uncertainty) == 50
        assert all(0.0 <= u <= 1.0 for u in uncertainty)


class TestUpdateUserState:
    """Tests for update_user_state function."""

    def test_like_reaction(self, sample_vectors):
        user = UserState(dim=50)
        update_user_state(user, "like", sample_vectors[0], ["tag1"])

        assert user.liked_count == 1

    def test_dislike_reaction(self, sample_vectors):
        user = UserState(dim=50)
        update_user_state(user, "dislike", sample_vectors[0])

        assert user.disliked_count == 1

    def test_irritation_reaction(self, sample_vectors):
        user = UserState(dim=50)
        update_user_state(user, "irritation", sample_vectors[0])

        assert user.irritation_count == 1
        assert user.disliked_count == 1  # Also counted as dislike

    def test_invalid_reaction(self, sample_vectors):
        user = UserState(dim=50)
        update_user_state(user, "invalid", sample_vectors[0])

        assert user.interactions == 0


class TestComputeUserVector:
    """Test the legacy compute_user_vector function."""

    def test_weighted_average(self, user_with_interactions):
        """Test that weighted average computation works."""
        vec = compute_user_vector(user_with_interactions)

        assert vec.dtype == np.float32
        assert len(vec) == 50

        # Should be normalized
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-6

    def test_empty_user(self):
        """Test with empty user state."""
        user = UserState(dim=50)
        vec = compute_user_vector(user)

        # Should be zero vector (unaffected by normalization)
        assert np.allclose(vec, 0.0)


class TestModelComparison:
    """Compare different models on same data."""

    def test_all_models_trainable(self, user_with_interactions, sample_vectors):
        """Test that all models can be trained on same data."""
        models = [
            LogisticRegressionFeedback(),
            RandomForestFeedback(n_estimators=5),
            GradientBoostingFeedback(n_estimators=5),
        ]
        if VW_AVAILABLE:
            models.append(ContextualBanditFeedback(dim=50))

        trainable_models = models[:-1] if VW_AVAILABLE else models
        for model in trainable_models:  # Bandit doesn't need fit
            success = model.fit(user_with_interactions)
            assert success is True

        if VW_AVAILABLE:
            # Bandit doesn't need fit
            models[-1].total_updates = 1  # Mark as "trained"

    def test_all_models_produce_scores(self, user_with_interactions, sample_vectors):
        """Test that all models produce reasonable scores."""
        models = [
            LogisticRegressionFeedback(),
            RandomForestFeedback(n_estimators=5),
            GradientBoostingFeedback(n_estimators=5),
        ]
        if VW_AVAILABLE:
            models.append(ContextualBanditFeedback(dim=50))

        trainable_models = models[:-1] if VW_AVAILABLE else models
        for model in trainable_models:
            model.fit(user_with_interactions)

        for model in models:
            scores = model.score_products(sample_vectors)
            assert len(scores) == len(sample_vectors)
            assert all(0.0 <= s <= 1.0 for s in scores)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
