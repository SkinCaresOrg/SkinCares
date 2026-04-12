# Local Development Setup & Testing Guide

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend)
- Bun package manager (optional, but recommended for speed)

### Setup Environment

#### 1. Backend Setup

```bash
# Navigate to project root
cd /Users/geethika/projects/SkinCares/SkinCares

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

#### 2. Frontend Setup

```bash
cd frontend

# Using npm
npm install

# OR using bun (faster)
bun install

# Verify installation
npm --version
node --version
```

---

## Running the Application

### Option A: Run Backend and Frontend Separately

#### Terminal 1 - Backend API Server

```bash
cd /Users/geethika/projects/SkinCares/SkinCares
source .venv/bin/activate

# Run the API server on port 8000
python3 -m uvicorn deployment.api.app:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

#### Terminal 2 - Frontend Development Server

```bash
cd /Users/geethika/projects/SkinCares/SkinCares/frontend
source ../.venv/bin/activate  # Use same venv

# Start the dev server
npm run dev
# OR with bun
bun run dev
```

**Expected Output:**
```
VITE v5.0.0  ready in 123 ms

➜  Local:   http://localhost:8080/
```

#### Access the Application

Open your browser and navigate to:
- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- API Docs (Swagger UI): http://localhost:8000/docs

---

### Option B: Run with Docker Compose

```bash
# From project root
docker-compose up --build

# Containers will start:
# - API on http://localhost:8000
# - Frontend on http://localhost:8080
```

---

## Testing the API Response

### Test 1: Quick Browser Test

1. Open http://localhost:8080 in your browser
2. Press `F12` to open Developer Tools
3. Go to Console tab
4. Paste the code from `BROWSER_CONSOLE_TEST.js`:

```javascript
// Copy from BROWSER_CONSOLE_TEST.js and paste here
```

### Test 2: Python Verification

```bash
source .venv/bin/activate
python3 verify_api_response.py
```

Expected output:
```
✓ API response format verification complete!
```

### Test 3: Direct cURL Test

```bash
# Get first 5 products
curl "http://localhost:8000/api/products?page=1&limit=5" | jq .

# Search for specific product
curl "http://localhost:8000/api/products?search=moisturizer&limit=10" | jq .

# Filter by price
curl "http://localhost:8000/api/products?min_price=20&max_price=50" | jq .
```

### Test 4: Frontend Network Tab

1. Open http://localhost:8080
2. Press `F12` and go to "Network" tab
3. Filter for XHR requests
4. Trigger a product fetch (scroll, search, filter)
5. Click the `/api/products` request
6. Go to "Response" tab to see the full JSON

---

## Debugging

### Enable Backend Logging

Add logging to the API:

```python
# In deployment/api/app.py
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.get("/api/products")
def list_products(...):
    logger.debug(f"Received request: category={category}, search={search}")
    # ... rest of function
    logger.debug(f"Returning {len(paged)} products")
    return response
```

### Frontend Console Logging

Add debugging to the API client:

```typescript
// In frontend/src/lib/api.ts
export async function getProducts(params?: {}): Promise<...> {
  console.log('getProducts called with:', params);
  try {
    const result = await fetchApi<...>(`/products${qs ? `?${qs}` : ""}`);
    console.log('getProducts response:', result);
    return result;
  } catch (error) {
    console.error('getProducts error:', error);
    throw error;
  }
}
```

### Network Debugging

Monitor all API requests:

```javascript
// Add to browser console
const originalFetch = window.fetch;
window.fetch = function(...args) {
  console.log('FETCH:', args[0], args[1]);
  return originalFetch.apply(this, args)
    .then(response => {
      console.log('RESPONSE:', response.status, response.statusText);
      return response;
    })
    .catch(error => {
      console.error('FETCH ERROR:', error);
      throw error;
    });
};
```

---

## Common Issues & Solutions

### Issue: "Cannot find module 'sqlalchemy'"

**Solution:**
```bash
source .venv/bin/activate
pip install sqlalchemy pydantic fastapi uvicorn
```

### Issue: Port 8000 already in use

**Solution:**
```bash
# Kill process on port 8000
lsof -ti :8000 | xargs kill -9

# Or use different port
python3 -m uvicorn deployment.api.app:app --port 8001
```

### Issue: CORS errors in browser

**Solution:**
Check if CORS middleware is enabled in `deployment/api/app.py`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Frontend can't reach API

