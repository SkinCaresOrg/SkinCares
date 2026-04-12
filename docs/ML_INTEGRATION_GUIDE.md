# ML Model Integration Guide

Complete guide for verifying and using the ML recommendation engine with Supabase tracking.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend (React)                        │
│  - User fills onboarding form                                    │
│  - User swipes products (like/dislike/skip)                      │
│  - Displays recommendations with explanation                     │
│  - Shows ML model performance (new)                              │
└──────────────┬──────────────────────────────────────────────────┘
               │ API Calls
               ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Backend API (FastAPI)                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Endpoints:                                                 │ │
│  │  GET  /api/recommendations/{user_id}                      │ │
│  │       → Calls get_best_model() → Logs predictions ✓       │ │
│  │  POST /api/swipe/{event_id}/questionnaire                 │ │
│  │       → Updates UserState → Logs feedback ✓               │ │
│  │  GET  /api/ml/model-metrics                              │ │
│  │       → Returns accuracy by model                         │ │
│  │  GET  /api/ml/compare-models                             │ │
│  │       → Ranked comparison with metadata                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ML Model Selection:                                        │ │
│  │  < 5:    LogisticRegression (fast)                        │ │
│  │  5-20:   RandomForest                                     │ │
│  │  20-100: GradientBoosting                                 │ │
│  │  100-500: LightGBM (if installed)                         │ │
│  │  500+:   XLearn FFM (if installed)                        │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────┬──────────────────────────────────────────────────┘
               │ Logs Predictions
               ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Supabase Database                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ model_predictions_audit:                                   │ │
│  │  - user_id, product_id, predicted_score                   │ │
│  │  - actual_reaction (like/dislike/pending)                 │ │
│  │  - model_version (e.g., "LightGBM (Power User)")         │ │
│  │  - is_correct (calculated from prediction vs reality)    │ │
│  │  - created_at (timestamp)                                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│  Other tables: ml_model_versions, ab_test_results, etc.        │
└─────────────────────────────────────────────────────────────────┘
```

## Setup Checklist

### Step 1: Configure Environment Variables

```bash
# Backend .env file
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key"
export SUPABASE_AVAILABLE=1
```

**Get credentials from:**
- Supabase Dashboard → Settings → API
- Copy "URL" and "anon" key

### Step 2: Verify Supabase Tables Exist

Check that these tables exist in your Supabase database:

```sql
-- model_predictions_audit
SELECT COUNT(*) FROM model_predictions_audit;

-- ml_model_versions
SELECT COUNT(*) FROM ml_model_versions;

-- ab_test_results
SELECT COUNT(*) FROM ab_test_results;

-- feature_importance
SELECT COUNT(*) FROM feature_importance;
```

If tables don't exist, run the migration scripts (see [Database Setup](./DATABASE_SETUP.md))

### Step 3: Install Advanced Models (Optional)

```bash
# LightGBM (highly recommended for production)
pip install lightgbm>=4.0.0

# XLearn (for ultra-large datasets)
pip install xlearn

# Vowpal Wabbit (for online learning)
pip install vowpalwabbit
```

## Verification

### Run Integration Check

```bash
python scripts/check_ml_integration.py
```

This will verify:
- ✅ Supabase connection
- ✅ All ML models available
- ✅ Prediction logging works
- ✅ Model selection strategy
- ✅ Metrics retrieval

### Test Individual Components

#### 1. Test Supabase Connection

```python
from deployment.api.app import supabase_client

if supabase_client:
    # Try to read predictions
    response = supabase_client.table("model_predictions_audit").select("*").limit(1).execute()
    print(f"Last prediction: {response.data}")
else:
    print("Supabase not connected - check environment variables")
```

#### 2. Test Model Training

```python
from skincarelib.ml_system.ml_feedback_model import (
    LogisticRegressionFeedback,
    RandomForestFeedback,
    UserState,
)
import numpy as np

# Create user state with data
user = UserState(dim=534)
for i in range(20):
    user.add_liked(np.random.randn(534).astype(np.float32))
    user.add_disliked(np.random.randn(534).astype(np.float32))

# Train models
models = [
    ("LR", LogisticRegressionFeedback()),
    ("RF", RandomForestFeedback()),
]

for name, model in models:
    success = model.fit(user)
    print(f"{name}: {success}")
    
    if success:
        score = model.predict_preference(np.random.randn(534).astype(np.float32))
        print(f"  → Score: {score:.2f}")
```

#### 3. Test Prediction Logging

```python
from deployment.api.app import log_prediction_to_supabase

success = log_prediction_to_supabase(
    user_id="test-user-001",
    product_id=123,
    predicted_score=0.75,
    actual_reaction="like",
    model_version="RandomForest (Mid Stage)",
)

print(f"Logged: {success}")
```

#### 4. Test API Endpoints

```bash
# Get model metrics
curl http://localhost:8000/api/ml/model-metrics | jq

# Compare models
curl http://localhost:8000/api/ml/compare-models | jq

# Expected output:
# {
#   "all_metrics": {
#     "LogisticRegression": {"accuracy": 0.65, "total_predictions": 100, ...},
#     "RandomForest": {"accuracy": 0.68, ...},
#     ...
#   },
#   "ranked_models": [...],
#   "best_model": {...}
# }
```

## Data Flow: A Complete User Journey

### Flow 1: User Onboarding

```
User fills form: "skin_type: oily, concerns: [acne, oiliness]"
         ↓
/api/onboarding endpoint
         ↓
_seed_user_model_from_onboarding()
         ↓
Match products with user preferences
         ↓
Add pseudo-likes/dislikes to UserState
         ↓
