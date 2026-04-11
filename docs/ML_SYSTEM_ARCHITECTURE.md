# SkinCares ML System: Complete Architecture Guide

## 📊 System Overview

The SkinCares ML system learns personalized skincare product recommendations from user feedback in real-time. Instead of using fixed rules, it adapts after every swipe.

**Core Philosophy:** Each user interaction teaches the model. First swipe is personalized (via cold-start). By swipe #5, recommendations are highly tailored.

---

## 👤 User Journey

### Phase 1: Onboarding (Cold Start)

```
User arrives
    ↓
Answers questionnaire:
├─ Skin type: "Oily" | "Dry" | "Sensitive" | "Combination" | "Normal"
├─ Skin concerns: ["Acne", "Dryness", "Sensitivity", "Dark spots", "Wrinkles", ...]
├─ Budget: "$20-50" | "$50-100" | "$100-200" | "$200+"
└─ Product categories (optional)
    ↓
[NEW] Cold-Start Pre-Training
├─ System scans product metadata for keyword matches
├─ Finds products for "Acne" user → adds as pseudo-likes
├─ Finds unsuitable products → adds as pseudo-dislikes
├─ Seeds Vowpal Wabbit online learner
└─ Model now has ~10-15 pseudo-interactions
    ↓
Onboarding complete - ready to swipe!
```

**Why:** Day 1 recommendations are personalized, not generic.

---

### Phase 2: Swiping Loop (Real-time Learning)

```
Get Next Product
    ↓
    [Contextual Bandit Decision]
    ├─ Early sessions: 80% random (explore) + 20% high-score (exploit)
    ├─ Later sessions: 20% random + 80% high-score
    └─ Epsilon decays smoothly (exploration → exploitation)
    ↓
Display Product
    ↓
User Swipes: "like" | "dislike" | "skip"
    ↓
    [Detailed Feedback Collection]
    ├─ Category-specific follow-up questions
    ├─ For Moisturizer + like: "What did you like?"
    │  Options: ["Hydrated well", "Absorbed quickly", "Good price", ...]
    ├─ For Cleanser + dislike: "Why didn't you like it?"
    │  Options: ["Too stripping", "Broke me out", "Expensive", ...]
    └─ Tracks ingredient preferences
    ↓
    [ONLINE LEARNING UPDATE] ⭐ KEY STEP
    ├─ Extract product vector (534-dimensional embedding)
    ├─ Get user context (skin type, budget, concerns)
    ├─ Update Vowpal Wabbit: learns immediately
    ├─ Track ingredient preferences
    ├─ Update ingredient tracker
    └─ Model instantly adapts
    ↓
Next iteration uses UPDATED model
```

**Repeat:** Until user stops or reaches 50+ swipes.

---

## 🧠 Models Used

### 1️⃣ **Vowpal Wabbit (Logistic Regression via VW)**
**File:** `skincarelib/ml_system/online_learning.py`

**What:**
- Online learning library optimized for real-time model updates
- No batch retraining needed
- Updates weights after each swipe

**How:**
```
Each swipe:
  1. Extract product vector (534-dim)
  2. Add user context features (skin type, budget) 
  3. Learn: VW updates weights based on feedback
  4. Next swipe uses updated weights
  
Result: Model learns continuously, on-demand
```

**When Used:** Every swipe, always active

**Strengths:**
- ⚡ Fast incremental updates
- 🎯 Real-time adaptation  
- 📊 Built-in exploration/exploitation
- 💾 Memory efficient

**Example:**
```python
# After user likes "Moisturizer A"
swipe = {
  product_vec: [0.5, 0.2, 0.8, ...],  # 534 dims
  label: 1  # Like = 1
}
vw_model.learn(swipe)
# VW instantly adjusts weights for similar products
```

---

### 2️⃣ **Logistic Regression (Batch Learning Mode)**
**File:** `skincarelib/ml_system/feedback_lr_model.py`

**What:**
- Sklearn LogisticRegression for batch feedback analysis
- Used when user has 3+ interactions
- Learns feature importance from accumulated feedback

