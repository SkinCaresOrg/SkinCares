# Integration Guide: Adding Swiping to Your App

## Complete Step-by-Step for Flask/FastAPI

---

## Overview

This guide shows how to integrate the online learning swiping system into a web application. We'll build a complete backend with:

- Session management
- REST API endpoints
- Database persistence (optional)
- Frontend-friendly responses

---

## Part 1: Backend Setup

### Step 1: Install Dependencies

```bash
# Already in setup.py, but for reference:
pip install vowpalwabbit>=9.0
pip install flask Flask-CORS
# OR for FastAPI
pip install fastapi uvicorn
```

### Step 2: Load Assets in Memory

Create `app.py`:

```python
import numpy as np
import pandas as pd
from pathlib import Path

# Load once at startup (not on every request)
PROJECT_ROOT = Path(__file__).parent
PRODUCT_VECTORS = np.load(PROJECT_ROOT / "artifacts/product_vectors.npy")
PRODUCT_METADATA = pd.read_csv(PROJECT_ROOT / "data/products_dataset_processed.csv")
PRODUCT_INDEX = {row["product_id"]: idx for idx, row in PRODUCT_METADATA.iterrows()}

print(f"✅ Loaded {len(PRODUCT_METADATA)} products")
print(f"✅ Product vectors shape: {PRODUCT_VECTORS.shape}")
```

### Step 3: Session Storage (In-Memory or Database)

For **small-scale** (development), use in-memory:

```python
from skincarelib.ml_system.swipe_session import SwipeSession

# Global session store (not production-safe!)
SESSIONS = {}

def get_or_create_session(user_id: str) -> SwipeSession:
    if user_id not in SESSIONS:
        SESSIONS[user_id] = SwipeSession(
            user_id=user_id,
            product_vectors=PRODUCT_VECTORS,
            product_metadata=PRODUCT_METADATA,
            product_index=PRODUCT_INDEX,
            learning_rate=0.1,
            initial_epsilon=0.8
        )
    return SESSIONS[user_id]
```

For **production**, use Redis or database:

```python
import json
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def save_session(session):
    """Save session state to Redis"""
    session_data = {
        "user_id": session.user_id,
        "products_shown": list(session.products_shown),
        "rating_history": session.rating_history,
        # Note: VW model itself stored separately (see below)
    }
    redis_client.set(f"session:{session.user_id}", json.dumps(session_data))

def load_session(user_id: str):
    """Restore session from Redis"""
    data = redis_client.get(f"session:{user_id}")
    if data:
        return json.loads(data)
    return None
```

---

## Part 2: Flask API (Option A)

### Complete Flask App

