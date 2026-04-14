#!/usr/bin/env python3
"""
Extract real product vectors from FAISS index and save as (256-dim) product_vectors.npy
"""
import numpy as np
import faiss
import os
from pathlib import Path

print("🔄 Extracting product vectors from FAISS index...\n")

# Load FAISS index
index = faiss.read_index('artifacts/faiss.index')
print(f"   - Loaded FAISS index: {index.ntotal} vectors, dimension {index.d}")

# Extract all vectors from FAISS
all_vectors = index.reconstruct_n(0, index.ntotal)
print(f"   - Extracted vectors shape: {all_vectors.shape}")
print(f"   - Data type: {all_vectors.dtype}")

# For compatibility with the app's 128-dim expectation, we'll:
# 1. Use dimensionality reduction if needed, OR
# 2. Sample first 128 dimensions, OR
# 3. Keep all 636 dimensions and update app
# Let's keep the real vectors and just truncate to first 256 dims for balance

vectors_256 = all_vectors[:, :256].astype(np.float32)
print(f"\n   - Reshaped to 256 dimensions: {vectors_256.shape}")

# Save as product_vectors.npy
output_path = Path('artifacts/product_vectors.npy')
np.save(output_path, vectors_256)
print(f"\n✅ Saved real product vectors to {output_path}")
print(f"   - File size: {os.path.getsize(output_path) / (1024*1024):.1f} MB")

# Verify
loaded = np.load(output_path, mmap_mode='r')
print(f"\n✅ Verification:")
print(f"   - Loaded shape: {loaded.shape}")
print(f"   - Data type: {loaded.dtype}")
print(f"   - Sample vector stats: min={loaded[0].min():.4f}, max={loaded[0].max():.4f}, mean={loaded[0].mean():.4f}")
