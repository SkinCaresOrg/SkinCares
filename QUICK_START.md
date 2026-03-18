# Quick Start: ML Feedback Models

## 30-Second Summary

Replace weighted average feedback with real ML:

```python
from skincarelib.ml_system.integration import recommend_with_feedback

# Just add model_type="logistic" (or random_forest, gradient_boosting, contextual_bandit)
recommendations = recommend_with_feedback(
    user_state=user,
    metadata_df=products,
    tokens_df=tokens,
    constraints={},
    model_type="logistic"  # ← Real ML instead of weighted average!
)
```

## Setup (Once)

```bash
cd /Users/geethika/projects/SkinCares
source venv/bin/activate
```

## Choose Your Model

### 1️⃣ **Logistic Regression** (Fast & Interpretable)
```python
recommendations = recommend_with_feedback(
    user_state=user,
    metadata_df=metadata,
    tokens_df=tokens,
    constraints={},
    model_type="logistic"
)
```
**Best for**: Explainability, fast inference, small datasets

### 2️⃣ **Random Forest** (Feature Importance)
```python
from skincarelib.ml_system.feedback_update import create_feedback_model

model = create_feedback_model("random_forest", n_estimators=100)
model.fit(user)
importance = model.get_feature_importance()  # See what matters!
scores = model.score_products(product_vectors)
```
**Best for**: Understanding which features users care about

### 3️⃣ **Gradient Boosting** (Highest Accuracy)
```python
recommendations = recommend_with_feedback(
    user_state=user,
    metadata_df=metadata,
    tokens_df=tokens,
    constraints={},
    model_type="gradient_boosting"
)
```
**Best for**: Maximum accuracy, production recommendations

### 4️⃣ **Contextual Bandit** (Online Learning)
```python
from skincarelib.ml_system.feedback_update import create_feedback_model

bandit = create_feedback_model("contextual_bandit", dim=50)

# Real-time learning - update as feedback arrives
bandit.update(product_vec, reward=1)  # User liked it
bandit.update(product_vec, reward=0)  # User disliked it

# Instant scores
scores = bandit.score_products(product_vectors)
```
**Best for**: Real-time adaptation, exploration/exploitation

### 0️⃣ **Weighted Average** (Legacy Default)
```python
# No model_type specified = uses weighted average (backward compatible)
recommendations = recommend_with_feedback(
    user_state=user,
    metadata_df=metadata,
    tokens_df=tokens,
    constraints={}
)
```
**Best for**: Backward compatibility, cold start

## Run Tests

```bash
python -m pytest tests/test_ml_feedback_models.py -v
```

## Run Simulations

```bash
# Single model test
python -m skincarelib.ml_system.simulation --model logistic

# Compare all models
python -m skincarelib.ml_system.simulation --compare

# Try different models
python -m skincarelib.ml_system.simulation --model random_forest
python -m skincarelib.ml_system.simulation --model gradient_boosting
python -m skincarelib.ml_system.simulation --model contextual_bandit
```

## Run Demo

```bash
# Single model demo
python examples/ml_feedback_demo.py --model logistic

# Compare all models
python examples/ml_feedback_demo.py --compare

# With more products
python examples/ml_feedback_demo.py --model gradient_boosting --n_products 500
```

## Typical Workflow

```python
from skincarelib.ml_system.feedback_update import UserState, update_user_state
from skincarelib.ml_system.integration import recommend_with_feedback

# 1. Create user
user = UserState(dim=256)

# 2. Add user feedback
update_user_state(user, "like", moisturizer_vec, ["hydrating"])
update_user_state(user, "dislike", greasy_sunscreen_vec)
update_user_state(user, "irritation", bad_cleanser_vec)

# 3. Get recommendations with ML
recommendations = recommend_with_feedback(
    user_state=user,
    metadata_df=products,
    tokens_df=tokens,
    constraints={"budget": 50, "skin_type": "oily"},
    top_n=10,
    model_type="random_forest"  # ← ML-powered!
)

# 4. Display results
print(recommendations[["product_id", "brand", "price"]])

# 5. User gives more feedback
update_user_state(user, "like", recommendations.iloc[0])

# 6. Get updated recommendations (model learns!)
recommendations_v2 = recommend_with_feedback(
    user_state=user,
    metadata_df=products,
    tokens_df=tokens,
    constraints={"budget": 50, "skin_type": "oily"},
    top_n=10,
    model_type="random_forest"
)
```

