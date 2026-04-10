"""
Integration guide for ML model persistence.
Add this to deployment/api/app.py
"""

# At the top of app.py, add:
from skincarelib.ml_system.persistence import MLStatePersistence

# Initialize persistence layer (after FastAPI app creation)
ml_persistence = MLStatePersistence(db_path="data/ml_models.db")


# Modify get_user_state() function to load from DB on first access:
def get_user_state(user_id: str) -> UserState:
    """Get or create user's ML model state, loading from DB if available."""
    if user_id not in USER_STATES:
        user_state = UserState(dim=PRODUCT_VECTORS.shape[1])
        
        # Try to load from database
        db_state = ml_persistence.load_user_model_state(
            user_id, PRODUCT_VECTORS.shape[1]
        )
        
        if db_state:
            # Restore from database
            (
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
            ) = db_state
            
            user_state.interactions = interactions
            user_state.liked_count = liked_count
            user_state.disliked_count = disliked_count
            user_state.irritation_count = irritation_count
            user_state.liked_vectors = list(liked_vectors)
            user_state.disliked_vectors = list(disliked_vectors)
            user_state.irritation_vectors = list(irritation_vectors)
            user_state.liked_reasons = liked_reasons
            user_state.disliked_reasons = disliked_reasons
            user_state.irritation_reasons = irritation_reasons
            
            print(f"[Restored from DB] {user_id}: {interactions} interactions")
        
        USER_STATES[user_id] = user_state
    
    return USER_STATES[user_id]


# Modify submit_feedback() to persist:
@app.post("/api/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    if payload.user_id not in USER_PROFILES:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")

    USER_FEEDBACK.append(payload)
    
    # Persist feedback to database
    ml_persistence.save_feedback(
        payload.user_id,
        payload.product_id,
        payload.reaction,
        payload.reason_tags,
        payload.free_text or "",
    )

    # Update ML model state with new feedback
    try:
        user_state = get_user_state(payload.user_id)
        if payload.has_tried:
            product_index = {p.product_id: i for i, p in enumerate(PRODUCTS.values())}
            vec = get_product_vector_safe(payload.product_id, product_index)
            if vec is not None:
                reasons = payload.reason_tags or []
                if payload.free_text:
                    reasons = reasons + [payload.free_text]
                
                if payload.reaction == "like":
                    user_state.add_liked(vec, reasons=reasons if reasons else None)
                elif payload.reaction == "dislike":
                    user_state.add_disliked(vec, reasons=reasons if reasons else None)
                elif payload.reaction == "irritation":
                    user_state.add_irritation(vec, reasons=reasons if reasons else None)
                
                # Persist model state after update
                ml_persistence.save_user_model_state(
                    payload.user_id,
                    user_state.interactions,
                    user_state.liked_count,
                    user_state.disliked_count,
                    user_state.irritation_count,
                    np.array(user_state.liked_vectors),
                    np.array(user_state.disliked_vectors),
                    np.array(user_state.irritation_vectors),
                    user_state.liked_reasons,
                    user_state.disliked_reasons,
                    user_state.irritation_reasons,
                )
                
    except Exception as e:
        print(f"Warning: Could not update ML model state: {e}")

    return FeedbackResponse(success=True, message="Feedback recorded & persisted")


# Add startup event to restore all users on server start:
@app.on_event("startup")
async def startup_event():
    """Restore all user models from database on startup."""
    users = ml_persistence.get_all_users()
    print(f"[Startup] Restoring {len(users)} user models from database...")
    for user_id in users:
        user_state = get_user_state(user_id)
        print(f"  - {user_id}: {user_state.interactions} interactions restored")
