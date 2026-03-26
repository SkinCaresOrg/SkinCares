"""
Embedding-based user-preference ranking for product recommendation.

Uses product embeddings (vectors) combined with user interaction patterns
to rank products without explicit user-user or item-item matrices.
This behaves as an implicit user-profile embedding approach and is not
classical neighborhood/matrix-factorization collaborative filtering.
It learns preferences from:
1. Product feature embeddings (already available)
2. User feedback patterns aggregated into embeddings
3. Similarity between user preference embedding and product embeddings
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


class EmbeddingCollaborativeFilter:
    """
        User-profile embedding ranker using product and user embeddings.
    
        Note:
        - This class keeps its historical name for backward compatibility.
        - Methodologically, this is an embedding-based user profile model
            (content + feedback), not classical cross-user collaborative filtering.

        Key behavior: Builds a user embedding from their feedback history
    by aggregating product embeddings with learned preference weights.
        Then uses this user embedding to find products with high cosine similarity.
    """
    
    def __init__(self, product_vectors: np.ndarray, product_index: Dict[str, int]):
        """
        Initialize the collaborative filter.
        
        Args:
            product_vectors: np.ndarray shape (N, D) - precomputed product embeddings
            product_index: dict mapping product_id -> row index in product_vectors
        """
        self.product_vectors = product_vectors
        self.product_index = product_index
        self.n_products, self.dim = product_vectors.shape
        
        # Track user interactions for implicit collaborative signals
        self.user_interaction_history: Dict[str, List[Tuple[int, int]]] = {}  # user_id -> [(product_idx, label)]
        self.user_embeddings: Dict[str, np.ndarray] = {}  # user_id -> embedding
    
    def record_interaction(self, user_id: str, product_id: str, feedback_label: int):
        """
        Record a user-product interaction for collaborative learning.
        
        Args:
            user_id: Unique user identifier
            product_id: Product ID
            feedback_label: 1 for liked, 0 for disliked, -1 for irritation
        """
        if product_id not in self.product_index:
            return
        
        product_idx = self.product_index[product_id]
        if user_id not in self.user_interaction_history:
            self.user_interaction_history[user_id] = []
        
        self.user_interaction_history[user_id].append((product_idx, feedback_label))
        # Invalidate cached embedding
        if user_id in self.user_embeddings:
            del self.user_embeddings[user_id]
    
    def build_user_embedding(self, user_id: str, use_cache: bool = True) -> np.ndarray:
        """
        Build a user embedding from their interaction history.
        
        Approach:
        - Liked products: +1.5x product embedding
        - Disliked products: -0.8x product embedding
        - Irritation products: -2.0x product embedding
        Then normalize.
        
        Args:
            user_id: User identifier
            use_cache: Whether to use cached embedding if available
            
        Returns:
            User embedding vector (shape: (D,))
        """
        if use_cache and user_id in self.user_embeddings:
            return self.user_embeddings[user_id]
        
        if user_id not in self.user_interaction_history or not self.user_interaction_history[user_id]:
            # Cold start: return random direction
            embedding = np.random.randn(self.dim).astype(np.float32)
            embedding = embedding / (np.linalg.norm(embedding) + 1e-9)
            return embedding
        
        interactions = self.user_interaction_history[user_id]
        user_embedding = np.zeros(self.dim, dtype=np.float32)
        
        for product_idx, label in interactions:
            product_vec = self.product_vectors[product_idx]
            if label == 1:  # liked
                user_embedding += 1.5 * product_vec
            elif label == 0:  # disliked
                user_embedding -= 0.8 * product_vec
            elif label == -1:  # irritation
                user_embedding -= 2.0 * product_vec
        
        # Normalize
        norm = np.linalg.norm(user_embedding)
        if norm > 1e-9:
            user_embedding = user_embedding / norm
        else:
            # If all interactions cancelled out, use liked average or random
            liked_products = [self.product_vectors[idx] for idx, label in interactions if label == 1]
            if liked_products:
                user_embedding = np.mean(liked_products, axis=0)
                user_embedding = user_embedding / (np.linalg.norm(user_embedding) + 1e-9)
            else:
                user_embedding = np.random.randn(self.dim).astype(np.float32)
                user_embedding = user_embedding / np.linalg.norm(user_embedding)
        
        if use_cache:
            self.user_embeddings[user_id] = user_embedding.astype(np.float32)
        
        return user_embedding.astype(np.float32)
    
    def find_collaborative_similar_products(
        self,
        user_embedding: np.ndarray,
        candidate_indices: List[int],
        top_k: int = 10
    ) -> List[Tuple[int, float]]:
        """
        Find products similar to user embedding using cosine similarity.
        
        Args:
            user_embedding: User embedding vector (shape: (D,))
            candidate_indices: List of product indices to consider
            top_k: Number of recommendations to return
            
        Returns:
            List of (product_index, similarity_score) tuples, sorted by similarity desc
        """
        if not candidate_indices:
            return []
        
        candidate_vectors = self.product_vectors[candidate_indices]
        sims = cosine_similarity(user_embedding.reshape(1, -1), candidate_vectors).flatten()
        
        # Create list of (original_idx, similarity)
        results = [(candidate_indices[i], float(sims[i])) for i in range(len(candidate_indices))]
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def rank_products_collaborative(
        self,
        user_embedding: np.ndarray,
        product_ids: List[str],
        top_n: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Rank products for a user using collaborative embeddings.
        
        Args:
            user_embedding: User preference embedding
            product_ids: List of product IDs to rank
            top_n: Number of recommendations
            
        Returns:
            List of (product_id, similarity_score) tuples
        """
        # Filter to valid products
        valid_products = [
            (pid, self.product_index[pid]) for pid in product_ids 
            if pid in self.product_index
        ]
        
        if not valid_products:
            return []
        
        product_ids_valid, indices = zip(*valid_products)
        ranked = self.find_collaborative_similar_products(
            user_embedding,
            list(indices),
            top_k=top_n
        )
        
        # Convert back to product IDs
        idx_to_pid = {self.product_index[pid]: pid for pid in product_ids_valid}
        results = [(idx_to_pid[idx], sim) for idx, sim in ranked]
        
        return results
    
    def get_interesting_products_for_user(
        self,
        user_id: str,
        all_candidate_ids: List[str],
        exclude_ids: Optional[List[str]] = None,
        top_n: int = 10
    ) -> List[Tuple[str, float]]:
        """
        End-to-end: get collaborative filtering recommendations for a user.
        
        Args:
            user_id: User identifier
            all_candidate_ids: Pool of product IDs to recommend from
            exclude_ids: Product IDs to exclude (already liked, etc.)
            top_n: Number of recommendations
            
        Returns:
            List of (product_id, score) tuples, sorted by score desc
        """
        exclude_set = set(exclude_ids or [])
        candidates = [pid for pid in all_candidate_ids if pid not in exclude_set]
        
        if not candidates:
            return []
        
        user_embedding = self.build_user_embedding(user_id)
        return self.rank_products_collaborative(user_embedding, candidates, top_n=top_n)
