# Team Onboarding Guide: ML Feedback System

**Purpose:** Help new team members understand how the skincare recommendation ML system works and how to extend it.

---

## Quick Start (5 minutes)

### What Does This System Do?
The ML system learns user preferences from their feedback and provides personalized skincare recommendations.

**User Journey:**
```
1. User signs up → Onboarding (skin type + concerns)
2. User browses products → Sees feedback questions
3. User gives feedback → System learns preferences
4. User gets recommendations → Based on learning
5. Cycle repeats → Model improves
```

### How to Run It

**Start the API:**
```bash
cd /Users/geethika/projects/SkinCares/SkinCares/deployment
python -m api.app
# Available at: http://localhost:8000
```

**Run tests:**
```bash
cd /Users/geethika/projects/SkinCares/SkinCares
python test_ml_comprehensive_standalone.py
```

**Check if learning works:**
- All 6 test phases pass ✅
- Model trains from feedback ✅
- Recommendations personalized ✅

---

## System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERACTION                          │
├─────────────────────────────────────────────────────────────┤
│  1. Browse products                                          │
│  2. Give feedback (4-step process)                          │
│  3. Get recommendations                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              FEEDBACK COLLECTION (FeedbackPanel)             │
├─────────────────────────────────────────────────────────────┤
│  Step 1: Have you tried?     → Boolean                       │
│  Step 2: Experience?         → like/dislike/irritation      │
│  Step 3: Which apply?        → Category-specific tags       │
│  Step 4: Anything else?      → Free-text comment            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              DATABASE STORAGE (UserProductEvent)             │
├─────────────────────────────────────────────────────────────┤
│  • reason_tags: JSON array  ['hydrated_well', ...]          │
│  • free_text: Plain text    "Great moisturizer!"            │
│  • reaction: Enum           like | dislike | irritation     │
│  • created_at: Timestamp    2024-01-15 14:30:00            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│          USERSTATE RECONSTRUCTION (/api/recommendations)    │
├─────────────────────────────────────────────────────────────┤
│  1. Query UserProductEvent for all events                   │
│  2. Combine reason_tags + free_text                         │
│  3. Load product vectors (256-dimensional)                  │
│  4. Create UserState with reason signals                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               MODEL SELECTION & TRAINING                     │
├─────────────────────────────────────────────────────────────┤
│  0-5 interactions:    LogisticRegression   (simple)         │
│  5-20 interactions:   RandomForest        (patterns)        │
│  20-50 interactions:  LightGBM            (gradient boost)  │
│  50+ interactions:    ContextualBandit    (online learning) │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         RECOMMENDATION RANKING & DELIVERY                    │
├─────────────────────────────────────────────────────────────┤
│  1. Load trained model for user                             │
│  2. Score all products against learned preferences          │
│  3. Sort by score (descending)                              │
│  4. Return top-N to frontend                                │
│  5. Show explanation text                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Components Explained

### 1. Feedback Panel (Frontend)

**File:** `frontend/src/components/FeedbackPanel.tsx`

**What it does:**
- Shows when user browses a product
- Presents 4 questions in sequence
- Collects structured + unstructured feedback

**The 4 Questions:**

| Step | Question | Input Type | Purpose |
|------|----------|-----------|---------|
| 1 | Have you tried this product before? | Boolean (Yes/No) | Ensure authentic feedback |
| 2 | What was your experience? | Single choice: 👍 Like \| 👎 Dislike \| ⚠️ Irritation | Classify preference |
| 3 | Which of these apply? | Multi-select tags (category-specific) | Structured reasons |
| 4 | Anything else you'd like to add? | Free text (optional) | Context & nuance |

**Why 4 steps:**
- ✅ Steps 1-2: Quick feedback (reaction to product)
- ✅ Step 3: Why they felt that way (tags)
- ✅ Step 4: Additional context (free text captures nuance not in tags)
- ✅ Together: Rich signal for learning

### 2. Backend API

**File:** `deployment/api/app.py`

**Key Endpoints:**

#### POST `/api/feedback`
Receive and store user feedback.

```python
@app.post("/api/feedback")
def save_feedback(request: FeedbackRequest):
    """
    Receives: {
        "user_id": "user_123",
        "product_id": 42,
        "reaction": "like",
        "reason_tags": ["hydrated_well", "absorbed_quickly"],
        "free_text": "Great moisturizer!"
    }
    
    Does:
    1. Save to UserProductEvent table
    2. Update UserState in memory
    3. Return confirmation
    """
    event = UserProductEvent(
        user_id=request.user_id,
        product_id=request.product_id,
        reaction=request.reaction,
        reason_tags=request.reason_tags,      # ← Stored as JSON
        free_text=request.free_text,          # ← Stored as TEXT
        has_tried=True,
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    return {"status": "success"}
```

