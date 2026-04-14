# ML Models Production Readiness Guide

## ✅ Current Status

**Models**: 4/4 working with real product data
**Backend**: Fully optimized with LightGBM + XLearn support
**Vectors**: 50,305 real embeddings (256-dim from FAISS)
**Tests**: 113/115 passing

---

## 🔗 Frontend Integration Checklist

### 1. **API Endpoints Ready**
- ✅ `/api/recommendations/{user_id}` - Get recommendations with model stage info
- ✅ `/api/onboarding` - Create user profile & initial model state
- ✅ `/api/feedback` - Submit user feedback (like/dislike/irritation)
- ✅ `/api/products` - List products

**Action**: Update frontend API client to include model stage in response:
```javascript
// Example response from /api/recommendations
{
  "recommendations": [...],
  "model_stage": "LogisticRegression (Early Stage)",  // ← Include this
  "explanation": {
    "reasons": ["ingredient_A", "ingredient_B"]
  }
}
```

### 2. **Frontend UI Components**
**Needed**: Display model learning stage & confidence

```tsx
// Components/ModelLearningStatus.tsx
<div>
  <p>Learning Stage: {modelStage}</p>
  <progress value={interactions} max={100} />
</div>
```

**Progression Display**:
- 0-5: "Early learning" (LogisticRegression)
- 5-20: "Learning patterns" (RandomForest)
- 20-50: "Understanding preferences" (LightGBM)
- 50-100: "Advanced learning" (XLearn fallback)
- 100+: "Expert mode" (ContextualBandit)

### 3. **Real-time Feedback Loop**
```javascript
// When user likes/dislikes a product
POST /api/feedback {
  user_id: "...",
  product_id: "...",
  reaction: "like" | "dislike" | "irritation",
  reason_tags: ["hydrating", "lightweight", ...]
}
```

---

## 🗄️ Supabase Integration Checklist

### 1. **Database Schema (Already exists)**
```sql
-- Verify these tables exist:
CREATE TABLE user_profile_state (user_id, skin_type, concerns, ...)
CREATE TABLE user_model_state (user_id, model_type, interactions, ...)
CREATE TABLE user_product_event (user_id, product_id, reaction, timestamp, ...)
CREATE TABLE user_recommendation_log (user_id, product_ids, model_stage, ...)
```

**Action**: Run verification query:
```bash
curl -X GET "https://YOUR_PROJECT.supabase.co/rest/v1/user_profile_state" \
  -H "apikey: YOUR_ANON_KEY"
```

### 2. **Environment Variables**
```bash
# .env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_KEY=YOUR_SERVICE_KEY

# Backend should connect via:
# - Primary: Direct PostgreSQL (production)
# - Fallback 1: Supabase REST API
# - Fallback 2: In-memory state (local dev)
```

### 3. **Persistence Strategy**
Backend has 3-tier fallback:
```python
# deployment/api/app.py
# 1. Try PostgreSQL connection
# 2. Try Supabase REST API 
# 3. Use in-memory storage
```

**Verify persistence**:
```bash
# Create user via backend
curl -X POST "http://localhost:8000/api/onboarding" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'

# Check Supabase for saved data
SELECT * FROM user_profile_state WHERE user_id = 'test_user';
```

### 4. **Data Sync on Deployment**
Before deploying:
```bash
# Run this to ensure fresh data
python scripts/verify_manifest.py
python tests/test_supabase_connection.py
```

---

## 🚀 Deployment Checklist

### Phase 1: Pre-Deployment (Local Testing)
- [ ] All models tested with real product data
- [ ] 113+ unit tests passing
- [ ] Frontend displays model stage
- [ ] Supabase connection verified
- [ ] Environment variables configured
- [ ] Product vectors extracted (`extract_product_vectors.py`)

**Commands**:
```bash
python extract_product_vectors.py           # Generate real vectors
python test_models_validation.py             # Validate all models
pytest tests/test_ml_feedback_models.py -v  # Run ML tests
```

### Phase 2: Staging Deployment
- [ ] Deploy backend to staging
- [ ] Deploy frontend to staging
- [ ] Connect to Supabase
- [ ] Test full user journey: Registration → Onboarding → Recommendations → Feedback

