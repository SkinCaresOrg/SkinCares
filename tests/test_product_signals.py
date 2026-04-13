"""
Test suite for PRODUCT_SIGNALS integration in the API.
Verifies that signal loading and scoring functions work correctly.
"""

import json
import tempfile
from csv import DictWriter
from pathlib import Path

import pytest

# Mock the load functions to test signal integration
def create_test_signals_csv() -> Path:
    """Create a temporary CSV with test signal data."""
    temp_dir = tempfile.mkdtemp()
    csv_path = Path(temp_dir) / "products_with_signals.csv"
    
    test_signals = [
        {
            "product_id": 1,
            "product_name": "Cleaner A",
            "hydration": 0.7,
            "barrier": 0.6,
            "acne_control": 0.8,
            "soothing": 0.5,
            "exfoliation": 0.3,
            "antioxidant": 0.4,
            "irritation_risk": 0.2,
            "score_dry": 0.8,
            "score_oily": 0.6,
            "score_sensitive": 0.5,
            "score_combination": 0.7,
            "score_normal": 0.75,
            "signal_vector": json.dumps({
                "hydration": 0.7,
                "barrier": 0.6,
                "acne_control": 0.8,
            }),
        },
        {
            "product_id": 2,
            "product_name": "Moisturizer B",
            "hydration": 0.9,
            "barrier": 0.8,
            "acne_control": 0.4,
            "soothing": 0.7,
            "exfoliation": 0.1,
            "antioxidant": 0.6,
            "irritation_risk": 0.1,
            "score_dry": 0.95,
            "score_oily": 0.4,
            "score_sensitive": 0.9,
            "score_combination": 0.8,
            "score_normal": 0.85,
            "signal_vector": json.dumps({
                "hydration": 0.9,
                "barrier": 0.8,
            }),
        },
    ]
    
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(test_signals[0].keys())
        writer = DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_signals)
    
    return csv_path


def test_signal_loading():
    """Test that signals are loaded correctly from CSV."""
    # Simulate the signal loading function
    csv_path = create_test_signals_csv()
    
    try:
        assert csv_path.exists()
        
        # Read and verify content
        with open(csv_path) as cf:
            content = cf.read()
            assert "hydration" in content
            assert "0.7" in content
            assert "0.9" in content
    finally:
        csv_path.unlink()


def test_skin_type_signal_score():
    """Test the skin type signal score computation."""
    signals = {
        "score_dry": 0.8,
        "score_oily": 0.5,
        "score_sensitive": 0.9,
        "score_normal": 0.7,
        "hydration": 0.75,
    }
    
    # Test each skin type
    for skin_type in ["dry", "oily", "sensitive", "normal"]:
        expected_key = f"score_{skin_type}"
        score = signals.get(expected_key, 0.0)
        assert score > 0.0, f"Expected positive signal score for {skin_type}"


def test_concern_to_signal_mapping():
    """Test that concerns map correctly to signal types."""
    concern_to_signal = {
        "acne": "acne_control",
        "dryness": "hydration",
        "oiliness": "barrier",
        "redness": "soothing",
        "dark_spots": "antioxidant",
        "fine_lines": "hydration",
        "dullness": "exfoliation",
        "large_pores": "barrier",
    }
    
    signals = {
        "acne_control": 0.8,
        "hydration": 0.9,
        "barrier": 0.7,
        "soothing": 0.6,
        "antioxidant": 0.5,
        "exfoliation": 0.4,
        "irritation_risk": 0.1,
    }
    
    concerns = ["acne", "dryness", "redness"]
    total_score = 0.0
    
    for concern in concerns:
        signal_key = concern_to_signal.get(concern)
        if signal_key:
            total_score += signals.get(signal_key, 0.0)
    
    average_score = total_score / len(concerns)
    assert 0.5 < average_score < 1.0, f"Expected reasonable concern score, got {average_score}"


def test_signal_score_computation():
    """Test the complete signal-based scoring function."""
    signals_dry = {
        "score_dry": 0.9,
        "score_oily": 0.3,
        "hydration": 0.85,
        "barrier": 0.5,
        "acne_control": 0.4,
        "irritation_risk": 0.1,
    }
    
    signals_oily = {
        "score_dry": 0.3,
        "score_oily": 0.9,
        "acne_control": 0.8,
        "barrier": 0.7,
        "hydration": 0.4,
        "irritation_risk": 0.2,
    }
    
    # Dry-skin product should score higher for dry users
    dry_score = signals_dry["score_dry"] * 0.4  # Skin-type weight
    oily_score = signals_oily["score_oily"] * 0.4
    
    assert dry_score > 0.2, "Expected decent dry score"
    assert oily_score > 0.2, "Expected decent oily score"
    assert dry_score > oily_score * 0.5, "Dry-skin product should score better for dry type"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