#### GET `/api/recommendations`
Generate personalized recommendations.

```python
@app.get("/api/recommendations")
def get_recommendations(user_id: str, count: int = 10):
    """
    Does:
    1. Load user profile (skin type, concerns, interests)
    2. Load all user feedback from database
    3. Reconstruct UserState with reason signals
    4. Train model on feedback
    5. Score all products
    6. Return top-N ranked by score
    """
    user_profile = db.query(UserProfileState).get(user_id)
    user_state = _load_user_state_from_db(user_id)
    
    model = get_best_model(len(user_state.liked_vectors))
    model.fit(user_state)
    
    all_products = db.query(Product).all()
    scores = [model.predict_preference(p.vector) for p in all_products]
    
    recommendations = sorted(zip(all_products, scores), 
                            key=lambda x: x[1], reverse=True)[:count]
    
    return {"recommendations": recommendations}
```

### 3. Database Models

**File:** `data/schema.py`

**UserProductEvent Table:**
```python
class UserProductEvent(Base):
    __tablename__ = "user_product_events"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("user_profiles.user_id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    
    # Feedback data
    reaction = Column(String)              # "like" | "dislike" | "irritation"
    reason_tags = Column(JSON)             # ["hydrated_well", "absorbed_quickly"]
    free_text = Column(String)             # "Great moisturizer!"
    
    has_tried = Column(Boolean)            # Did user actually try it
    created_at = Column(DateTime)          # When feedback was given
```

**Why this design:**
- `reason_tags` as JSON → Easy to parse tags, can query/filter
- `free_text` as plain TEXT → Full string search capable, preserves original text
- `reaction` as STRING → Easy classification for model labels
- `created_at` → Temporal ordering for sequence learning

### 4. Model Classes

**File:** `skincarelib/ml_system/ml_feedback_model.py`

**4 Models in Action:**

#### LogisticRegression (0-5 interactions)
```python
class LogisticRegression:
    def fit(self, user_state):
        """Train on early feedback - simple linear model"""
        # Good when: User just started, few examples
        # Fast: Good initial performance with limited data
        # Reason signals: Used to weight features
    
    def predict_preference(self, product_vector):
        """Score: 0.0 (dislike) to 1.0 (like)"""
        return self.classifier.predict_proba(product_vector)[0, 1]
```

#### RandomForest (5-20 interactions)
```python
class RandomForest:
    def fit(self, user_state):
        """Train on growing feedback - capture non-linear patterns"""
        # Good when: User has given several examples
        # Captures: Feature interactions and importance
        # Reason signals: Available for feature weighting
    
    def predict_preference(self, product_vector):
        """Score: probability of like"""
        return self.forest.predict_proba(product_vector)[0, 1]
```

#### LightGBM (20-50 interactions)
```python
class LightGBM:
    def fit(self, user_state):
        """Train on substantial feedback - gradient boosting"""
        # Good when: Enough examples to avoid overfitting
        # Fast: Gradient boosting is efficient
        # Reason signals: Strong feature importance available
    
    def predict_preference(self, product_vector):
        """Score: probability of like"""
        return self.model.predict_proba(product_vector)[0, 1]
```

#### ContextualBandit (50+ interactions)
```python
class ContextualBandit:
    def fit(self, user_state):
        """Train on lots of feedback - online learning"""
        # Good when: Massive interaction history
        # Online: Can update incrementally
        # Exploration: Balances exploitation vs exploration
    
    def predict_preference(self, product_vector):
        """Score with exploration bonus"""
        # Prioritizes uncertain products for exploration
        return self.agent.score(product_vector)
```

---

## How Learning Works

### Example: User Learns to Love Hydrating Moisturizers

**Step 1: User Tries Product A**
- Product: Hydrating Moisturizer
- Reaction: 👍 Like
- Tags: `['hydrated_well', 'absorbed_quickly', 'non_irritating']`
- Text: "This works great! Very hydrating and non-sticky."
- Database stores everything

**Step 2: Model Learns**
```
feedback_event = {
    'product_vector': [0.8, 0.2, 0.5, ...],  # 256 dimensions
    'reaction': 'like',
    'reason_tags': ['hydrated_well', 'absorbed_quickly'],
    'free_text': 'This works great...'
}

user_state.add_liked(
    vector=feedback_event['product_vector'],
    reasons=['hydrated_well', 'absorbed_quickly', 'This works great...']
)

model.fit(user_state)
# Model learns this vector's features predict positive preference
```

**Step 3: Recommendations Change**
- New hydrating product launches
- System scores it high: Matches learned features
- Next recommendations: Show hydrating products first