**Staging URL**: `https://staging-skincares.vercel.app`

### Phase 3: Production Deployment
- [ ] Backend on production domain (e.g., `api.skincares.app`)
- [ ] Frontend on production domain (e.g., `skincares.app`)
- [ ] Supabase production database
- [ ] Monitoring & logging enabled

---

## 🧪 Testing Procedures

### 1. **End-to-End Test Script**
```bash
#!/bin/bash

# Start backend
python -m uvicorn deployment.api.app:app --reload &
BACKEND_PID=$!

# Start frontend
cd frontend && npm run dev &
FRONTEND_PID=$!

# Wait and test
sleep 5

# Test API
curl -X POST http://localhost:8000/api/onboarding \
  -d '{"user_id": "test_e2e"}' 

# Test recommendations (should use real vectors)
curl http://localhost:8000/api/recommendations/test_e2e

# Test feedback loop
curl -X POST http://localhost:8000/api/feedback \
  -d '{"user_id": "test_e2e", "product_id": "0", "reaction": "like"}'

# Cleanup
kill $BACKEND_PID $FRONTEND_PID
```

### 2. **Model Learning Verification**
```bash
python << 'EOF'
from deployment.api.app import get_best_model
from skincarelib.ml_system.ml_feedback_model import UserState, PRODUCT_VECTORS

# Simulate user progression
for stage in [0, 5, 15, 25, 75, 150]:
    user = UserState(PRODUCT_VECTORS.shape[1])
    user.interactions = stage
    model, name = get_best_model(user)
    print(f"Stage {stage}: {name}")
EOF
```

### 3. **Supabase Persistence Test**
```bash
# Test that user data persists in Supabase
TEST_USER="test_$(date +%s)"

# Create user
curl -X POST http://localhost:8000/api/onboarding \
  -d "{\"user_id\": \"$TEST_USER\"}"

# Verify in Supabase
curl -X GET "https://YOUR_PROJECT.supabase.co/rest/v1/user_profile_state?user_id=eq.$TEST_USER" \
  -H "apikey: YOUR_ANON_KEY"
```

---

## 📊 Monitoring Metrics

### Backend Metrics to Track
```
1. Model selection distribution (how many users at each stage)
2. Average recommendation response time (<100ms target)
3. Feedback submission success rate (>99%)
4. Database connection uptime (>99.9%)
```

### Frontend Metrics to Track
```
1. Model stage display accuracy
2. Recommendation click-through rate
3. Feedback form submission completion
4. Page load time with model info
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow
```yaml
# .github/workflows/production.yml
on: [push to main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run ML tests
        run: pytest tests/test_ml_feedback_models.py -v
      - name: Validate vectors
        run: python check_vectors.py
        
  deploy:
    needs: test
    steps:
      - name: Deploy backend
        run: ...
      - name: Deploy frontend
        run: ...
```

---

## 🆘 Troubleshooting

### Issue: "Product vectors not found"
**Solution**: Run extraction script
```bash
python extract_product_vectors.py
```

### Issue: Models slow (>1s response)
**Solution**: Check product sampling
```python
# In app.py, verify sampling is working
# Max 1000 products sampled per request
```

### Issue: Supabase connection failing
**Solution**: Check fallback chain
```bash
# Backend will use in-memory state if DB fails
# Check logs for which tier is being used
```

---

## ✨ Next Steps to Production

1. **Immediate** (This week)
   - [ ] Frontend displays model stage info
   - [ ] Run full integration test
   - [ ] Verify Supabase data persistence

2. **Short-term** (Week 2)
   - [ ] Set up monitoring dashboards
   - [ ] Configure staging environment
   - [ ] Load test with 1000+ concurrent users

3. **Production** (Week 3)
   - [ ] Deploy to production
   - [ ] Enable CloudFlare caching
   - [ ] Monitor real user feedback

---

## 📞 Support

**Issues with models?** Run diagnostics:
```bash
python test_models_validation.py
python check_vectors.py
pytest tests/test_ml_feedback_models.py -v
```

**Need to rebuild vectors?**
```bash
python extract_product_vectors.py
```

**Check backend health:**
```bash
curl http://localhost:8000/api/health
```
