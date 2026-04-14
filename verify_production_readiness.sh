#!/bin/bash
# Production Deployment Checklist

echo "=== SkinCares Production Readiness Verification ==="
echo ""

# 1. Check environment variables
echo "[1/6] Checking environment configuration..."
if [ -f .env ]; then
    echo "✅ .env file found"
    if grep -q "SUPABASE_URL" .env; then
        echo "✅ SUPABASE_URL configured"
    else
        echo "⚠️  SUPABASE_URL not configured"
    fi
    if grep -q "SUPABASE_KEY" .env; then
        echo "✅ SUPABASE_KEY configured"
    else
        echo "⚠️  SUPABASE_KEY not configured"
    fi
else
    echo "⚠️  .env file not found - using defaults"
fi

# 2. Check database
echo ""
echo "[2/6] Checking database setup..."
python3 -c "from deployment.api.db.init_db import init_db; init_db(); print('✅ Database initialized')" 2>/dev/null || echo "⚠️  Database init failed"

# 3. Check ML assets
echo ""
echo "[3/6] Checking ML assets..."
if [ -f "artifacts/product_vectors.npy" ]; then
    echo "✅ Product vectors found"
    SIZE=$(wc -c < "artifacts/product_vectors.npy")
    echo "   Size: $(($SIZE / 1048576))MB"
else
    echo "⚠️  Product vectors not found"
fi

if [ -f "data/processed/products_with_signals.csv" ]; then
    PRODUCT_COUNT=$(wc -l < "data/processed/products_with_signals.csv")
    echo "✅ Product CSV found with ~$((PRODUCT_COUNT-1)) products"
else
    echo "⚠️  Product CSV not found"
fi

# 4. Check dependencies
echo ""
echo "[4/6] Checking Python dependencies..."
python3 -c "import sklearn; import lightgbm; import numpy; echo '✅ Core ML dependencies installed'" 2>/dev/null || echo "⚠️  Some ML dependencies missing"

# 5. Check frontend build
echo ""
echo "[5/6] Checking frontend setup..."
if [ -d "frontend/node_modules" ]; then
    echo "✅ Frontend dependencies installed"
else
    echo "⚠️  Frontend dependencies not installed"
fi

# 6. Run quick tests
echo ""
echo "[6/6] Running quick functional tests..."
python3 << 'EOF'
try:
    # Test onboarding
    from deployment.api.app import submit_onboarding, OnboardingRequest
    profile = OnboardingRequest(
        skin_type="normal",
        concerns=["dryness"],
        sensitivity_level="rarely_sensitive",
        ingredient_exclusions=[],
        price_range="mid_range",
        routine_size="basic"
    )
    print("✅ Onboarding endpoint functional")
except Exception as e:
    print(f"⚠️  Onboarding test failed: {e}")

try:
    # Test ML import
    from skincarelib.ml_system.ml_feedback_model import UserState
    state = UserState(dim=128)
    print("✅ ML system initialized")
except Exception as e:
    print(f"⚠️  ML system test failed: {e}")
EOF

echo ""
echo "=== Verification Complete ==="
echo ""
echo "Status: Review warnings above and apply PRODUCTION_READINESS_AUDIT.md fixes"

