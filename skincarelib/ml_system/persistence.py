"""
Persistence layer for ML model state.
Stores user feedback and model vectors in SQLite for recovery after restarts.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np


class MLStatePersistence:
    """Handle persistence of user ML model state to SQLite."""

    def __init__(self, db_path: str = "ml_models.db"):
        self.db_path = db_path if db_path == ":memory:" else Path(db_path)
        if db_path != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        if db_path == ":memory:":
            # For in-memory DB, keep persistent connection
            self.conn = sqlite3.connect(":memory:")
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        if self.db_path == ":memory:":
            conn = self.conn
        else:
            conn = sqlite3.connect(str(self.db_path))
        
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    product_id INTEGER NOT NULL,
                    reaction TEXT,  -- 'like', 'dislike', 'irritation'
                    reason_tags TEXT,  -- JSON list
                    free_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_model_state (
                    user_id TEXT PRIMARY KEY,
                    interactions INTEGER DEFAULT 0,
                    liked_count INTEGER DEFAULT 0,
                    disliked_count INTEGER DEFAULT 0,
                    irritation_count INTEGER DEFAULT 0,
                    liked_vectors BLOB,  -- numpy array serialized
                    disliked_vectors BLOB,
                    irritation_vectors BLOB,
                    liked_reasons TEXT,  -- JSON
                    disliked_reasons TEXT,
                    irritation_reasons TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_feedback_user 
                ON user_feedback(user_id)
            """)
            
            conn.commit()
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def _get_conn(self):
        """Get connection - use persistent one for in-memory, create new for file-based."""
        if self.db_path == ":memory:":
            return self.conn
        return sqlite3.connect(str(self.db_path))

    def save_feedback(
        self,
        user_id: str,
        product_id: int,
        reaction: Optional[str],
        reason_tags: List[str],
        free_text: str,
    ) -> None:
        """Save individual feedback record."""
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO user_feedback 
                (user_id, product_id, reaction, reason_tags, free_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    product_id,
                    reaction,
                    json.dumps(reason_tags),
                    free_text,
                ),
            )
            conn.commit()
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def save_user_model_state(
        self,
        user_id: str,
        interactions: int,
        liked_count: int,
        disliked_count: int,
        irritation_count: int,
        liked_vectors: np.ndarray,
        disliked_vectors: np.ndarray,
        irritation_vectors: np.ndarray,
        liked_reasons: List[str],
        disliked_reasons: List[str],
        irritation_reasons: List[str],
    ) -> None:
        """Save user's ML model state."""
        conn = self._get_conn()
        try:
            # Serialize numpy arrays to bytes
            liked_vec_bytes = liked_vectors.tobytes() if len(liked_vectors) > 0 else None
            disliked_vec_bytes = (
                disliked_vectors.tobytes() if len(disliked_vectors) > 0 else None
            )
            irritation_vec_bytes = (
                irritation_vectors.tobytes()
                if len(irritation_vectors) > 0
                else None
            )

            # Check if user exists
            cursor = conn.execute(
                "SELECT user_id FROM user_model_state WHERE user_id = ?",
                (user_id,),
            )

            if cursor.fetchone():
                # Update
                conn.execute(
                    """
                    UPDATE user_model_state
                    SET interactions = ?, liked_count = ?, disliked_count = ?,
                        irritation_count = ?, liked_vectors = ?,
                        disliked_vectors = ?, irritation_vectors = ?,
                        liked_reasons = ?, disliked_reasons = ?,
                        irritation_reasons = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                    """,
                    (
                        interactions,
                        liked_count,
                        disliked_count,
                        irritation_count,
                        liked_vec_bytes,
                        disliked_vec_bytes,
                        irritation_vec_bytes,
                        json.dumps(liked_reasons),
                        json.dumps(disliked_reasons),
                        json.dumps(irritation_reasons),
                        user_id,
                    ),
                )
            else:
                # Insert
                conn.execute(
                    """
                    INSERT INTO user_model_state
                    (user_id, interactions, liked_count, disliked_count,
                     irritation_count, liked_vectors, disliked_vectors,
                     irritation_vectors, liked_reasons, disliked_reasons,
                     irritation_reasons)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        interactions,
                        liked_count,
                        disliked_count,
                        irritation_count,
                        liked_vec_bytes,
                        disliked_vec_bytes,
                        irritation_vec_bytes,
                        json.dumps(liked_reasons),
                        json.dumps(disliked_reasons),
                        json.dumps(irritation_reasons),
                    ),
                )

            conn.commit()
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def load_user_model_state(
        self, user_id: str, vector_dim: int
    ) -> Optional[Tuple]:
        """Load user's ML model state from database."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT interactions, liked_count, disliked_count,
                       irritation_count, liked_vectors, disliked_vectors,
                       irritation_vectors, liked_reasons, disliked_reasons,
                       irritation_reasons
                FROM user_model_state
                WHERE user_id = ?
                """,
                (user_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            (
                interactions,
                liked_count,
                disliked_count,
                irritation_count,
                liked_vec_bytes,
                disliked_vec_bytes,
                irritation_vec_bytes,
                liked_reasons_json,
                disliked_reasons_json,
                irritation_reasons_json,
            ) = row

            # Deserialize numpy arrays
            liked_vectors = (
                np.frombuffer(liked_vec_bytes, dtype=np.float32).reshape(-1, vector_dim)
                if liked_vec_bytes
                else np.array([], dtype=np.float32).reshape(0, vector_dim)
            )
            disliked_vectors = (
                np.frombuffer(disliked_vec_bytes, dtype=np.float32).reshape(
                    -1, vector_dim
                )
                if disliked_vec_bytes
                else np.array([], dtype=np.float32).reshape(0, vector_dim)
            )
            irritation_vectors = (
                np.frombuffer(irritation_vec_bytes, dtype=np.float32).reshape(
                    -1, vector_dim
                )
                if irritation_vec_bytes
                else np.array([], dtype=np.float32).reshape(0, vector_dim)
            )

            # Deserialize JSON
            liked_reasons = json.loads(liked_reasons_json) if liked_reasons_json else []
            disliked_reasons = (
                json.loads(disliked_reasons_json) if disliked_reasons_json else []
            )
            irritation_reasons = (
                json.loads(irritation_reasons_json) if irritation_reasons_json else []
            )

            return (
                interactions,
                liked_count,
                disliked_count,
                irritation_count,
                liked_vectors,
                disliked_vectors,
                irritation_vectors,
                liked_reasons,
                disliked_reasons,
                irritation_reasons,
            )
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def load_user_feedback(self, user_id: str) -> List[dict]:
        """Load all feedback for a user."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT product_id, reaction, reason_tags, free_text, created_at
                FROM user_feedback
                WHERE user_id = ?
                ORDER BY created_at ASC
                """,
                (user_id,),
            )

            feedback_list = []
            for row in cursor.fetchall():
                feedback_list.append(
                    {
                        "product_id": row[0],
                        "reaction": row[1],
                        "reason_tags": json.loads(row[2]) if row[2] else [],
                        "free_text": row[3],
                        "created_at": row[4],
                    }
                )

            return feedback_list
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def get_all_users(self) -> List[str]:
        """Get list of all users with saved models."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT DISTINCT user_id FROM user_model_state"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            if self.db_path != ":memory:":
                conn.close()