```python
# app_flask.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import pandas as pd
from datetime import datetime

from skincarelib.ml_system.swipe_session import SwipeSession

app = Flask(__name__)
CORS(app)

# Load assets
PRODUCT_VECTORS = np.load("artifacts/product_vectors.npy")
PRODUCT_METADATA = pd.read_csv("data/products_dataset_processed.csv")
PRODUCT_INDEX = {row["product_id"]: idx for idx, row in PRODUCT_METADATA.iterrows()}

# Session storage
SESSIONS = {}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_session(user_id: str) -> SwipeSession:
    """Get existing session, create if not exists"""
    if user_id not in SESSIONS:
        SESSIONS[user_id] = SwipeSession(
            user_id=user_id,
            product_vectors=PRODUCT_VECTORS,
            product_metadata=PRODUCT_METADATA,
            product_index=PRODUCT_INDEX
        )
    return SESSIONS[user_id]

def serialize_product(product_id: str, product_data: dict) -> dict:
    """Convert product data to JSON-safe format"""
    return {
        "product_id": product_id,
        "brand": product_data.get("brand", "Unknown"),
        "name": product_data.get("name", "Unknown"),
        "category": product_data.get("category", "Unknown"),
        "price": float(product_data.get("price", 0)),
        "ingredients": product_data.get("ingredients", "").split("|")[:5],  # Top 5
        "image_url": f"/static/images/{product_id}.jpg"
    }

# ============================================================================
# ENDPOINTS: SESSION MANAGEMENT
# ============================================================================

@app.route("/api/session/create", methods=["POST"])
def create_session():
    """Create or get session for user"""
    data = request.json
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    session = get_session(user_id)
    
    return jsonify({
        "status": "success",
        "user_id": user_id,
        "session_exists": user_id in SESSIONS,
        "timestamp": datetime.now().isoformat()
    }), 201

@app.route("/api/session/<user_id>", methods=["GET"])
def get_session_state(user_id: str):
    """Get current session state"""
    if user_id not in SESSIONS:
        return jsonify({"error": "session not found"}), 404
    
    session = SESSIONS[user_id]
    state = session.get_session_state()
    
    return jsonify({
        "user_id": user_id,
        "products_shown": state["total_products_shown"],
        "products_rated": state["products_rated"],
        "likes": state["feedback_summary"]["products_liked"],
        "dislikes": state["feedback_summary"]["products_disliked"],
        "exploration_rate": f"{state['exploration_exploitation']['exploration_rate']:.1%}",
        "model_learning_interactions": state["model_interactions_learned"]
    }), 200

@app.route("/api/session/<user_id>/delete", methods=["DELETE"])
def delete_session(user_id: str):
    """Delete session (cleanup)"""
    if user_id in SESSIONS:
        del SESSIONS[user_id]
        return jsonify({"status": "deleted"}), 200
    return jsonify({"error": "session not found"}), 404

# ============================================================================
# ENDPOINTS: ONBOARDING
# ============================================================================

@app.route("/api/onboarding/options", methods=["GET"])
def get_onboarding_options():
    """Get all onboarding question options"""
    from skincarelib.ml_system.feedback_structures import (
        InitialUserQuestionnaire,
        DetailedFeedbackCollector
    )
    
    questionnaire = InitialUserQuestionnaire()
    
    return jsonify({
        "skin_types": questionnaire.SKIN_TYPES,
        "skin_concerns": questionnaire.SKIN_CONCERNS,
        "budget_ranges": [
            {"label": label, "max_price": max_price}
            for label, max_price in questionnaire.BUDGET_RANGES
        ],
        "product_categories": DetailedFeedbackCollector().PRODUCT_CATEGORIES
    }), 200

@app.route("/api/onboarding/complete", methods=["POST"])
def complete_onboarding():
    """Complete user onboarding"""
    data = request.json
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    session = get_session(user_id)
    
    try:
        session.complete_onboarding(
            skin_type=data["skin_type"],
            skin_concerns=data["skin_concerns"],
            budget_range=(data["budget_label"], data["budget_max"]),
            preferred_categories=" ".join(data.get("preferred_categories", []))
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    state = session.get_session_state()
    
    return jsonify({
        "status": "onboarding_complete",
        "user_profile": {
            "skin_type": session.user_questionnaire.profile.get("skin_type"),
            "concerns": session.user_questionnaire.profile.get("skin_concerns"),
            "budget": session.user_questionnaire.profile.get("budget_max")
        }
    }), 200

# ============================================================================
# ENDPOINTS: SWIPING
# ============================================================================

@app.route("/api/product/next", methods=["GET"])
def get_next_product():
    """Get next product for user to swipe"""
    user_id = request.args.get("user_id")
    
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    if user_id not in SESSIONS:
        return jsonify({"error": "session not found"}), 404
    
    session = SESSIONS[user_id]
    
    try:
        product_id, product_meta = session.get_next_product()
    except Exception as e:
        return jsonify({"error": f"Failed to get product: {str(e)}"}), 500
    
    product_data = PRODUCT_METADATA.loc[PRODUCT_INDEX[product_id]].to_dict()
    
    return jsonify({
        "product_id": product_id,
        "brand": product_data.get("brand"),
        "name": product_data.get("name"),
        "category": product_data.get("category"),
        "price": float(product_data.get("price", 0)),
        "description": product_data.get("description", ""),
        "ingredients": product_data.get("ingredients", "").split("|")[:10],
        "image_url": f"/static/images/{product_id}.jpg",
        "model_confidence": round(product_meta["confidence_score"], 2),
        "was_exploration": product_meta["exploration_action"]
    }), 200

@app.route("/api/product/swipe", methods=["POST"])
def record_swipe():
    """Record user swipe (like/dislike/skip)"""
    data = request.json
    user_id = data.get("user_id")
    product_id = data.get("product_id")
    reaction = data.get("reaction")  # "like", "dislike", "skip"
    
    if not all([user_id, product_id, reaction]):
        return jsonify({"error": "user_id, product_id, reaction required"}), 400
    
    if reaction not in ["like", "dislike", "skip"]:
        return jsonify({"error": "invalid reaction"}), 400
    
    if user_id not in SESSIONS:
        return jsonify({"error": "session not found"}), 404
    
    session = SESSIONS[user_id]
    tried_status = data.get("tried_status", "yes")
    feedback_reasons = data.get("feedback_reasons", [])
    
    try:
        result = session.record_swipe(
            product_id=product_id,
            tried_status=tried_status,
            reaction=reaction,
            feedback_reasons=feedback_reasons
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    state = session.get_session_state()
    
    return jsonify({
        "status": "swipe_recorded",
        "reaction": reaction,
        "interaction_count": state["model_interactions_learned"],
        "like_rate": round(
            state["feedback_summary"]["products_liked"] / max(1, state["feedback_summary"]["products_tried"]),
            2
        )
    }), 200

# ============================================================================
# ENDPOINTS: FEEDBACK COLLECTION
# ============================================================================

@app.route("/api/feedback/questions", methods=["GET"])
def get_feedback_questions():
    """Get category-specific follow-up questions"""
    product_id = request.args.get("product_id")
    reaction = request.args.get("reaction")  # "like" or "dislike"
    
    if not product_id or not reaction:
        return jsonify({"error": "product_id and reaction required"}), 400
    
    if product_id not in PRODUCT_INDEX:
        return jsonify({"error": "product not found"}), 404
    
    if reaction not in ["like", "dislike"]:
        return jsonify({"error": "invalid reaction"}), 400
    
    # Get product category
    product_data = PRODUCT_METADATA.loc[PRODUCT_INDEX[product_id]].to_dict()
    category = product_data.get("category", "Unknown")
    
    # Get feedback questions
    from skincarelib.ml_system.feedback_structures import DetailedFeedbackCollector
    collector = DetailedFeedbackCollector()
    
    try:
        question, options = collector.get_followup_questions(category, reaction)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    return jsonify({
        "product_id": product_id,
        "reaction": reaction,
        "category": category,
        "question": question,
        "options": options,
        "allow_multiple": True
    }), 200

# ============================================================================
# ENDPOINTS: RECOMMENDATIONS
# ============================================================================

@app.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    """Get personalized recommendations"""
    user_id = request.args.get("user_id")
    top_n = int(request.args.get("top_n", 5))
    
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    if user_id not in SESSIONS:
        return jsonify({"error": "session not found"}), 404
    
    session = SESSIONS[user_id]
    
    try:
        recommendations = session.get_recommendations(top_n=top_n)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    # Convert to JSON
    result = []
    for _, row in recommendations.iterrows():
        result.append({
            "product_id": row["product_id"],
            "brand": row.get("brand", "Unknown"),
            "category": row.get("category", "Unknown"),
            "price": float(row.get("price", 0)),
            "preference_score": round(row.get("preference_score", 0), 2),
            "image_url": f"/static/images/{row['product_id']}.jpg"
        })
    
    return jsonify({
        "recommendations": result,
        "total": len(result)
    }), 200

# ============================================================================
# ENDPOINTS: INSIGHTS
# ============================================================================

@app.route("/api/insights/ingredients", methods=["GET"])
def get_ingredient_insights():
    """Get ingredient-level preferences"""
    user_id = request.args.get("user_id")
    
    if not user_id or user_id not in SESSIONS:
        return jsonify({"error": "session not found"}), 404
    
    session = SESSIONS[user_id]
    tracker = session.ingredient_tracker
    
    liked = tracker.get_liked_ingredients(threshold=0.5)
    disliked = tracker.get_disliked_ingredients(threshold=-0.5)
    all_scores = tracker.get_ingredient_preference_scores()
    
    return jsonify({
        "liked_ingredients": liked[:10],  # Top 10
        "disliked_ingredients": disliked[:10],  # Top 10
        "total_ingredients_tracked": len(all_scores)
    }), 200

# ============================================================================
# ROOT ENDPOINTS
# ============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "app": "SkinCares Online Learning Recommender",
        "version": "2.0",
        "endpoints": {
            "session": [
                "POST /api/session/create",
                "GET /api/session/<user_id>",
                "DELETE /api/session/<user_id>/delete"
            ],
            "onboarding": [
                "GET /api/onboarding/options",
                "POST /api/onboarding/complete"
            ],
            "swiping": [
                "GET /api/product/next?user_id=<user_id>",
                "POST /api/product/swipe"
            ],
            "feedback": [
                "GET /api/feedback/questions?product_id=<id>&reaction=<reaction>"
            ],
            "recommendations": [
                "GET /api/recommendations?user_id=<user_id>&top_n=5"
            ],
            "insights": [
                "GET /api/insights/ingredients?user_id=<user_id>"
            ]
        }
    }), 200

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

### Run Flask

```bash
python app_flask.py
# Server running on http://localhost:5000
```

---

## Part 3: FastAPI (Option B)

### Complete FastAPI App

```python
# app_fastapi.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import pandas as pd
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from skincarelib.ml_system.swipe_session import SwipeSession

