#!/usr/bin/env python
"""Test if single-class mean-vector approach is working."""

import sys
sys.path.insert(0, '.')
import numpy as np
from deployment.api.app import PRODUCT_VECTORS
from skincarelib.ml_system.ml_feedback_model import UserState

# Simulate user liking the same product 10 times
user_state = UserState(PRODUCT_VECTORS.shape[1])

# Pick a product vector
product_vec = PRODUCT_VECTORS[0]

# Add 10 "likes" of the same product
for _ in range(10):
    user_state.add_liked(product_vec, reasons=["hydrating", "non_irritating"])

print(f"Interactions: {user_state.interactions}")
print(f"Liked count: {user_state.liked_count}")
print(f"Liked vectors: {len(user_state.liked_vectors)}")

training_data = user_state.get_training_data()
if training_data:
    X, y = training_data
    print(f"Training data shape: X={X.shape}, y={y.shape}")
    print(f"Unique classes in y: {np.unique(y)}")
    print(f"Number of unique classes: {len(np.unique(y))}")
else:
    print("No training data")

# Now test the scoring
mean_vector = np.mean(user_state.liked_vectors, axis=0)
print(f"\nMean vector shape: {mean_vector.shape}")
print(f"Mean vector norm: {np.linalg.norm(mean_vector):.6f}")

# Test scoring the same product
similarity = np.dot(product_vec, mean_vector) / (np.linalg.norm(product_vec) * np.linalg.norm(mean_vector) + 1e-7)
print(f"Cosine similarity of product with mean: {similarity:.6f}")
print(f"Mapped score: {(similarity + 1.0) / 2.0:.6f}")

# Test scoring a different product
different_vec = PRODUCT_VECTORS[1]
similarity2 = np.dot(different_vec, mean_vector) / (np.linalg.norm(different_vec) * np.linalg.norm(mean_vector) + 1e-7)
print(f"Cosine similarity of different product with mean: {similarity2:.6f}")
print(f"Mapped score: {(similarity2 + 1.0) / 2.0:.6f}")