**Step 4: User Tries Product B (Greasy Oil)**
- Reaction: 👎 Dislike
- Tags: `['too_greasy', 'felt_sticky']`
- Model learns: These features predict negative preference
- Next recommendations: Deprioritize greasy products

**Result:**
- User gets more hydrating products
- Fewer greasy products
- Recommendations improve over time

### Reason Signals in the Model

**How tags + text drive learning:**

```python
# When a user likes a product:
liked_reasons = [
    'hydrated_well',           # ← Tag 1
    'absorbed_quickly',        # ← Tag 2  
    'non_irritating',          # ← Tag 3
    'This works great!'        # ← Text part 1
]

# Model learns:
# Products with similar features to loved products
# AND matching these reason keywords
# Should be ranked higher

# Example: New product "Ultra-Hydrating Serum"
# Matches: 'hydrated_well' + 'absorbs quickly'
# → Gets high score
# → Shown in recommendations
```

---

## API Contract

### Request/Response Examples

**Feedback Submission:**
```json
{
  "user_id": "user_123",
  "product_id": 42,
  "reaction": "like",
  "reason_tags": ["hydrated_well", "absorbed_quickly", "non_irritating"],
  "free_text": "This moisturizer works great! Very hydrating and non-sticky."
}

← Response →

{
  "status": "success",
  "feedback_id": "fb_abc123",
  "message": "Feedback saved and model updated"
}
```

**Recommendations Request:**
```json
GET /api/recommendations?user_id=user_123&count=10

← Response →

{
  "recommendations": [
    {
      "product_id": 254,
      "product_name": "Ultra Hydrating Serum",
      "score": 0.9401,
      "confidence": "high",
      "reason": "Matches your preference for hydrating products"
    },
    {
      "product_id": 1,
      "product_name": "Moisturizing Cream",
      "score": 0.9109,
      "confidence": "high",
      "reason": "Similar to products you've liked"
    }
  ],
  "explanation": "Based on your 3 interactions (1 liked, 1 disliked, 1 irritation)",
  "model_type": "LogisticRegression",
  "interaction_count": 3
}
```

---

## Common Tasks

### Task 1: Add a New Reason Tag

**Scenario:** Want to add "moisturizing" tag as a reason option

**Steps:**

1. **Update tag definition** (`features/ingredient_groups.json`):
```json
{
  "moisturizing_tags": {
    "like": [
      "hydrated_well",
      "absorbed_quickly",
      "non_irritating",
      "moisturizing"        ← NEW
    ]
  }
}
```

2. **Update Frontend** (`frontend/src/components/FeedbackPanel.tsx`):
```typescript
const likeReasons = [
  { id: 'hydrated_well', label: 'Hydrated Well' },
  { id: 'absorbed_quickly', label: 'Absorbed Quickly' },
  { id: 'non_irritating', label: 'Non-Irritating' },
  { id: 'moisturizing', label: 'Very Moisturizing' }  ← NEW
];
```

3. **Test:**
```bash
# Run test with new tag
python test_ml_comprehensive_standalone.py
```

### Task 2: Debug Model Not Learning

**Symptoms:**
- Recommendations not changing after feedback
- All products have same score

**Debugging:**

1. **Check feedback is saved:**
```python
# In Python shell
from data.schema import UserProductEvent
from data.db import get_db

db = get_db()
events = db.query(UserProductEvent).filter_by(user_id="user_123").all()
print(f"Found {len(events)} feedback events")
for event in events:
    print(f"  Product {event.product_id}: {event.reaction}")
    print(f"    Tags: {event.reason_tags}")
    print(f"    Text: {event.free_text}")
```

2. **Check model is selected:**
```python
from deployment.api.app import get_best_model

model = get_best_model(len(events))
print(f"Selected model: {model.__class__.__name__}")
```

3. **Check UserState reconstruction:**
```python
from deployment.api.app import _load_user_state_from_db

user_state = _load_user_state_from_db("user_123")
print(f"Liked vectors: {len(user_state.liked_vectors)}")
print(f"Disliked vectors: {len(user_state.disliked_vectors)}")
print(f"Irritation vectors: {len(user_state.irritation_vectors)}")
```

4. **Check model training:**
```python
model.fit(user_state)
print("Model trained")

# Test on a few products
scores = [model.predict_preference(v) for v in test_vectors[:5]]
print(f"Scores: {scores}")
```

### Task 3: Add Explanation to Recommendations

**Scenario:** Want better "why" text in recommendations

**File:** `deployment/api/app.py` (in `/api/recommendations`)

**Add explanation logic:**
```python
def get_explanation(user_state, product_id, score):
    """Generate human-readable explanation"""
    if score >= 0.8:
        if len(user_state.liked_vectors) > 0:
            return "Matches products you've liked"
        else:
            return "Great match for your preferences"
    elif score >= 0.6:
        return "Similar to your interests"
    else:
        return "Worth exploring"
```