app = FastAPI(
    title="SkinCares Online Learning",
    version="2.0",
    description="Vowpal Wabbit + Contextual Bandits swiping recommender"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load assets
PRODUCT_VECTORS = np.load("artifacts/product_vectors.npy")
PRODUCT_METADATA = pd.read_csv("data/products_dataset_processed.csv")
PRODUCT_INDEX = {row["product_id"]: idx for idx, row in PRODUCT_METADATA.iterrows()}

# Session storage
SESSIONS = {}

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class OnboardingRequest(BaseModel):
    user_id: str
    skin_type: str
    skin_concerns: List[str]
    budget_label: str
    budget_max: float
    preferred_categories: Optional[List[str]] = []

class SwipeRequest(BaseModel):
    user_id: str
    product_id: str
    tried_status: str = "yes"
    reaction: str  # "like", "dislike", "skip"
    feedback_reasons: Optional[List[str]] = []

# ============================================================================
# HELPERS
# ============================================================================

def get_session(user_id: str) -> SwipeSession:
    if user_id not in SESSIONS:
        SESSIONS[user_id] = SwipeSession(
            user_id=user_id,
            product_vectors=PRODUCT_VECTORS,
            product_metadata=PRODUCT_METADATA,
            product_index=PRODUCT_INDEX
        )
    return SESSIONS[user_id]

# ============================================================================
# REST ENDPOINTS
# ============================================================================

@app.get("/")
def read_root():
    return {
        "app": "SkinCares Online Learning",
        "version": "2.0",
        "status": "running"
    }

@app.post("/api/session/create")
def create_session(user_id: str):
    """Create or get session"""
    session = get_session(user_id)
    return {
        "status": "success",
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/session/{user_id}")
def get_session_state(user_id: str):
    """Get session state"""
    if user_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = SESSIONS[user_id]
    state = session.get_session_state()
    
    return {
        "user_id": user_id,
        "products_shown": state["total_products_shown"],
        "products_rated": state["products_rated"],
        "likes": state["feedback_summary"]["products_liked"],
        "dislikes": state["feedback_summary"]["products_disliked"],
        "exploration_rate": f"{state['exploration_exploitation']['exploration_rate']:.1%}"
    }

@app.get("/api/onboarding/options")
def get_onboarding_options():
    """Get onboarding question options"""
    from skincarelib.ml_system.feedback_structures import InitialUserQuestionnaire
    
    q = InitialUserQuestionnaire()
    return {
        "skin_types": q.SKIN_TYPES,
        "skin_concerns": q.SKIN_CONCERNS,
        "budget_ranges": [
            {"label": label, "max": max_price}
            for label, max_price in q.BUDGET_RANGES
        ]
    }

@app.post("/api/onboarding/complete")
def complete_onboarding(request: OnboardingRequest):
    """Complete onboarding"""
    session = get_session(request.user_id)
    
    try:
        session.complete_onboarding(
            skin_type=request.skin_type,
            skin_concerns=request.skin_concerns,
            budget_range=(request.budget_label, request.budget_max),
            preferred_categories=" ".join(request.preferred_categories or [])
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {"status": "onboarding_complete"}

@app.get("/api/product/next")
def get_next_product(user_id: str):
    """Get next product to swipe"""
    if user_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = SESSIONS[user_id]
    product_id, product_meta = session.get_next_product()
    product_data = PRODUCT_METADATA.loc[PRODUCT_INDEX[product_id]].to_dict()
    
    return {
        "product_id": product_id,
        "brand": product_data.get("brand"),
        "category": product_data.get("category"),
        "price": float(product_data.get("price", 0)),
        "image_url": f"/static/{product_id}.jpg",
        "confidence": round(product_meta["confidence_score"], 2),
        "exploration": product_meta["exploration_action"]
    }

@app.post("/api/product/swipe")
def record_swipe(request: SwipeRequest):
    """Record swipe"""
    if request.user_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if request.reaction not in ["like", "dislike", "skip"]:
        raise HTTPException(status_code=400, detail="Invalid reaction")
    
    session = SESSIONS[request.user_id]
    
    result = session.record_swipe(
        product_id=request.product_id,
        tried_status=request.tried_status,
        reaction=request.reaction,
        feedback_reasons=request.feedback_reasons or []
    )
    
    state = session.get_session_state()
    
    return {
        "status": "recorded",
        "reaction": request.reaction,
        "interactions": state["model_interactions_learned"]
    }

@app.get("/api/recommendations")
def get_recommendations(user_id: str, top_n: int = Query(5, ge=1, le=20)):
    """Get recommendations"""
    if user_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = SESSIONS[user_id]
    recommendations = session.get_recommendations(top_n=top_n)
    
    result = []
    for _, row in recommendations.iterrows():
        result.append({
            "product_id": row["product_id"],
            "brand": row.get("brand"),
            "price": float(row.get("price", 0)),
            "score": round(row.get("preference_score", 0), 2)
        })
    
    return {"recommendations": result, "total": len(result)}

@app.get("/health")
def health():
    return {"status": "healthy"}
```

### Run FastAPI

```bash
uvicorn app_fastapi:app --reload --port 8000
# Server running on http://localhost:8000
# Docs at http://localhost:8000/docs
```

---

## Part 4: Frontend Integration (React Example)

### React Swiping Component

```jsx
// SwipeCard.jsx
import React, { useState, useEffect } from "react";

const SwipeCard = ({ userId }) => {
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackQuestion, setFeedbackQuestion] = useState(null);

  // Get next product
  const fetchNextProduct = async () => {
    setLoading(true);
    const res = await fetch(`/api/product/next?user_id=${userId}`);
    const data = await res.json();
    setProduct(data);
    setShowFeedback(false);
    setLoading(false);
  };

  // Handle swipe
  const handleSwipe = async (reaction) => {
    // Get feedback question
    const feedRes = await fetch(
      `/api/feedback/questions?product_id=${product.product_id}&reaction=${reaction}`
    );
    const feedData = await feedRes.json();
    
    setFeedbackQuestion(feedData);
    setShowFeedback(true);
  };

  // Record swipe with feedback
  const recordSwipeWithFeedback = async (feedback) => {
    await fetch("/api/product/swipe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        product_id: product.product_id,
        reaction: feedbackQuestion.reaction,
        feedback_reasons: feedback
      })
    });

    // Get next product
    fetchNextProduct();
  };

  useEffect(() => {
    fetchNextProduct();
  }, [userId]);

  if (loading) return <div>Loading...</div>;

  if (!showFeedback) {
    return (
      <div className="swipe-card">
        <img src={product.image_url} alt={product.brand} />
        <h3>{product.brand}</h3>
        <p>{product.category}</p>
        <p className="price">${product.price}</p>

        <div className="buttons">
          <button onClick={() => handleSwipe("dislike")} className="btn-dislike">
            👎 DISLIKE
          </button>
          <button onClick={() => handleSwipe("skip")} className="btn-skip">
            ⏭️ SKIP
          </button>
          <button onClick={() => handleSwipe("like")} className="btn-like">
            👍 LIKE
          </button>
        </div>

        <div className="confidence">
          Model confidence: {(product.confidence * 100).toFixed(0)}%
          {product.exploration && " (exploring)"}
        </div>
      </div>
    );
  }

  return (
    <FeedbackForm
      question={feedbackQuestion}
      onSubmit={recordSwipeWithFeedback}
    />
  );
};

