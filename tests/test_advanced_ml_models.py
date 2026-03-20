"""
Tests for advanced ML models: LogisticRegressionFeedback and EmbeddingCollaborativeFilter.

Tests validate the new implementations for:
1. Logistic regression feedback learning (replacing simple weighted average)
2. Embedding-based collaborative filtering (advanced method)
"""

import numpy as np
import pytest

from skincarelib.ml_system.feedback_lr_model import FeedbackLogisticRegression
from skincarelib.ml_system.embedding_collab_filter import EmbeddingCollaborativeFilter
from skincarelib.ml_system.feedback_update import UserState, compute_user_vector_lr


class TestFeedbackLogisticRegression:
    """Test the logistic regression feedback model."""
    
    @pytest.fixture
    def lr_model(self):
        """Create a logistic regression feedback model."""
        return FeedbackLogisticRegression(dim=10)
    
    @pytest.fixture
    def sample_vectors(self):
        """Generate sample product vectors."""
        np.random.seed(42)
        return [np.random.randn(10).astype(np.float32) for _ in range(20)]
    
    def test_initialization(self, lr_model):
        """Test that model initializes correctly."""
        assert lr_model.dim == 10
        assert not lr_model.is_trained
        assert len(lr_model.feedback_history) == 0
    
    def test_add_feedback(self, lr_model, sample_vectors):
        """Test adding feedback samples."""
        vec1 = sample_vectors[0]
        lr_model.add_feedback(vec1, feedback_label=1)
        assert len(lr_model.feedback_history) == 1
        assert lr_model.feedback_history[0][1] == 1
    
    def test_add_multiple_feedback(self, lr_model, sample_vectors):
        """Test adding multiple feedback samples."""
        for i, vec in enumerate(sample_vectors[:5]):
            label = 1 if i < 3 else 0
            lr_model.add_feedback(vec, feedback_label=label)
        
        assert len(lr_model.feedback_history) == 5
        liked_count = sum(1 for _, label in lr_model.feedback_history if label == 1)
        assert liked_count == 3
    
    def test_train_insufficient_samples(self, lr_model, sample_vectors):
        """Test that training fails with insufficient samples."""
        lr_model.add_feedback(sample_vectors[0], feedback_label=1)
        lr_model.add_feedback(sample_vectors[1], feedback_label=0)
        
        result = lr_model.train(min_samples=3)
        assert not result
        assert not lr_model.is_trained
    
    def test_train_sufficient_samples(self, lr_model, sample_vectors):
        """Test successful training with sufficient samples."""
        # Add samples from different classes
        for i in range(5):
            label = 1 if i < 3 else 0
            lr_model.add_feedback(sample_vectors[i], feedback_label=label)
        
        result = lr_model.train(min_samples=3)
        assert result
        assert lr_model.is_trained
    
    def test_predict_preference_score(self, lr_model, sample_vectors):
        """Test preference score prediction."""
        # Train with mixed feedback
        for i in range(6):
            label = 1 if i < 4 else -1  # Some liked, some irritating
            lr_model.add_feedback(sample_vectors[i], feedback_label=label)
        
        lr_model.train(min_samples=3)
        
        # Predict on a new vector
        new_vec = sample_vectors[10]
        score = lr_model.predict_preference_score(new_vec)
        
        # Score should be a float in a reasonable range
        assert isinstance(score, float)
        assert -3 <= score <= 2  # Reasonable bounds for our weighting
    
    def test_get_learned_weights(self, lr_model, sample_vectors):
        """Test extraction of learned weights."""
        for i in range(6):
            label = 1 if i < 4 else 0
            lr_model.add_feedback(sample_vectors[i], feedback_label=label)
        
        lr_model.train(min_samples=3)
        weights = lr_model.get_learned_weights()
        
        assert weights is not None
        assert len(weights) == 10
        assert weights.dtype == np.float32
        assert np.all((weights >= 0) & (weights <= 1))  # Normalized weights
    
    def test_dimension_mismatch(self, lr_model, sample_vectors):
        """Test that dimension mismatches are caught."""
        with pytest.raises(ValueError):
            wrong_vec = np.random.randn(5).astype(np.float32)
            lr_model.add_feedback(wrong_vec, feedback_label=1)


