#!/usr/bin/env python3
import json
import numpy as np
import os

# Check product index
with open('artifacts/product_index.json', 'r') as f:
    product_index = json.load(f)

print(f"📦 Product Index Info:")
print(f"   - Total entries: {len(product_index)}")
if product_index:
    print(f"   - Sample entry: {list(product_index.items())[0]}")

# Check if FAISS index exists
print(f"\n🔍 FAISS Index Info:")
try:
    import faiss
    index = faiss.read_index('artifacts/faiss.index')
    print(f"   ✅ FAISS index loaded successfully")
    print(f"   - Vectors in index: {index.ntotal}")
    print(f"   - Vector dimension: {index.d}")
except Exception as e:
    print(f"   - Error loading FAISS: {e}")

# Check for TF-IDF vectors
print(f"\n📊 TF-IDF Model Info:")
try:
    import joblib
    tfidf = joblib.load('artifacts/tfidf.joblib')
    print(f"   ✅ TF-IDF model loaded")
    print(f"   - Vocabulary size: {len(tfidf.get('vocab', []))}")
except Exception as e:
    print(f"   - Error: {e}")

# Check if product_vectors.npy exists
if os.path.exists('artifacts/product_vectors.npy'):
    vectors = np.load('artifacts/product_vectors.npy', mmap_mode='r')
    print(f"\n✅ Product Vectors (REAL DATA):")
    print(f"   - Shape: {vectors.shape}")
    print(f"   - Data type: {vectors.dtype}")
else:
    print(f"\n❌ Product Vectors: NOT FOUND")
    print(f"   - App falls back to synthetic random vectors")
    print(f"   - Need to generate/extract real vectors from FAISS or create from TF-IDF")
