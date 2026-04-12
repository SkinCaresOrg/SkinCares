# ML Model Testing & Improvement Guide

## 🚀 Quick Start

### 1. **Set Up Supabase Connection**

Add to your `.env` file:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
```

Get these from Supabase dashboard:
- Go to Settings → API
- Copy `Project URL` and `anon public key`

### 2. **Install Supabase Client**

```bash
pip install supabase
```

---

## 🧪 **Test Your Models**

### **Run Unit Tests**
```bash
# Test ML models
pytest tests/test_ml_feedback_models.py -v

# Test all components
pytest tests/ -v --tb=short
```

### **Run Model Evaluation**
```bash
# Compare all 4 models on synthetic data
python scripts/evaluate_ml_models.py
```

This will output:
```
============================================================
ML Model Evaluation Pipeline
============================================================

[1/3] Creating synthetic test data...
✓ Created 10 test users, 50 products

[2/3] Initializing ML models...
✓ Initialized 4 models

[3/3] Evaluating models...

============================================================
logistic_regression
============================================================
Accuracy:  75.42%
Precision: 82.15%
Recall:    68.33%
F1 Score:  74.67%
Tested on: 157 samples

🏆 Best Model: gradient_boosting (82.31% accuracy)

✓ Report saved to artifacts/evaluation_report.json
```

---

## 📊 **Check Model Metrics from API**

Once your app is running:

### **Get Current Model Accuracy**
```bash
curl http://localhost:8000/api/ml/model-metrics
```

Response:
```json
{
  "vowpal_wabbit": {
    "accuracy": 0.84,
    "total_predictions": 150,
    "correct": 126
  },
  "random_forest": {
    "accuracy": 0.78,
    "total_predictions": 145,
    "correct": 113
  }
}
```

### **Compare All Models**
```bash
curl http://localhost:8000/api/ml/compare-models
```

Response:
```json
{
  "all_models": {
    "vowpal_wabbit": {...},
    "random_forest": {...},
    ...
  },
  "best_model": {
    "name": "vowpal_wabbit",
    "accuracy": 0.84
  }
}
```

---

##📈 **How Predictions Are Logged**

The backend automatically logs every prediction:

```python
# In deployment/api/app.py - when a user gets recommendations:

# Get prediction score
predicted_score = model.predict_score(product_vec, user_state)

# Log for evaluation
log_prediction_to_supabase(
    user_id=user_id,
    product_id=product_id,
    predicted_score=predicted_score,
    actual_reaction=user_reaction,  # like/dislike/irritation
    model_version="vowpal_wabbit"
)
```

Each log includes:
- `user_id`: Which user
- `product_id`: Which product  
- `predicted_score`: 0-1 confidence
- `actual_reaction`: What user actually did
- `is_correct`: Whether prediction matched reality
- `model_version`: which model made prediction

---

## 🎯 **Key Metrics to Track**

| Metric | Target | How to Improve |
|--------|--------|----------------|
| **Accuracy** | >80% | More training data, feature engineering |
| **Precision** | >85% | Reduce false positives (wrong likes) |
| **Recall** | >75% | Reduce false negatives (missed likes) |
| **F1 Score** | >0.80 | Balance precision & recall |
| **Cold-start (0-5 swipes)** | >60% | Better questionnaire seeding |
| **Warm-start (20+ swipes)** | >85% | Vowpal Wabbit online learning |

---

## 🔄 **Improvement Workflow**

### **Week 1: Baseline**
1. Run `python scripts/evaluate_ml_models.py`
2. Check `/api/ml/model-metrics` for production accuracy
3. Record baseline in Supabase

### **Week 2: Add Features**
```python
# Add to UserState features:
- price_sensitivity: Compare prices user likes vs dislikes
- brand_affinity: Which brands does user prefer?
- ingredient_frequency: Count liked/disliked ingredients
- category_exploration: Diversity of categories explored
```

### **Week 3: A/B Test**
- Users Group A: Old model (Logistic Regression)
- Users Group B: New model (Gradient Boosting)
- Compare accuracy, click-through, conversion

### **Week 4: Deploy Winner**
- Update `VOWPAL_WABBIT_MODEL_PATH` to best model
- Monitor in Supabase
- Set alerts for accuracy drop

---

## 🚨 **Monitor Production Model**

### **Set Up Alerts** (in your monitoring tool)

Alert if accuracy drops below 75%:
```sql
SELECT model_version, COUNT(*) as predictions, 
       SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)::float / COUNT(*) as accuracy
FROM model_predictions_audit
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY model_version
HAVING SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)::float / COUNT(*) < 0.75
```

### **Daily Metrics Dashboard**

```python
# Check daily accuracy trend
python -c "
import requests
metrics = requests.get('http://localhost:8000/api/ml/model-metrics').json()
for model, data in metrics.items():
    print(f'{model}: {data[\"accuracy\"]:.1%}')
"
```

---

## 📝 **Feature Engineering Ideas**

### **Add Price Sensitivity Signal**
```python
def extract_price_signal(user: UserState, product_prices: dict) -> float:
    liked_prices = [product_prices[pid] for pid in user.liked_product_ids]
    disliked_prices = [product_prices[pid] for pid in user.disliked_product_ids]
    
    if not liked_prices or not disliked_prices:
        return 0.0
    
    avg_liked = np.mean(liked_prices)
    avg_disliked = np.mean(disliked_prices)
    
    # Return ratio: if user likes expensive, return high value
    return avg_liked / max(avg_disliked, 1)
```

### **Add Brand Affinity**
```python
def extract_brand_signal(user: UserState, products: dict) -> dict:
    brand_scores = {}
    
    for product_id in user.liked_product_ids:
        brand = products[product_id]["brand"]
        brand_scores[brand] = brand_scores.get(brand, 0) + 1
    
    return brand_scores
```

### **Add Ingredient Frequency**
```python
def extract_ingredient_signals(user: UserState, products: dict) -> dict:
    ingredient_scores = {}
    
    for product_id in user.liked_product_ids:
        ingredients = products[product_id]["ingredients"]
        for ing in ingredients:
            ingredient_scores[ing] = ingredient_scores.get(ing, 0) + 1
    
    return ingredient_scores
```

---

## ✅ **Checklist**

- [ ] Added `SUPABASE_URL` and `SUPABASE_KEY` to `.env`
- [ ] Ran `pip install supabase`
- [ ] Created Supabase tables (check with admin)
- [ ] Tested endpoint: `curl http://localhost:8000/api/ml/model-metrics`
- [ ] Ran evaluation: `python scripts/evaluate_ml_models.py`
- [ ] Checked `artifacts/evaluation_report.json`
- [ ] Set up daily metric checks
- [ ] Planned first feature engineering task
