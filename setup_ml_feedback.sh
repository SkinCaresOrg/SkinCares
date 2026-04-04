#!/bin/bash
# Install and quick test script

echo "================================================"
echo "SkinCares ML Feedback Models - Setup"
echo "================================================"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -e '.[dev]'

echo ""
echo "================================================"
echo "Running Tests"
echo "================================================"
python -m pytest tests/test_ml_feedback_models.py -v --tb=short

echo ""
echo "================================================"
echo "Testing Single Model"
echo "================================================"
python examples/ml_feedback_demo.py --model logistic 2>&1 | head -30

echo ""
echo "================================================"
echo "✅ Setup Complete!"
echo "================================================"
echo ""
echo "To use ML feedback models:"
echo ""
echo "  source venv/bin/activate"
echo ""
echo "  # Run simulation with ML model"
echo "  python -m skincarelib.ml_system.simulation --model random_forest"
echo ""
echo "  # Compare all models"
echo "  python -m skincarelib.ml_system.simulation --compare"
echo ""
echo "  # Run demo"
echo "  python examples/ml_feedback_demo.py --compare"
echo ""
echo "To use in Python:"
echo ""
echo "  from skincarelib.ml_system.integration import recommend_with_feedback"
echo ""
echo "  recommendations = recommend_with_feedback("
echo "      user_state=user,"
echo "      metadata_df=products,"
echo "      tokens_df=tokens,"
echo "      constraints={},"
echo "      model_type='logistic'  # or random_forest, gradient_boosting, contextual_bandit"
echo "  )"
echo ""
echo "See QUICK_START.md for more examples"
echo ""