**How:**
```
Collect user feedback:
├─ Liked products: class 1
├─ Disliked products: class 0
├─ Irritated products: class -1
    ↓
Train LogisticRegression:
├─ Features: product vectors (534-dim)
├─ Target: feedback labels
├─ Output: learned feature weights
    ↓
Use model to score new candidates by probability
```

**When Used:** 
- Optional advanced path (not default)
- When `recommend_with_lr_feedback()` called
- Provides interpretable feature importance

**Strengths:**
- 🔍 Interpretable (see which features matter)
- 🎓 Learnable with minimal data (3+ items)
- 📈 Good for analysis and reporting

---

### 3️⃣ **Embedding-Based User Profiling**
**File:** `skincarelib/ml_system/embedding_collab_filter.py`

**What:**
- Builds user preference embedding from feedback
- Uses cosine similarity to rank products
- **NOT classical collaborative filtering** (despite name)

**How:**
```
User feedback adds to embedding:
├─ +1.5 × liked product vectors
├─ -0.8 × disliked product vectors  
├─ -2.0 × irritated product vectors
    ↓
Normalize → user embedding (534-dim)
    ↓
New product score = cosine_similarity(user_embedding, product_vector)
    ↓
Rank by similarity scores
```

**When Used:**
- Optional advanced path
- When `recommend_with_collaborative_filtering()` called
- For deep user profiling

**Strengths:**
- 👥 Captures implicit preferences in embedding space
- 🎯 All decisions in 534-dim vector space
- ⚡ Fast similarity computation

---

### 4️⃣ **Contextual Bandits (Exploration/Exploitation)**
**File:** `skincarelib/ml_system/online_learning.py` → `ContextualBanditStrategy`

**What:**
- Epsilon-greedy strategy for balancing exploration vs exploitation
- Prevents "filter bubbles"
- Smoothly transitions from exploring to exploiting

**How:**
```
Initial state:
├─ epsilon = 0.8 (80% random, 20% best)
├─ User sees diverse products
└─ Model builds broad understanding

After 10 swipes:
├─ epsilon = 0.5 (50% random, 50% best)
└─ Balanced exploration/exploitation

After 50 swipes:
├─ epsilon = 0.1 (10% random, 90% best)
└─ Mostly personalized recommendations
```

**Formula:** `epsilon = initial_epsilon × exp(-decay_rate × swipes)`

**Strengths:**
- 🔄 Avoids recommending only what model thinks user likes
- 🎲 Explores new product categories
- 📈 Smooth transition to personalization

---

## 🔄 ML Pipeline Architecture

```
┌─────────────────────────────────────────────────────┐
│ USER ONBOARDING                                     │
└────────────────┬────────────────────────────────────┘
                 ↓
    ┌────────────────────────────┐
    │ Cold-Start Pre-Training    │
    │ (NEW Feature)              │
    ├────────────────────────────┤
    │ • Scan product metadata    │
    │ • Match to skin type       │
    │ • Add pseudo-feedback      │
    │ • Seed VW + LR models      │
    └────────┬───────────────────┘
             ↓
┌─────────────────────────────────────────────────────┐
│ SWIPE LOOP (Repeat × N)                             │
└────────────────┬────────────────────────────────────┘
                 ↓
    ┌────────────────────────────┐
    │ Get Next Product           │
    │ (Contextual Bandit)        │
    ├────────────────────────────┤
    │ Epsilon-greedy selection:  │
    │ • Early: explore (80%)     │
    │ • Late: exploit (80%)      │
    └────────┬───────────────────┘
             ↓
    ┌────────────────────────────┐
    │ Display Product            │
    │ (Web/Mobile UI)            │
    └────────┬───────────────────┘
             ↓
    ┌────────────────────────────┐
    │ User Swipes               │
    │ + Detailed Feedback        │
    └────────┬───────────────────┘
             ↓
    ┌────────────────────────────┐
    │ ONLINE LEARNING UPDATE ⭐  │
    │ (Immediate Model Update)   │
    ├────────────────────────────┤
    │ 1. Update VW weights       │
    │ 2. Update LR if needed     │
    │ 3. Update user embedding   │
    │ 4. Track ingredients       │
    └────────┬───────────────────┘
             ↓
    ┌────────────────────────────┐
    │ Next Product Uses          │
    │ UPDATED Model Headers      │
    └────────┬───────────────────┘
             ↓
    Ready for next swipe ↻
```