export default SwipeCard;
```

### Feedback Form Component

```jsx
// FeedbackForm.jsx
import React, { useState } from "react";

const FeedbackForm = ({ question, onSubmit }) => {
  const [selected, setSelected] = useState([]);

  const handleToggle = (option) => {
    setSelected(prev =>
      prev.includes(option)
        ? prev.filter(o => o !== option)
        : [...prev, option]
    );
  };

  return (
    <div className="feedback-form">
      <h3>{question.question}</h3>
      <div className="options">
        {question.options.map(option => (
          <label key={option}>
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => handleToggle(option)}
            />
            {option}
          </label>
        ))}
      </div>
      <button onClick={() => onSubmit(selected)} className="btn-submit">
        Next
      </button>
    </div>
  );
};

export default FeedbackForm;
```

---

## Part 5: Deployment

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t skincares-api .
docker run -p 8000:8000 skincares-api
```

### Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
    volumes:
      - ./artifacts:/app/artifacts
      - ./data:/app/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

```bash
docker-compose up
```

---

## Testing

```bash
# Test Flask
curl -X POST http://localhost:5000/api/session/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'

# Test onboarding
curl -X POST http://localhost:5000/api/onboarding/complete \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "skin_type": "Dry",
    "skin_concerns": ["Dryness"],
    "budget_label": "50-100",
    "budget_max": 100
  }'

# Test get next product
curl "http://localhost:5000/api/product/next?user_id=test_user"

# Test swipe
curl -X POST http://localhost:5000/api/product/swipe \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "product_id": "p123",
    "reaction": "like",
    "feedback_reasons": ["It hydrated well"]
  }'
```

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Product vectors not found | Check path to `artifacts/product_vectors.npy` |
| Session memory growing | Implement Redis persistence (see Part 1) |
| Slow prediction | Pre-load all assets at startup (done above) |
| CORS errors | Add CORS middleware (done in FastAPI/Flask) |
| VW model too slow | Increase learning_rate (more aggressive learning) |