## Comparison Table

| Feature | Logistic | RF | Gradient | Bandit |
|---------|----------|----|---------|----|
| Speed | ⚡⚡⚡ | ⚡⚡ | ⚡ | ⚡⚡⚡ |
| Accuracy | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Feature Importance | ✅ | ✅ | ✅ | ✅ |
| Online Learning | ❌ | ❌ | ❌ | ✅ |
| Interpretable | ✅ | ⭐⭐ | ⭐ | ⭐⭐ |
| Min Data | 2 | 2 | 2 | 1 |

## API Reference

### Creating Models
```python
from skincarelib.ml_system.feedback_update import create_feedback_model

logistic = create_feedback_model("logistic")
rf = create_feedback_model("random_forest", n_estimators=100)
gb = create_feedback_model("gradient_boosting", n_estimators=100)
bandit = create_feedback_model("contextual_bandit", dim=50, learning_rate=0.01)
```

### Training (except Bandit)
```python
success = model.fit(user_state)
if not success:
    print("Not enough data (need >=2 interactions)")
```

### Predicting
```python
# Single product
score = model.predict_preference(product_vector)  # Returns 0.0-1.0

# Multiple products
scores = model.score_products(product_vectors)  # Returns array
```

### Bandit-Specific
```python
# Online update (no retraining!)
bandit.update(product_vector, reward=1)
bandit.update(product_vector, reward=0)

# Get uncertainty (for exploration)
uncertainty = bandit.get_uncertainty()
```

### Feature Importance (RF & Gradient Boosting)
```python
importance = model.get_feature_importance()  # array of importances
top_5 = np.argsort(importance)[-5:][::-1]
```

### Persistence
```python
model.save(Path("my_model.pkl"))
model.load(Path("my_model.pkl"))
```

## When to Use Each Model

### Use Logistic Regression When:
- ✅ You need fast training & inference
- ✅ Explainability is important
- ✅ You have limited data (2-100 interactions)
- ✅ You want probability estimates

### Use Random Forest When:
- ✅ You want to understand feature importance
- ✅ You need robustness to outliers
- ✅ You have more data (100+ interactions)
- ✅ Non-linear patterns matter

### Use Gradient Boosting When:
- ✅ Maximum accuracy is critical
- ✅ You have sufficient data (500+ interactions)
- ✅ You can afford training time
- ✅ You want state-of-the-art results

### Use Contextual Bandit When:
- ✅ You need real-time learning
- ✅ Data arrives incrementally
- ✅ Exploration/exploitation tradeoff matters
- ✅ You can't afford retraining overhead

## Troubleshooting

### Model returns 0.5 (neutral) on everything
```
→ Insufficient training data (need >=2 interactions)
→ User preferences are balanced
→ Try adding more user feedback
```

### Slow inference
```
→ Using Gradient Boosting (slow but accurate)
→ Try Logistic Regression for speed
→ Use Contextual Bandit for real-time
```

### Model doesn't adapt to feedback
```
→ Using Logistic/RF/GB: need to retrain (automatic in integrate.py)
→ Using Bandit: should be immediate
→ Check that update_user_state() is called
```

## Documentation

- **Full guide**: [docs/ml_feedback_models.md](docs/ml_feedback_models.md)
- **Implementation summary**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Test suite**: [tests/test_ml_feedback_models.py](tests/test_ml_feedback_models.py)

## Examples

- **Single model**: [examples/ml_feedback_demo.py](examples/ml_feedback_demo.py)
- **Simulation**: Run `python -m skincarelib.ml_system.simulation --compare`

---

**That's it!** You now have production-ready ML-based feedback instead of weighted average. 🎉