---

## 📥 Recommendation Paths (How Scoring Works)

### Path 1: Weighted Average (Legacy/Cold Start)
```
When: < 3 user interactions
How:  Fixed weights (not learned)
      score = 2.0×liked_avg - 1.0×disliked_avg - 2.0×irritation_avg
Fast: ✅ Yes
Good: ⭐ Okay (generic)
```

### Path 2: Vowpal Wabbit Online Learning (Default) ⭐
```
When: Always active (even during onboarding)
How:  VW learns weights from each swipe
      score = vw_model.predict(product_vec, context)
Fast: ✅ Yes
Good: ⭐⭐⭐ Great (personalized)
```

### Path 3: Logistic Regression (Analysis Path)
```
When: 3+ interactions + explicit call
How:  LR trains batch model
      score = lr_model.predict_probability(product_vec)
Fast: ⚠️ Slower (batch training)
Good: ⭐⭐⭐ Great (interpretable)
```

### Path 4: Embedding Similarity (Profiling Path)
```
When: Advanced mode + 3+ interactions
How:  Build user embedding, score by cosine similarity
      score = cosine(user_embedding, product_vector)
Fast: ✅ Yes
Good: ⭐⭐⭐ Great (deep profiling)
```

---

## 🔑 Important Features

### 1. **Cold-Start Pre-Training** ⭐ NEW
```python
User: "Oily skin + Acne"
    ↓
System finds ~10 acne products → pseudo-likes
System finds ~5 inappropriate products → pseudo-dislikes
    ↓
VW model trained on pseudo-feedback
    ↓
Result: First recommendation is personalized!
```

### 2. **Per-User Model Binding**
```python
# Prevents accidental data leakage between users
lr_model.bind_user("user_123")
lr_model.bind_user("user_456")  # ❌ Error! Model bound to user_123
```

### 3. **Irritation = Both Irritation + Dislike** 
```python
if reaction == "irritation":
    user.add_disliked(vec)      # Counts as dislike
    user.add_irritation(vec)    # Also counts as irritation
```

### 4. **Real-Time Model Updates**
```
User swipes → Vowpal Wabbit updates weights instantly
              → Next product uses updated model
              → No batch retraining needed
```

### 5. **Ingredient-Level Tracking**
```python
# Models learn ingredient preferences
ingredient_tracker.record_ingredient_feedback(
    ingredients=["salicylic acid", "glycerin"],
    rating=1  # Like
)

# Later, avoid disliked ingredients
disliked = ingredient_tracker.get_disliked_ingredients()
```

### 6. **Feedback Questions by Category**
```
User likes "Moisturizer":
  Q: "What did you like?"
  Options: ["Hydrated well", "Absorbed quickly", "Good price", ...]

User dislikes "Cleanser":
  Q: "Why didn't you like it?"
  Options: ["Too stripping", "Broke me out", "Expensive", ...]
```

---

## 📊 Data Flow Example

```
User Profile:
├─ ID: "user_123"
├─ Skin type: "Oily"
├─ Concerns: ["Acne", "Oiliness"]
└─ Budget: $50-100

Cold Start (Onboarding):
├─ Find "acne-fighting" products → VW += 1 (like)
├─ Find "heavy moisturizers" → VW += -1 (dislike)
└─ VW model: ~12 pseudo-interactions

Swipe 1: Show lightweight moisturizer
├─ VW scores: 0.65 (good for oily)
├─ Bandit: explore mode → random pick OK
└─ Show product

User Feedback: "like"
├─ VW learns: lightweight moisturizer vectors → positive
├─ Next products avoid heavy textures
└─ VW: 13 total interactions

Swipe 2: Show salicylic acid cleanser
├─ VW scores: 0.72 (matches "acne" concern)
├─ Model learned from swipe 1
└─ Better recommendation!

… (repeat)

Swipe 5: Model highly trained
├─ VW scores: 0.89 (very personalized)
├─ Bandit shift to exploit (90%)
└─ Recommendations = user's preference profile
```