class TestEmbeddingCollaborativeFilter:
    """Test the embedding-based collaborative filtering model."""
    
    @pytest.fixture
    def product_setup(self):
        """Create test product vectors and index."""
        np.random.seed(42)
        vectors = np.random.randn(10, 20).astype(np.float32)  # 10 products, 20-dim embeddings
        index = {f"p{i}": i for i in range(10)}
        return vectors, index
    
    @pytest.fixture
    def collab_filter(self, product_setup):
        """Create a collaborative filter."""
        vectors, index = product_setup
        return EmbeddingCollaborativeFilter(vectors, index)
    
    def test_initialization(self, collab_filter, product_setup):
        """Test collaborative filter initialization."""
        vectors, index = product_setup
        assert collab_filter.n_products == 10
        assert collab_filter.dim == 20
    
    def test_record_interaction(self, collab_filter):
        """Test recording user interactions."""
        collab_filter.record_interaction("user1", "p0", feedback_label=1)
        collab_filter.record_interaction("user1", "p1", feedback_label=0)
        
        assert "user1" in collab_filter.user_interaction_history
        assert len(collab_filter.user_interaction_history["user1"]) == 2
    
    def test_build_user_embedding_cold_start(self, collab_filter):
        """Test building user embedding with no history (cold start)."""
        embedding = collab_filter.build_user_embedding("new_user")
        
        assert embedding.shape == (20,)
        assert np.linalg.norm(embedding) > 0.99  # Should be normalized
    
    def test_build_user_embedding_with_history(self, collab_filter):
        """Test building user embedding with interaction history."""
        # Record interactions
        collab_filter.record_interaction("user1", "p0", feedback_label=1)
        collab_filter.record_interaction("user1", "p1", feedback_label=1)
        collab_filter.record_interaction("user1", "p2", feedback_label=-1)
        
        embedding = collab_filter.build_user_embedding("user1")
        
        assert embedding.shape == (20,)
        # Check it's normalized
        norm = np.linalg.norm(embedding)
        assert 0.99 <= norm <= 1.01
    
    def test_embedding_caching(self, collab_filter):
        """Test that embeddings are cached."""
        collab_filter.record_interaction("user1", "p0", feedback_label=1)
        collab_filter.record_interaction("user1", "p1", feedback_label=1)
        
        # Build embedding (gets cached)
        embedding1 = collab_filter.build_user_embedding("user1", use_cache=True)
        embedding2 = collab_filter.build_user_embedding("user1", use_cache=True)
        
        # Should be exact same object/values due to cache
        assert np.allclose(embedding1, embedding2)
        assert "user1" in collab_filter.user_embeddings
    
    def test_find_collaborative_similar_products(self, collab_filter):
        """Test finding collaboratively similar products."""
        # Create a user embedding
        user_embedding = np.random.randn(20).astype(np.float32)
        user_embedding = user_embedding / np.linalg.norm(user_embedding)
        
        candidate_indices = [0, 1, 2, 3, 4]
        results = collab_filter.find_collaborative_similar_products(
            user_embedding, candidate_indices, top_k=3
        )
        
        assert len(results) == 3
        assert all(isinstance(item, tuple) and len(item) == 2 for item in results)
        # Results should be sorted by similarity descending
        similarities = [sim for _, sim in results]
        assert similarities == sorted(similarities, reverse=True)
    
    def test_rank_products_collaborative(self, collab_filter):
        """Test ranking products using collaborative similarity."""
        # Record interactions
        collab_filter.record_interaction("user1", "p0", feedback_label=1)
        collab_filter.record_interaction("user1", "p1", feedback_label=1)
        
        user_embedding = collab_filter.build_user_embedding("user1")
        
        products = ["p2", "p3", "p4", "p5"]
        ranked = collab_filter.rank_products_collaborative(user_embedding, products, top_n=2)
        
        assert len(ranked) == 2
        assert all(pid in products for pid, _ in ranked)
    
    def test_get_interesting_products_for_user(self, collab_filter):
        """Test end-to-end recommendation for a user."""
        # Setup user interactions
        collab_filter.record_interaction("user1", "p0", feedback_label=1)
        collab_filter.record_interaction("user1", "p1", feedback_label=1)
        collab_filter.record_interaction("user1", "p2", feedback_label=0)
        
        # Get recommendations
        all_products = [f"p{i}" for i in range(10)]
        exclude = ["p0", "p1", "p2"]
        recommendations = collab_filter.get_interesting_products_for_user(
            "user1", all_products, exclude_ids=exclude, top_n=3
        )
        
        assert len(recommendations) <= 3
        assert all(pid not in exclude for pid, _ in recommendations)
        assert all(pid in all_products for pid, _ in recommendations)


class TestComputeUserVectorLR:
    """Test the logistic regression-based user vector computation."""
    
    @pytest.fixture
    def user_state(self):
        """Create a user state with some feedback."""
        user = UserState(dim=10)
        
        # Add some likes
        for i in range(3):
            vec = np.random.randn(10).astype(np.float32)
            user.add_liked(vec, ["natural"])
        
        # Add some dislikes
        for i in range(2):
            vec = np.random.randn(10).astype(np.float32)
            user.add_disliked(vec, ["heavy"])
        
        # Add an irritation
        vec = np.random.randn(10).astype(np.float32)
        user.add_irritation(vec, ["irritating"])
        
        return user
    
    def test_compute_user_vector_lr_with_sufficient_feedback(self, user_state):
        """Test LR vector computation with enough feedback."""
        vec = compute_user_vector_lr(user_state)
        
        # Should return a normalized vector
        assert vec.shape == (10,)
        assert vec.dtype == np.float32
        norm = np.linalg.norm(vec)
        assert 0.99 <= norm <= 1.01
    
    def test_compute_user_vector_lr_with_insufficient_feedback(self):
        """Test LR vector computation falls back with insufficient feedback."""
        user = UserState(dim=10)
        user.add_liked(np.random.randn(10).astype(np.float32), [])
        
        # Should fall back to weighted average
        vec = compute_user_vector_lr(user)
        
        assert vec.shape == (10,)
        assert vec.dtype == np.float32
    
    def test_compute_user_vector_lr_consistency(self, user_state):
        """Test that vector computation is deterministic given same state."""
        vec1 = compute_user_vector_lr(user_state)
        vec2 = compute_user_vector_lr(user_state)
        
        # Should produce very similar results
        assert np.allclose(vec1, vec2, rtol=1e-5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