User seeded with initial training data ✓
```

### Flow 2: Get Recommendations

```
User requests: GET /api/recommendations/user123
         ↓
Load UserState (if not cached)
         ↓
get_best_model(user_state) → Selects model based on interactions
         ↓
For each candidate product:
  - Calculate ML score + signal score
  - Create recommendation object
         ↓
For each recommendation:
  - log_prediction_to_supabase() ← Logs prediction
  - Return to frontend
         ↓
Frontend displays recommendations ✓
```

### Flow 3: User Swipes

```
User swipes: POST /api/swipe
         ↓
SwipeEvent created, stored in DB
         ↓
User submits questionnaire: POST /api/swipe/{event_id}/questionnaire
         ↓
FeedbackRequest created
         ↓
UserState updated with actual reaction (like/dislike/irritation)
         ↓
log_prediction_to_supabase() ← Logs actual reaction
         ↓
Model learns from feedback ✓
```

### Flow 4: Monitor Model Performance

```
curl /api/ml/model-metrics
         ↓
get_model_metrics_from_supabase()
         ↓
Query model_predictions_audit:
  - Group by model_version
  - Calculate accuracy = is_correct / total
  - Return metrics
         ↓
Frontend displays model comparison dashboard ✓
```

## Frontend Integration

### API Methods Available

```typescript
// Now available in frontend/src/lib/api.ts

// Get metrics for all models
getMLModelMetrics(): Promise<MLMetrics>
// Returns: { modelName: { accuracy, total_predictions, correct } }

// Compare models with ranking
compareMLModels(): Promise<ModelComparison>
// Returns: { ranked_models, best_model, summary }
```

### Usage in Components

```typescript
import { getMLModelMetrics, compareMLModels } from "@/lib/api";

export function MLDashboard() {
  const [metrics, setMetrics] = useState<MLMetrics>({});
  
  useEffect(() => {
    // Fetch metrics on component mount
    getMLModelMetrics().then(setMetrics);
    
    // Refresh every 30 seconds
    const interval = setInterval(() => {
      getMLModelMetrics().then(setMetrics);
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);
  
  return (
    <div>
      <h2>Model Performance</h2>
      {Object.entries(metrics).map(([model, data]) => (
        <div key={model}>
          <p>{model}: {(data.accuracy * 100).toFixed(1)}%</p>
        </div>
      ))}
    </div>
  );
}
```

## Expected Metrics

### After 100 predictions per model:

| Model | Typical Accuracy | Predictions |
|-------|-----------------|-------------|
| LogisticRegression | 60-70% | 100 |
| RandomForest | 65-75% | 100 |
| GradientBoosting | 68-78% | 100 |
| LightGBM | 72-82% | 100 (with more data) |
| XLearn FFM | 75-85% | 100 (with < interactions) |

## Troubleshooting

### Issue: Supabase connection fails

**Error:** `Supabase not connected` or credentials missing

**Fix:**
```bash
# Verify environment variables
echo $SUPABASE_URL
echo $SUPABASE_KEY

# Restart backend
pkill -f "uvicorn deployment.api"
python -m uvicorn deployment.api:app --reload
```

### Issue: Predictions not logging

**Check:**
```bash
# View logs
tail -f backend.log | grep "log_prediction"

# Manual test
python -c "
from deployment.api.app import log_prediction_to_supabase
log_prediction_to_supabase('test-user', 1, 0.5, 'like', 'test')
"
```

### Issue: Model not selected correctly

**Debug:**
```python
from deployment.api.app import get_best_model
from skincarelib.ml_system.ml_feedback_model import UserState

user_state = UserState(dim=534)
user_state.interactions = 50

model, model_name = get_best_model(user_state)
print(f"Selected: {model_name}")  # Should be "GradientBoosting (Experienced)"
```

### Issue: Missing advanced models

**Check availability:**
```python
from skincarelib.ml_system.ml_feedback_model import (
    LIGHTGBM_AVAILABLE,
    XLEARN_AVAILABLE,
)

print(f"LightGBM: {LIGHTGBM_AVAILABLE}")  # Should be True if installed
print(f"XLearn: {XLEARN_AVAILABLE}")      # Should be True if installed
```

**Install:**
```bash
pip install lightgbm xlearn --no-cache-dir
```

## Performance Optimization

### For Production:

1. **Enable model caching:**
   ```python
   # In get_best_model(), cache the selected model
   MODEL_CACHE = {}
   ```

2. **Batch prediction logging:**
   ```python
   # Collect predictions and log in batches
   PREDICTION_BATCH = []
   ```

3. **Monitor query performance:**
   ```sql
   -- Add index on model_predictions_audit for faster queries
   CREATE INDEX idx_model_predictions_user ON model_predictions_audit(user_id);
   CREATE INDEX idx_model_predictions_model ON model_predictions_audit(model_version);
   ```

4. **Cache metrics:**
   ```python
   # Cache metrics for 5 minutes to reduce DB load
   from functools import lru_cache
   import time
   
   @lru_cache(maxsize=1)
   def get_cached_metrics():
       return get_model_metrics_from_supabase()
   ```

## Next Steps

1. ✅ Run `python scripts/check_ml_integration.py`
2. ✅ Verify Supabase tables exist
3. ✅ Test API endpoints with curl
4. ✅ Monitor real user data flowing through system
5. ✅ Run A/B test with different models
6. ✅ Implement feature engineering improvements

## References

- [ML Model Architecture](./ML_SYSTEM_ARCHITECTURE.md)
- [Advanced Models Setup](./ADVANCED_MODELS_SETUP.md)
- [ML Testing Guide](./ML_TESTING_GUIDE.md)
