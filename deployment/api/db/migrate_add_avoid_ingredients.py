#!/usr/bin/env python3
"""
Migration script to add avoid_ingredients columns to user_model_state table.

This script adds two new columns:
- avoid_ingredients: JSON column tracking accumulated disliked ingredients  
- avoid_ingredient_last_seen_at: JSON column tracking when each ingredient was last disliked

Run this before deploying the updated app.py
"""

from sqlalchemy import text
from deployment.api.db.session import engine

def migrate():
    """Add avoid_ingredients columns to user_model_state table."""
    with engine.begin() as conn:
        # Check if columns already exist
        inspector_query = text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='user_model_state' AND column_name IN ('avoid_ingredients', 'avoid_ingredient_last_seen_at')
        """)
        result = conn.execute(inspector_query)
        existing_cols = {row[0] for row in result}
        
        # Add columns if they don't exist
        if 'avoid_ingredients' not in existing_cols:
            conn.execute(text("""
                ALTER TABLE user_model_state ADD COLUMN avoid_ingredients JSON NOT NULL DEFAULT '{}'
            """))
            print("✓ Added avoid_ingredients column")
        else:
            print("✓ avoid_ingredients column already exists")
            
        if 'avoid_ingredient_last_seen_at' not in existing_cols:
            conn.execute(text("""
                ALTER TABLE user_model_state ADD COLUMN avoid_ingredient_last_seen_at JSON NOT NULL DEFAULT '{}'
            """))
            print("✓ Added avoid_ingredient_last_seen_at column")
        else:
            print("✓ avoid_ingredient_last_seen_at column already exists")

if __name__ == "__main__":
    migrate()
    print("\nMigration completed successfully!")
