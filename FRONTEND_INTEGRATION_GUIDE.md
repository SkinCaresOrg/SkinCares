# Frontend-Backend ML Models Integration Guide

## 🔌 API Contract

### 1. Onboarding User (Initialize ML Model)
```javascript
// POST /api/onboarding
const response = await fetch('http://localhost:8000/api/onboarding', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: 'user_123',
    skin_type: 'oily',
    concerns: ['acne', 'sensitivity']
  })
});

const data = await response.json();
// Response:
{
  "user_id": "user_123",
  "status": "onboarding_complete",
  "model_stage": "LogisticRegression (Early Stage)",
  "interactions": 0
}
```

### 2. Get Recommendations with Model Info
```javascript
// GET /api/recommendations/{user_id}
const response = await fetch('http://localhost:8000/api/recommendations/user_123');
const data = await response.json();

// Response:
{
  "recommendations": [
    {
      "product_id": "101",
      "name": "Hydrating Serum",
      "score": 0.89,
      "explanation": {
        "reasons": ["hydrating", "lightweight"],
        "model_confidence": 0.95
      }
    },
    // ... more products
  ],
  "model_stage": "LogisticRegression (Early Stage)",
  "interactions_count": 0,
  "next_stage_at": 5,  // Progression threshold
  "model_details": {
    "type": "LogisticRegression",
    "vectors_used": 1000,
    "training_samples": 0
  }
}
```

### 3. Submit User Feedback
```javascript
// POST /api/feedback
const response = await fetch('http://localhost:8000/api/feedback', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: 'user_123',
    product_id: '101',
    reaction: 'like',  // or 'dislike', 'irritation'
    reason_tags: ['hydrating', 'brightening']
  })
});

// Response:
{
  "status": "feedback_recorded",
  "model_updated": true,
  "new_model_stage": "LogisticRegression (Early Stage)",
  "total_interactions": 1
}
```

### 4. Get User Model Learning Progress
```javascript
// GET /api/user/{user_id}/model-progress
const response = await fetch('http://localhost:8000/api/user/user_123/model-progress');
const data = await response.json();

// Response:
{
  "user_id": "user_123",
  "total_interactions": 3,
  "current_stage": "LogisticRegression (Early Stage)",
  "stage_progress": {
    "current": "Early Stage",
    "likes": 2,
    "dislikes": 1,
    "irritations": 0,
    "interactions_until_next": 2  // 5 total needed
  },
  "model_history": [
    {
      "stage": "LogisticRegression",
      "activated_at": 0,
      "deactivated_at": 5
    }
  ]
}
```

---

## 🎯 Frontend Component Examples

### Display Model Stage
```tsx
// pages/Recommendations.tsx
import { useEffect, useState } from 'react';

export default function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState([]);
  const [modelStage, setModelStage] = useState('');
  const [interactions, setInteractions] = useState(0);

  useEffect(() => {
    const fetchRecommendations = async () => {
      const res = await fetch(`/api/recommendations/${userId}`);
      const data = await res.json();
      
      setRecommendations(data.recommendations);
      setModelStage(data.model_stage);
      setInteractions(data.interactions_count);
    };

    fetchRecommendations();
  }, []);

  return (
    <div>
      {/* Model Learning Status */}
      <div className="model-status">
        <h3>AI Learning Progress</h3>
        <p>Stage: {modelStage}</p>
        <ProgressBar 
          current={interactions} 
          max={5}  // Early stage threshold
        />
        <p className="hint">
          {interactions < 5 
            ? `Interact with ${5 - interactions} more products to unlock advanced learning`
            : `Expert mode unlocked!`
          }
        </p>
      </div>

      {/* Recommendations List */}
      <div className="recommendations">
        {recommendations.map(product => (
          <ProductCard 
            key={product.product_id}
            product={product}
            onLike={() => submitFeedback(product.product_id, 'like')}
            onDislike={() => submitFeedback(product.product_id, 'dislike')}
          />
        ))}
      </div>
    </div>
  );
}
```

