# API Quick Reference

## SwipeSession - Main Class

### Initialization
```python
session = SwipeSession(
    user_id,           # str: unique user identifier
    product_vectors,   # ndarray: (N_products, 534)
    product_metadata,  # DataFrame: product details
    product_index,     # dict: product_id -> array_index
    learning_rate=0.1, # float: VW learning rate (0.01-0.5)
    initial_epsilon=0.8 # float: exploration ratio (0-1)
)
```

### User Onboarding
```python
session.complete_onboarding(
    skin_type,           # str: "Oily"|"Dry"|"Sensitive"|"Combination"|"Normal"
    skin_concerns,       # list[str]: subset of ["Acne", "Dark spots", "Dryness", "Sensitivity", "Oiliness", "Fine lines", "Wrinkles"]
    budget_range,        # tuple: (range_label, max_price) e.g., ("50-100", 100)
    preferred_categories="" # str: optional, comma-separated categories
)
```

### Get Next Product
```python
product_id, metadata = session.get_next_product()
# Returns: (str, dict)
# metadata keys: product_id, brand, category, price, confidence_score, exploration_action
```

### Record User Feedback
```python
result = session.record_swipe(
    product_id,       # str: product identifier
    tried_status,     # str: "yes" or "no"
    reaction,         # str: "like", "dislike", or "skip"
    feedback_reasons  # list[str]: why they liked/disliked
)
# ⚠️ MODEL UPDATES HERE - next prediction will use updated weights
```

### Get Recommendations
```python
recommendations = session.get_recommendations(
    top_n=5  # int: number of recommendations
)
# Returns: DataFrame with columns: product_id, brand, category, price, preference_score
```

### Monitoring
```python
state = session.get_session_state()
# Returns dict with:
# - total_products_shown
# - products_rated
# - model_interactions_learned
# - exploration_exploitation (epsilon, rates)
# - feedback_summary (tried, liked, disliked)

curves = session.get_learning_curves()
# Returns dict with:
# - engagement_over_time
# - ingredient_preference_convergence
```

---

## OnlineLearner - Vowpal Wabbit Wrapper

```python
from skincarelib.ml_system.online_learning import OnlineLearner

learner = OnlineLearner(dim=534, learning_rate=0.1)

# Learn from interaction (called automatically by SwipeSession)
learner.learn_from_interaction(
    product_vec,   # ndarray: product embedding (534,)
    label,         # int: 1=like, -1=dislike, 0=skip
    user_context   # dict: skin_type, budget, concerns, etc.
)

# Predict preference (called automatically by SwipeSession)
score, metadata = learner.predict_preference(
    product_vec,   # ndarray: product embedding
    user_context   # dict: user features
)
# Returns: (float in [-1, 1], dict with prediction_count, models_used)
```

---

## ContextualBanditStrategy - Exploration/Exploitation

```python
from skincarelib.ml_system.online_learning import ContextualBanditStrategy

bandit = ContextualBanditStrategy(
    initial_epsilon=0.8,  # float: start with 80% exploration
    decay_rate=0.02       # float: decay rate per interaction
)

# Select product (called automatically by SwipeSession)
product_id, was_exploration = bandit.select_product(
    candidate_scores  # dict: {product_id: score, ...}
)
# Returns: (str, bool) - selected product and whether it was exploration
```

---

## DetailedFeedbackCollector - Category-Specific Questions

```python
from skincarelib.ml_system.feedback_structures import DetailedFeedbackCollector

collector = DetailedFeedbackCollector()

# Get follow-up questions
question, options = collector.get_followup_questions(
    category,  # str: "Cleanser"|"Moisturizer"|"Face Mask"|"Treatment"|"Eye Cream"|"Sun Protect"
    reaction   # str: "like" or "dislike"
)
# Returns: (str, list[str])

# Record feedback
feedback = collector.record_feedback(
    product_id,   # str
    category,     # str
    tried_status, # str: "yes"|"no"
    reaction,     # str: "like"|"dislike"
    reasons       # list[str]
)

# Get feedback summary
summary = collector.get_feedback_summary()
# Returns: dict with counts of likes, dislikes, and reasons per category
```

---

## InitialUserQuestionnaire - Cold-Start Profiling

```python
from skincarelib.ml_system.feedback_structures import InitialUserQuestionnaire

questionnaire = InitialUserQuestionnaire()

# Set user profile
questionnaire.set_user_profile(
    skin_type,           # str: from SKIN_TYPES
    skin_concerns,       # list[str]: from SKIN_CONCERNS
    budget_range,        # tuple: (label, max_value)
    preferred_categories="" # str: optional
)

# Get model-ready features
context = questionnaire.get_context_features()
# Returns: dict with keys: skin_type, budget, concerns, category_pref

# Get options for UI
SKIN_TYPES = ["Dry", "Oily", "Sensitive", "Combination", "Normal"]
SKIN_CONCERNS = ["Acne", "Dark spots", "Dryness", "Sensitivity", "Oiliness", "Fine lines", "Wrinkles"]
BUDGET_RANGES = [("$20-50", 50), ("$50-100", 100), ("$100-200", 200), ("$200+", 9999)]
```

---

## IngredientPreferenceTracker - Ingredient-Level Learning

