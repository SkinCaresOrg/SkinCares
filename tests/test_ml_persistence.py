"""Test ML persistence functionality."""
import numpy as np
from skincarelib.ml_system.persistence import MLStatePersistence


def test_persistence():
    # Use in-memory database for testing
    db = MLStatePersistence(':memory:')
    
    user_id = 'test_user_1'
    liked_vecs = np.random.rand(5, 100).astype(np.float32)
    disliked_vecs = np.random.rand(3, 100).astype(np.float32)
    
    # Save
    db.save_user_model_state(
        user_id=user_id,
        interactions=8,
        liked_count=5,
        disliked_count=3,
        irritation_count=0,
        liked_vectors=liked_vecs,
        disliked_vectors=disliked_vecs,
        irritation_vectors=np.array([]),
        liked_reasons=['hydrating', 'good price'],
        disliked_reasons=['too oily'],
        irritation_reasons=[],
    )
    
    # Load
    result = db.load_user_model_state(user_id, vector_dim=100)
    assert result is not None, "Failed to load model state"
    
    interactions, liked_count, disliked_count, irritation_count, loaded_liked, loaded_disliked, loaded_irr, liked_r, disliked_r, irr_r = result
    
    assert interactions == 8
    assert liked_count == 5
    assert disliked_count == 3
    assert liked_r == ['hydrating', 'good price']
    assert loaded_liked.shape == (5, 100)
    
    print("✅ Persistence layer works correctly!")
    print(f"   - Saved and restored user model state")
    print(f"   - Vector dimensions preserved: {loaded_liked.shape}")
    print(f"   - Metadata preserved: {liked_count} likes, {disliked_count} dislikes")


if __name__ == "__main__":
    test_persistence()