**Check:**
1. Is backend running? `curl http://localhost:8000/api/products`
2. Is vite proxy correct? Check `frontend/vite.config.ts`
3. Is `VITE_API_BASE_URL` set correctly? Check `.env` files

### Issue: Products not loading in frontend

**Debug:**
1. Open browser Dev Tools (F12)
2. Check Console tab for errors
3. Check Network tab for failed requests
4. Look for 404, 500, or CORS errors
5. Run `python3 verify_api_response.py` to check backend

---

## Production Simulation

### Run Production Build

```bash
# Frontend production build
cd frontend
npm run build
npm run preview

# Backend production mode
cd ..
source .venv/bin/activate
python3 -m uvicorn deployment.api.app:app --host 0.0.0.0 --port 8000
```

### Load Testing

```bash
# Install Apache Bench
# macOS: brew install httpd
# Linux: sudo apt-get install apache2-utils

# Test API performance
ab -n 100 -c 10 http://localhost:8000/api/products?page=1&limit=20

# Test with different parameters
ab -n 1000 -c 50 http://localhost:8000/api/products?search=moisturizer
```

---

## Useful Development Commands

### Frontend

```bash
cd frontend

# Development
npm run dev          # Start dev server with hot reload

# Production
npm run build        # Build for production
npm run preview      # Preview production build locally
npm run lint         # Run ESLint
npm run format       # Format code with Prettier

# Testing
npm run test         # Run Vitest tests
npm run test:ui      # Run tests with UI
```

### Backend

```bash
# Development
python3 -m uvicorn deployment.api.app:app --reload

# Formatting & Linting
ruff format .        # Format with Ruff
ruff check .         # Lint with Ruff
ruff check --fix .   # Auto-fix issues

# Testing
pytest tests/        # Run tests
pytest -v tests/     # Verbose output
pytest --cov         # With coverage report
```

---

## Performance Monitoring

### Check API Performance

```bash
# Time a single request
time curl "http://localhost:8000/api/products?page=1&limit=20"

# Monitor with watch
watch -n 1 'curl -s http://localhost:8000/api/products?page=1&limit=5 | jq .total'
```

### Monitor Memory Usage

```bash
# Backend
ps aux | grep uvicorn
# Look at %MEM column

# Frontend (Node)
ps aux | grep node
```

### Check Vite Build Performance

```bash
cd frontend
npm run build -- --profile

# Results will show in terminal
```

---

## Tips & Tricks

### Use jq for JSON Pretty-Printing

```bash
# Install jq (macOS)
brew install jq

# Pretty print JSON responses
curl "http://localhost:8000/api/products?limit=1" | jq .
curl "http://localhost:8000/api/products?limit=1" | jq '.items[0]'
curl "http://localhost:8000/api/products?limit=1" | jq '.items[0] | {product_id, product_name, price}'
```

### Watch File Changes (with auto-reload)

```bash
# Backend - already has --reload with uvicorn
python3 -m uvicorn deployment.api.app:app --reload

# Frontend - already has HMR with npm run dev
npm run dev
```

### Test Multiple Queries

```bash
# Create a batch of test requests
for page in {1..5}; do
  echo "Page $page:"
  curl -s "http://localhost:8000/api/products?page=$page&limit=5" | jq '.total'
done
```

---

## Environment Variables

### Backend (.env)

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true

# Database
DATABASE_URL=postgresql://user:password@localhost/skincares

# CSV Path
PRODUCTS_CSV_PATH=data/processed/products_dataset_processed.csv
```

### Frontend (.env.development)

```bash
# API Configuration
VITE_API_BASE_URL=/api  # Uses Vite proxy in dev mode
```

### Frontend (.env.production)

```bash
# API Configuration
VITE_API_BASE_URL=https://api.example.com/api
```

---

## Troubleshooting Resources

- **API Issues**: See [API_RESPONSE_FORMAT.md](./API_RESPONSE_FORMAT.md)
- **Frontend Issues**: Check `frontend/src/lib/api.ts` and `frontend/src/pages/Catalog.tsx`
- **Backend Issues**: Check `deployment/api/app.py`
- **Browser Console**: Press F12 and look for red error messages

---

## Support

For specific issues, check:
1. Browser Console (F12)
2. Network Tab (check failed requests)
3. Run verification script: `python3 verify_api_response.py`
4. Run browser console test (see above)
5. Check logs from backend terminal