```python
from skincarelib.ml_system.feedback_structures import IngredientPreferenceTracker

tracker = IngredientPreferenceTracker()

# Record feedback with ingredients
tracker.record_ingredient_feedback(
    ingredients,  # list[str]: ingredient names
    rating,       # int: 1=like, -1=dislike, 0=skip
    product_id    # str
)

# Get preference scores per ingredient
scores = tracker.get_ingredient_preference_scores()
# Returns: dict[str, float] - maps ingredient -> score in [-1, 1]

# Get disliked ingredients
disliked = tracker.get_disliked_ingredients(threshold=-0.5)
# Returns: list[str] of ingredients user likely dislikes

# Get liked ingredients
liked = tracker.get_liked_ingredients(threshold=0.5)
# Returns: list[str] of ingredients user likely likes
```

---

## Constants & Enums

```python
# Skin Types
SKIN_TYPES = ["Dry", "Oily", "Sensitive", "Combination", "Normal"]

# Skin Concerns
SKIN_CONCERNS = [
    "Acne",
    "Dark spots",
    "Dryness",
    "Sensitivity",
    "Oiliness",
    "Fine lines",
    "Wrinkles"
]

# Budget Ranges
BUDGET_RANGES = [
    ("$20-50", 50),
    ("$50-100", 100),
    ("$100-200", 200),
    ("$200+", 9999)
]

# Product Categories (from feedback collector)
PRODUCT_CATEGORIES = [
    "Cleanser",
    "Moisturizer",
    "Face Mask",
    "Treatment",
    "Eye Cream",
    "Sun Protect"
]

# Reaction Types
REACTIONS = ["like", "dislike", "skip"]

# VW Label Space
LABELS = {
    "like": 1,
    "dislike": -1,
    "skip": 0
}
```

---

## Common Patterns

### Pattern 1: Basic Swipe Loop
```python
for i in range(10):
    product_id, product = session.get_next_product()
    reaction = user_swipes(product)  # like/dislike/skip
    session.record_swipe(product_id, "yes", reaction, [])
```

### Pattern 2: With Feedback
```python
for i in range(10):
    product_id, product = session.get_next_product()
    reaction = user_swipes(product)
    feedback = get_user_feedback(product, reaction)  # user answers follow-up questions
    session.record_swipe(product_id, "yes", reaction, feedback)
```

### Pattern 3: Checking Progress
```python
session.complete_onboarding(skin_type, concerns, budget)

for i in range(50):
    product_id, _ = session.get_next_product()
    reaction = user_interaction()
    session.record_swipe(product_id, "yes", reaction, [])
    
    if (i + 1) % 10 == 0:
        state = session.get_session_state()
        print(f"Epsilon: {state['exploration_exploitation']['epsilon']:.2f}")
        print(f"Like rate: {state['feedback_summary']['products_liked'] / state['feedback_summary']['products_tried']:.1%}")

recommendations = session.get_recommendations(5)
```

### Pattern 4: Ingredient Tracking
```python
recommendations = session.get_recommendations(5)
disliked_ingredients = session.ingredient_tracker.get_disliked_ingredients(threshold=-0.6)

# Filter future recommendations to exclude these
recommendations = recommendations[recommendations['ingredients'].apply(
    lambda ingr: not any(d in ingr for d in disliked_ingredients)
)]
```

---

## Hyperparameters to Tune

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| learning_rate | 0.1 | 0.01-0.5 | Higher = faster learning, more noise |
| initial_epsilon | 0.8 | 0.5-1.0 | Higher = more initial exploration |
| decay_rate | 0.02 | 0.01-0.1 | Higher = quicker shift to exploitation |

### Tuning Guide
```
Slow learning? Try learning_rate=0.3
Model too random? Try decay_rate=0.05
Quick convergence? Try learning_rate=0.5 + decay_rate=0.1
```

---

## Error Handling

```python
try:
    session.record_swipe(product_id, "yes", "like", ["reason"])
except ValueError as e:
    if "dimension mismatch" in str(e):
        # Product vector size != 534
        pass
    elif "Unknown category" in str(e):
        # Invalid product category
        pass
except KeyError as e:
    # Product not in index
    pass
```

---

## Testing

```python
import pytest
from skincarelib.ml_system.swipe_session import SwipeSession

def test_session():
    session = SwipeSession(...)
    session.complete_onboarding("Dry", ["Dryness"], ("50-100", 100))
    
    for _ in range(5):
        product_id, _ = session.get_next_product()
        session.record_swipe(product_id, "yes", "like", [])
    
    state = session.get_session_state()
    assert state["products_rated"] == 5
    
    recs = session.get_recommendations(3)
    assert len(recs) == 3
```

**Run tests**:
```bash
pytest tests/test_online_learning_swipes.py -v
```

---

## Performance Tips

1. **Batch initialization**: Load product vectors once at startup
2. **Cache predictions**: Don't call get_next_product multiple times without swiping
3. **Async recording**: Use threading for session.record_swipe() if needed
4. **Monitor memory**: Session memory grows with swipe history (~1KB per swipe)
5. **Archive old sessions**: Consider archiving sessions with 1000+ swipes

---

## Debugging Tips

```python
# Inspect session state
print(session.get_session_state())

# Check learning progress
curves = session.get_learning_curves()
print(curves['engagement_over_time'])

# Look at ingredient preferences
print(session.ingredient_tracker.get_ingredient_preference_scores())

# Check what products are marked as shown
print(session.products_shown)

# Track model confidence
for _ in range(5):
    product_id, metadata = session.get_next_product()
    print(f"Confidence: {metadata['confidence_score']:.2f}")
    session.record_swipe(product_id, "yes", "like", [])
```