**Return in recommendation:**
```python
recommendation = {
    "product_id": product_id,
    "score": score,
    "explanation": get_explanation(user_state, product_id, score)
}
```

---

## Testing & Quality Assurance

### Run Comprehensive Tests

```bash
cd /Users/geethika/projects/SkinCares/SkinCares
python test_ml_comprehensive_standalone.py
```

**What it tests:**
- ✅ Phase 1: Onboarding saves profile
- ✅ Phase 2: Feedback questions trigger
- ✅ Phase 3: Feedback stores in DB
- ✅ Phase 4: Model trains from feedback
- ✅ Phase 5: Recommendations generated
- ✅ Phase 6: End-to-end pipeline works

### Check Specific Components

**Test feedback storage:**
```bash
python test_feedback_integration_standalone.py
```

**Test model training:**
```bash
python test_trained_models.py
```

**Test recommendation pipeline:**
```bash
python test_supabase_connection.py
```

---

## Performance & Monitoring

### Key Metrics to Track

| Metric | How to Measure | Good Value |
|--------|----------------|-----------|
| Feedback Submission Rate | Events per user per week | > 2 |
| Model Training Time | Latency on `/api/recommendations` | < 500ms |
| Recommendation Click-Through | Recommendations clicked | > 10% |
| Model Accuracy | Whether recommendations help | > 60% |

### Monitoring Queries

**User engagement:**
```sql
SELECT user_id, COUNT(*) as feedback_count
FROM user_product_events
WHERE created_at > NOW() - INTERVAL 7 DAY
GROUP BY user_id
ORDER BY feedback_count DESC;
```

**Model performance:**
```sql
SELECT 
  model_type,
  COUNT(*) as user_count,
  AVG(confidence) as avg_confidence
FROM user_model_states
GROUP BY model_type;
```

---

## Troubleshooting

### Issue: "No feedback found for user"

**Probable Cause:** User hasn't given feedback yet

**Solution:**
```
1. Check if user exists: db.query(UserProfileState).get(user_id)
2. Show feedback questions when user browses
3. Create default profile if needed
4. Return default recommendations for cold start
```

### Issue: "Model training timeout"

**Probable Cause:** Too many interactions, model taking long

**Solution:**
```python
# Add timeout handling
from concurrent.futures import ThreadPoolExecutor, TimeoutError

with ThreadPoolExecutor() as executor:
    future = executor.submit(model.fit, user_state)
    try:
        future.result(timeout=5.0)  # 5 second timeout
    except TimeoutError:
        # Fall back to simpler model
        model = LogisticRegression()
        model.fit(user_state[:100])  # Use first 100 interactions
```

### Issue: "Inconsistent recommendations"

**Probable Cause:** Model not using all feedback

**Solution:**
1. Check `_load_user_state_from_db()` loads all events
2. Verify `reason_tags` and `free_text` parsed correctly
3. Ensure vectors loaded for all products
4. Test with smaller dataset first

---

## Key Takeaways for New Team Members

✅ **What the system does:**
- Collects user feedback through 4-step panel
- Learns user preferences from feedback
- Generates personalized recommendations

✅ **Why it works:**
- 4-step flow captures both quick + detailed feedback
- Database design preserves reason signals
- Models train on feedback to learn patterns
- Dynamic model selection scales with user data

✅ **How to extend it:**
- Add new tags → Update `features/ingredient_groups.json`
- Change model behavior → Edit `ml_feedback_model.py`
- Add explanations → Modify `/api/recommendations`
- Monitor performance → Track metrics in database

✅ **How to debug:**
- Check feedback in database
- Verify model selection
- Inspect UserState reconstruction
- Test model training with small dataset

---

## Additional Resources

**Files to Study:**
1. `deployment/api/app.py` - Main API (1000+ lines)
2. `skincarelib/ml_system/ml_feedback_model.py` - Model classes
3. `data/schema.py` - Database models
4. `frontend/src/components/FeedbackPanel.tsx` - Frontend
5. `test_ml_comprehensive_standalone.py` - Test suite

**Questions?**
1. Check `ML_SYSTEM_VERIFICATION_REPORT.md` for detailed architecture
2. Run `test_ml_comprehensive_standalone.py` to see system in action
3. Read code comments in main files
4. Test locally before committing changes

**Next for the Team:**
- [ ] All team members run test suite locally
- [ ] Review database schema
- [ ] Understand model selection logic
- [ ] Test feedback submission flow
- [ ] Monitor recommendation quality

---

**Last Updated:** 2024  
**System Status:** ✅ Production Ready  
**All Tests Passing:** ✅ YES