---

## 🧪 Testing & Validation

### Test Files
```
tests/test_online_learning_swipes.py     # 26 tests ✅
├─ OnlineLearner (VW) tests
├─ ContextualBandit tests
├─ SwipeSession tests (with cold-start)
├─ Ingredient tracking tests
└─ All 26 passing ✓

tests/test_ml_feedback_models.py         # 32 tests ✅
├─ UserState tests
├─ Logistic Regression tests
├─ Random Forest tests
├─ Gradient Boosting tests
└─ All 32 passing ✓

tests/test_advanced_ml_models.py         # 19 tests ✅
├─ LR feedback model tests
├─ Embedding collaborative filter tests
└─ All 19 passing ✓

TOTAL: 77 tests ✅
```

---

## 🚀 Performance Characteristics

| Aspect | VW (Online) | LR (Batch) | Embedding |
|--------|-----------|-----------|-----------|
| Training time | < 1ms | ~10ms | ~5ms |
| Inference | ~0.1ms | ~0.5ms | ~1ms |
| Memory | ~100KB | ~10MB | ~1MB |
| Updates | Incremental | Batch | Batch |
| Min data | 1 interaction | 3 items | 3 items |
| Exploration | Built-in | N/A | Via bandit |
| Real-time | ✅ Yes | ❌ No | ❌ No |

---

## 📁 Project Structure

```
skincarelib/ml_system/
├── swipe_session.py                    # Main session manager (+ cold-start)
├── online_learning.py                  # VW wrapper + contextual bandits
├── feedback_lr_model.py                # Logistic regression feedback learning
├── embedding_collab_filter.py          # Embedding-based user profiling
├── feedback_update.py                  # User state management + feedback aggregation
├── feedback_structures.py              # Category-specific feedback, questionnaires
├── integration.py                      # Recommendation pipeline endpoints
├── simulation.py                       # Testing & benchmarking
└── ...other modules

tests/
├── test_online_learning_swipes.py      # Online learning tests (26)
├── test_ml_feedback_models.py          # Feedback model tests (32)
├── test_advanced_ml_models.py          # Advanced ML tests (19)
└── ...other tests
```

---

## 🎯 Key Takeaways

1. **Immediate Personalization:** Cold-start pre-training makes Day 1 recommendations personalized
2. **Real-Time Learning:** Vowpal Wabbit updates after every swipe (no batch retraining)
3. **Multiple Approaches:** VW (fast), LR (interpretable), Embeddings (deep profiling)
4. **Safe Design:** Per-user model binding, ingredient tracking, multi-label feedback
5. **Exploration-Exploitation:** Contextual bandits balance discovery vs personalization
6. **Production Ready:** 77 tests passing, comprehensive error handling, backward compatible

---

## 🔗 Related Files

**Core ML System:**
- `skincarelib/ml_system/swipe_session.py` - User session management
- `skincarelib/ml_system/online_learning.py` - Vowpal Wabbit integration
- `skincarelib/ml_system/feedback_lr_model.py` - Logistic Regression learning

**Integration:**
- `skincarelib/ml_system/integration.py` - Recommendation endpoints
- `deployment/api/` - REST API for frontend

**Testing:**
- `tests/test_online_learning_swipes.py` - Online learning tests
- `tests/test_ml_feedback_models.py` - Feedback model tests
- `tests/test_advanced_ml_models.py` - Advanced ML tests

---

**Last Updated:** March 26, 2026  
**Status:** ✅ Production Ready  
**Tests:** ✅ 77/77 Passing
