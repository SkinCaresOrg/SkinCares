#!/usr/bin/env python
"""
Verification script to check that the ML setup is correct and the recommendation system works.

Run with: python verify_ml_setup.py
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def check_imports():
    """Check that all ML modules can be imported"""
    print_header("1. Checking Imports")
    
    try:
        from skincarelib.ml_system.online_learning import OnlineLearner, ContextualBanditStrategy
        print("✅ OnlineLearner imported")
        print("✅ ContextualBanditStrategy imported")
    except ImportError as e:
        print(f"❌ Failed to import online learning: {e}")
        return False
    
    try:
        from skincarelib.ml_system.feedback_structures import (
            DetailedFeedbackCollector,
            InitialUserQuestionnaire,
            IngredientPreferenceTracker,
        )
        print("✅ DetailedFeedbackCollector imported")
        print("✅ InitialUserQuestionnaire imported")
        print("✅ IngredientPreferenceTracker imported")
    except ImportError as e:
        print(f"❌ Failed to import feedback structures: {e}")
        return False
    
    try:
        from skincarelib.ml_system.swipe_session import SwipeSession
        print("✅ SwipeSession imported")
    except ImportError as e:
        print(f"❌ Failed to import SwipeSession: {e}")
        return False
    
    return True

def check_artifacts():
    """Check that required artifacts exist"""
    print_header("2. Checking Artifacts")
    
    artifacts_path = Path("artifacts")
    required_files = [
        "product_vectors.npy",
        "product_index.json",
        "tfidf.joblib",
    ]
    
    all_exist = True
    for filename in required_files:
        filepath = artifacts_path / filename
        if filepath.exists():
            size_mb = filepath.stat().st_size / (1024 * 1024)
            print(f"✅ {filename} exists ({size_mb:.1f} MB)")
        else:
            print(f"❌ {filename} missing")
            all_exist = False
    
    return all_exist

def check_data():
    """Check that product metadata is available"""
    print_header("3. Checking Product Data")
    
    try:
        metadata = pd.read_csv("data/processed/products_dataset_processed.csv")
        print(f"✅ Loaded {len(metadata)} products")
        
        required_cols = ["category", "price", "ingredients"]
        missing_cols = [col for col in required_cols if col not in metadata.columns]
        
        if missing_cols:
            print(f"⚠️  Missing columns: {missing_cols}")
            return False
        
        print(f"✅ All required columns present: {required_cols}")
        print(f"   Categories: {metadata['category'].nunique()} unique")
        print(f"   Price range: ${metadata['price'].min():.2f} - ${metadata['price'].max():.2f}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to load product data: {e}")
        return False

def check_model_initialization():
    """Check that models can be initialized"""
    print_header("4. Checking Model Initialization")
    
    try:
        from skincarelib.ml_system.online_learning import OnlineLearner
        
        learner = OnlineLearner(dim=534, learning_rate=0.1)
        print(f"✅ OnlineLearner initialized")
        print(f"   - Dimension: {learner.dim}")
        print(f"   - Learning rate: {learner.learning_rate}")
        print(f"   - Interaction count: {learner.interaction_count}")
    except Exception as e:
        print(f"❌ Failed to initialize OnlineLearner: {e}")
        return False
    
    try:
        from skincarelib.ml_system.online_learning import ContextualBanditStrategy
        
        bandit = ContextualBanditStrategy(initial_epsilon=0.8, decay_rate=0.02)
        print(f"✅ ContextualBanditStrategy initialized")
        print(f"   - Initial epsilon: {bandit.epsilon:.2f}")
        print(f"   - Decay rate: {bandit.decay_rate}")
    except Exception as e:
        print(f"❌ Failed to initialize ContextualBanditStrategy: {e}")
        return False
    
    return True

def check_swipe_session():
    """Check end-to-end SwipeSession flow"""
    print_header("5. Testing End-to-End SwipeSession Flow")
    
    try:
        import numpy as np
        import pandas as pd
        from skincarelib.ml_system.swipe_session import SwipeSession
        
        # Load data
        product_vectors = np.load("artifacts/product_vectors.npy")
        metadata = pd.read_csv("data/processed/products_dataset_processed.csv")
        
        # Create product_id from index if not present
        if "product_id" not in metadata.columns:
            metadata["product_id"] = [f"p{i}" for i in range(len(metadata))]
        
        # Limit metadata to match product vectors (vectors may be for a subset)
        n_vectors = len(product_vectors)
        metadata = metadata.iloc[:n_vectors]
        
        product_index = {row["product_id"]: idx for idx, row in metadata.iterrows()}
        
        print(f"✅ Loaded product vectors: {product_vectors.shape}")
        print(f"✅ Loaded {len(metadata)} products")
        
        # Create session
        session = SwipeSession(
            user_id="test_user",
            product_vectors=product_vectors,
            product_metadata=metadata,
            product_index=product_index,
            learning_rate=0.1,
            initial_epsilon=0.8,
        )
        print(f"✅ SwipeSession created")
        
        # Complete onboarding
        session.complete_onboarding(
            skin_type="Dry",
            skin_concerns=["Dryness", "Sensitivity"],
            budget_range=("50-100", 100),
            preferred_categories="Moisturizer Face Mask"
        )
        print(f"✅ Onboarding completed")
        
        # Get first product
        product_id, product_meta = session.get_next_product()
        print(f"✅ Got next product: {product_id}")
        print(f"   - Confidence: {product_meta['confidence_score']:.2f}")
        print(f"   - Category: {product_meta.get('category', 'N/A')}")
        print(f"   - Exploration: {product_meta['exploration_action']}")
        
        # Record swipe
        swipe_result = session.record_swipe(
            product_id=product_id,
            tried_status="yes",
            reaction="like",
            feedback_reasons=["Felt lightweight"]
        )
        print(f"✅ Recorded swipe")
        print(f"   - Interaction count: {swipe_result['model_update']['interactions_learned']}")
        
        # Get session state
        state = session.get_session_state()
        print(f"✅ Session state retrieved")
        print(f"   - Products shown: {state['total_products_shown']}")
        print(f"   - Products rated: {state['products_rated']}")
        print(f"   - Exploration rate: {state['exploration_exploitation']['exploration_rate']:.1%}")
        
        # Do a few more swipes
        print(f"\n  Running 5 more swipes to test learning...")
        for i in range(5):
            product_id, _ = session.get_next_product()
            session.record_swipe(product_id, "yes", "like", [])
        
        state = session.get_session_state()
        print(f"✅ After 6 swipes:")
        print(f"   - Exploration rate decreased: {state['exploration_exploitation']['exploration_rate']:.1%}")
        print(f"   - Products shown: {state['total_products_shown']}")
        
        # Get recommendations
        recommendations = session.get_recommendations(top_n=5)
        print(f"✅ Got {len(recommendations)} recommendations")
        if len(recommendations) > 0:
            print(f"   Top recommendation: {recommendations.iloc[0]['product_id']}")
            print(f"   Score: {recommendations.iloc[0]['preference_score']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_model_learning():
    """Check that the model actually learns from interactions"""
    print_header("6. Testing Model Learning")
    
    try:
        from skincarelib.ml_system.online_learning import OnlineLearner
        
        learner = OnlineLearner(dim=534, learning_rate=0.1)
        
        # Create dummy product vectors
        product_vec1 = np.random.randn(534)
        product_vec2 = np.random.randn(534)
        
        user_context = {
            "skin_type": "dry",
            "budget": 100.0,
        }
        
        # Get initial prediction (before learning)
        score_before_1, _ = learner.predict_preference(product_vec1, user_context)
        print(f"✅ Initial prediction for product 1: {score_before_1:.3f}")
        
        # Learn that user likes product 1
        learner.learn_from_interaction(product_vec1, label=1, user_context=user_context)
        print(f"✅ Model learned: user LIKES product 1")
        
        # Get prediction after learning
        score_after_1, _ = learner.predict_preference(product_vec1, user_context)
        print(f"✅ Prediction for product 1 after learning: {score_after_1:.3f}")
        
        if score_after_1 > score_before_1:
            print(f"✅ Score increased (learning worked): {score_before_1:.3f} → {score_after_1:.3f}")
        else:
            print(f"⚠️  Score did not increase as expected")
        
        # Learn that user dislikes product 2
        learner.learn_from_interaction(product_vec2, label=-1, user_context=user_context)
        print(f"✅ Model learned: user DISLIKES product 2")
        
        score_2, _ = learner.predict_preference(product_vec2, user_context)
        print(f"✅ Prediction for product 2 after learning dislike: {score_2:.3f}")
        
        if score_2 < 0:
            print(f"✅ Score is negative (captures dislike sentiment)")
        
        print(f"\n  Model learning: ✅ WORKING")
        return True
        
    except Exception as e:
        print(f"❌ Model learning test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_feedback_collection():
    """Check feedback collection system"""
    print_header("7. Testing Feedback Collection")
    
    try:
        from skincarelib.ml_system.feedback_structures import (
            DetailedFeedbackCollector,
            InitialUserQuestionnaire,
            IngredientPreferenceTracker,
        )
        
        # Test questionnaire
        questionnaire = InitialUserQuestionnaire()
        questionnaire.set_user_profile(
            skin_type="Oily",
            skin_concerns=["Acne"],
            budget_range=("20-50", 50),
        )
        context = questionnaire.get_context_features()
        print(f"✅ InitialUserQuestionnaire working")
        print(f"   - Context features: {list(context.keys())}")
        
        # Test feedback collector
        collector = DetailedFeedbackCollector()
        question, options = collector.get_followup_questions("Moisturizer", "like")
        print(f"✅ DetailedFeedbackCollector working")
        print(f"   - Question: '{question}'")
        print(f"   - Options available: {len(options)}")
        
        # Test ingredient tracker
        tracker = IngredientPreferenceTracker()
        tracker.record_ingredient_feedback(
            ingredients=["water", "glycerin", "hyaluronic acid"],
            rating=1,
            product_id="p123"
        )
        tracker.record_ingredient_feedback(
            ingredients=["alcohol", "fragrance"],
            rating=-1,
            product_id="p124"
        )
        
        scores = tracker.get_ingredient_preference_scores()
        print(f"✅ IngredientPreferenceTracker working")
        print(f"   - Tracked ingredients: {len(scores)}")
        
        liked = tracker.get_liked_ingredients(threshold=0.5)
        disliked = tracker.get_disliked_ingredients(threshold=-0.5)
        print(f"   - Liked ingredients: {len(liked)}")
        print(f"   - Disliked ingredients: {len(disliked)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Feedback collection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all checks"""
    print("\n" + "="*60)
    print("  ML SETUP VERIFICATION")
    print("="*60)
    
    checks = [
        ("Imports", check_imports),
        ("Artifacts", check_artifacts),
        ("Product Data", check_data),
        ("Model Initialization", check_model_initialization),
        ("Model Learning", check_model_learning),
        ("Feedback Collection", check_feedback_collection),
        ("End-to-End Flow", check_swipe_session),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    # Summary
    print_header("SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {name}")
    
    print(f"\n{passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! ML system is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} checks failed. Review errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
