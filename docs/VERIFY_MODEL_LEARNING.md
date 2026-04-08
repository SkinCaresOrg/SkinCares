# Verifying ML Model Learning While Swiping

This guide explains how to verify that your ML models are actually learning when you interact with the app.

## 🚀 Quick Start

1. **Start both servers**:
   ```bash
   # Terminal 1: Backend API
   cd /Users/geethika/projects/SkinCares/SkinCares
   source .venv/bin/activate
   python -m uvicorn deployment.api.app:app --reload --port 8000

   # Terminal 2: Frontend
   cd /Users/geethika/projects/SkinCares/SkinCares/frontend
   npm run dev
   ```

2. **Open the app**: http://localhost:8080/

3. **Complete onboarding** to create a user profile

## 📊 Verify Model Learning in Real-Time

### Method 1: Debug Panel (Easiest)

After onboarding, go to **Recommendations** page:

1. Click **"Show model debug info"** button
2. You'll see a yellow panel showing:
   - **Total Interactions**: How many products you've rated
   - **Liked**: Products marked as liked
   - **Disliked**: Products marked as dislike
   - **Model Ready**: ✓ when you have both likes AND dislikes

3. The debug panel states:
   - ❌ "Need more feedback..." → Model not ready yet (need at least 1 like + 1 dislike)
   - ✅ "Model is learning!" → Model is now personalizing recommendations

### Method 2: ML Score Badges

When the model is ready (✓ Model Ready in debug panel):

1. Each product card shows a **blue percentage badge** in the top-right corner
2. This is the ML model's confidence score (0-100%)
   - **High score (70-99%)**: Model thinks you'll like it
   - **Medium score (40-60%)**: Model is unsure
   - **Low score (10-30%)**: Model thinks you might dislike it

### Method 3: Score Changes Over Time

Watch how scores evolve as you swipe:

**Before swiping any products:**
- All scores = 50% (neutral)
- Product order is random

**After 1-2 swipes:**
- Scores still 50% (not enough data)
- Debug panel shows: "Need more feedback..."

**After 3+ swipes (at least 1 like + 1 dislike):**
- ✅ Model Ready = true
- Scores are **personalized** and vary
- Products are **reordered** based on your preferences

## 🔍 Advanced Debugging

### API Endpoints for Inspection

If you want to check model state programmatically:

```bash
# Get user's model state
curl http://localhost:8000/api/debug/user-state/user_1 | jq .

# Response:
{
  "user_id": "user_1",
  "interactions": 5,
  "liked_count": 3,
  "disliked_count": 2,
  "irritation_count": 0,
  "has_training_data": true,
  "model_ready": true
}

# Get score for specific product
curl http://localhost:8000/api/debug/product-score/user_1/42 | jq .

# Response:
{
  "product_id": 42,
  "product_name": "Hydrating Moisturizer",
  "score": 0.87,
  "interpretation": "Likely match",
  "model_state": {
    "interactions": 5,
    "liked": 3,
    "disliked": 2
  }
}
```

### Browser Console Logging

Open Developer Tools (F12) and check:

1. **Network tab**: Watch API calls for `/api/recommendations`
   - Scores should change as you provide feedback

2. **Console tab**: Check for any errors (red messages)

## ✅ What Should Happen

### Flow: User Interaction → Model Learning → Personalized Results

**Step 1: Onboard User**
```
User enters: skin_type="dry", concerns=["dryness"]
→ Creates user profile
→ Model initialized with empty state
```

**Step 2: Swipe Products (Go to Swiping page)**
```
Swipe 1 (Like): Product A
Swipe 2 (Dislike): Product B
Swipe 3 (Like): Product C
→ Model receives 3 interactions
→ Learns: A and C are good, B is bad
```

**Step 3: Check Recommendations**
```
Go back to Recommendations
→ Click "Show model debug info"
→ See:
   - Interactions: 3
   - Liked: 2
   - Disliked: 1
   - Model Ready: ✓
→ Products now have ML scores (70%, 45%, 82%, etc.)
```

## 🎯 Expected Behavior

| Stage | Interactions | Model Ready | Scores | Behavior |
|-------|--------------|-------------|--------|----------|
| Start | 0 | ✗ | All 50% | Random order |
| After 1-2 | 1-2 | ✗ | All 50% | Model gathering data |
| After 3+ | 3+ | ✓ | 20-90% | Personalized ranking |
| After 10+ | 10+ | ✓ | More spread | Strong preferences learned |

## 🚨 Troubleshooting

### Problem: Scores always stay at 50%
- ✅ **Solution**: Make sure `Model Ready: ✓` in debug panel
- Swipe at least 2 products with different reactions (like vs dislike)

### Problem: Debug panel not showing
- ✅ **Solution**: Refresh the page after swiping
- Go to Recommendations page and click "Show model debug info"

### Problem: Backend not responding
- ✅ **Solution**: Check if backend is running
- Run: `curl http://localhost:8000/api/debug/user-state/user_1`
- Should return JSON (not error)

### Problem: Scores don't change after new swipes
- ✅ **Solution**: Refresh page to reload recommendations
- Models recompute scores on each page load

## 📈 Success Criteria

Your ML integration is working if you see:

1. ✅ Debug panel shows increasing interaction count as you swipe
2. ✅ After 3+ swipes with both likes and dislikes, Model Ready = ✓
3. ✅ Product scores change (no longer all 50%)
4. ✅ Scores reflect your preferences (liked products get higher scores)
5. ✅ Going to Swiping page, swiping more products, then returning to Recommendations shows updated scores

## 🧪 Test Script (Run in Terminal)

To verify end-to-end integration without using the frontend:

```bash
cd /Users/geethika/projects/SkinCares/SkinCares
source .venv/bin/activate
python examples/test_api_ml_integration.py
```

This runs the same verification we did during integration testing.

---

**Summary**: The model is learning when:
1. You see increasing numbers in the debug panel
2. `Model Ready` changes from ✗ to ✓
3. Product scores vary instead of all being 50%
4. Products are reordered based on your feedback history