### Feedback Form
```tsx
// components/ProductFeedback.tsx
import { useState } from 'react';

export default function ProductFeedback({ productId, userId }) {
  const [selectedReason, setSelectedReason] = useState('');
  const [reaction, setReaction] = useState('');

  const handleSubmitFeedback = async () => {
    const res = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        product_id: productId,
        reaction: reaction,
        reason_tags: [selectedReason]
      })
    });

    const data = await res.json();
    
    // Show model update to user
    if (data.model_updated) {
      showNotification(`Model progressed: ${data.new_model_stage}`);
    }
  };

  return (
    <div className="feedback-form">
      <button onClick={() => setReaction('like')}>👍 Love It</button>
      <button onClick={() => setReaction('dislike')}>👎 Not Now</button>
      <button onClick={() => setReaction('irritation')}>⚠️ Causes Issues</button>
      
      <select value={selectedReason} onChange={(e) => setSelectedReason(e.target.value)}>
        <option value="">Select reason...</option>
        <option value="hydrating">Hydrating</option>
        <option value="lightweight">Lightweight</option>
        <option value="affordable">Affordable</option>
      </select>

      <button onClick={handleSubmitFeedback}>Submit Feedback</button>
    </div>
  );
}
```

### Model Stage Visual
```tsx
// components/ModelStageIndicator.tsx
export default function ModelStageIndicator({ stage, interactions }) {
  const stages = [
    { name: 'Early', min: 0, max: 5, model: 'LogisticRegression', emoji: '🌱' },
    { name: 'Learning', min: 5, max: 20, model: 'RandomForest', emoji: '🌿' },
    { name: 'Advanced', min: 20, max: 50, model: 'LightGBM', emoji: '🌳' },
    { name: 'Expert', min: 50, max: Infinity, model: 'ContextualBandit', emoji: '🌲' }
  ];

  return (
    <div className="stage-indicator">
      {stages.map(s => (
        <div 
          key={s.name}
          className={`stage ${interactions >= s.min ? 'active' : 'inactive'}`}
        >
          <span>{s.emoji} {s.name}</span>
          <small>{s.model}</small>
        </div>
      ))}
      
      <div className="progress">
        <div className="bar" style={{ 
          width: `${Math.min(interactions / 50 * 100, 100)}%` 
        }} />
      </div>
    </div>
  );
}
```

---

## 🗄️ Supabase Integration

### Frontend Connection (if needed)
```javascript
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js';

export const supabase = createClient(
  process.env.REACT_APP_SUPABASE_URL,
  process.env.REACT_APP_SUPABASE_ANON_KEY
);

// Fetch user's model progression from DB
export async function getUserModelProgress(userId) {
  const { data, error } = await supabase
    .from('user_model_state')
    .select('*')
    .eq('user_id', userId)
    .single();

  if (error) throw error;
  return data;
}
```

### Backend Supabase Connection
The backend already handles this via 3-tier fallback:
```python
# deployment/api/app.py

# 1. PostgreSQL (production)
try:
    conn = psycopg.connect(DATABASE_URL)
except:
    # 2. Supabase REST API
    try:
        response = requests.post(SUPABASE_REST_ENDPOINT, ...)
    except:
        # 3. In-memory storage (always works)
        USER_STATES[user_id] = UserState(...)
```

---

## ✅ Integration Checklist

- [ ] Frontend calls `/api/onboarding` on sign-up
- [ ] Frontend displays model stage from `/api/recommendations` response
- [ ] Frontend submits feedback to `/api/feedback` after user interaction
- [ ] Feedback form includes reason tags
- [ ] Model progression displayed as visual indicator
- [ ] Supabase data syncs (optional, backend handles it)
- [ ] Error handling for API failures (fallback to recommendations)
- [ ] Loading states while fetching recommendations

---

## 🧪 Testing the Integration

### Manual Test Flow
```bash
# 1. Start backend
cd /Users/geethika/projects/SkinCares/SkinCares
python -m uvicorn deployment.api.app:app --reload

# 2. Start frontend
cd frontend
npm run dev

# 3. Navigate to http://localhost:8080
# 4. Register/Login
# 5. Complete onboarding
# 6. Check recommendations page shows model stage
# 7. Click like/dislike
# 8. Verify feedback submitted
# 9. Check model stage updates after 5 interactions
```

### API Testing with cURL
```bash
# Create user
curl -X POST http://localhost:8000/api/onboarding \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test_user","skin_type":"oily","concerns":["acne"]}'

# Get recommendations (with model info)
curl http://localhost:8000/api/recommendations/test_user

# Submit feedback
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test_user","product_id":"0","reaction":"like","reason_tags":["hydrating"]}'

# Check progress
curl http://localhost:8000/api/user/test_user/model-progress
```

---

## 🚀 Deployment URLs

### Development
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:8080`
- Supabase: Local or dev project

### Staging
- Backend: `https://staging-api.skincares.app`
- Frontend: `https://staging.skincares.app`
- Supabase: Staging database

### Production
- Backend: `https://api.skincares.app`
- Frontend: `https://skincares.app`
- Supabase: Production database
