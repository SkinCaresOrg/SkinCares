#!/usr/bin/env python3
"""Generate products_with_signals.csv with precomputed signal scores."""

import csv
import ast
from pathlib import Path
import numpy as np
import json

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
INPUT_CSV = DATA_DIR / "products_dataset_processed.csv"
OUTPUT_CSV = DATA_DIR / "products_with_signals.csv"

# Signal definitions for each ingredient
# Tier A (direct CosIng mappings)
TIER_A_SIGNALS = {
    # Humectants
    "glycerin": {"hydration": 1, "barrier": 1, "soothing": 0.2, "irritation_risk": 0},
    "hyaluronic acid": {"hydration": 1, "barrier": 0.5, "soothing": 0.2, "irritation_risk": 0},
    
    # Occlusives
    "shea butter": {"hydration": 0.3, "barrier": 1, "soothing": 0.5, "irritation_risk": 0},
    "squalane": {"hydration": 0.5, "barrier": 1, "soothing": 0.3, "irritation_risk": 0},
    
    # Exfoliants
    "salicylic acid": {"soothing": 0.2, "exfoliation": 1, "irritation_risk": 1},
    "glycolic acid": {"soothing": 0.1, "exfoliation": 0.9, "irritation_risk": 1},
    
    # Actives
    "niacinamide": {"acne_control": 1, "hydration": 0.7, "irritation_risk": 0.3},
    "retinol": {"acne_control": 0.8, "exfoliation": 0.7, "irritation_risk": 1},
    
    # Soothing
    "centella asiatica": {"soothing": 1, "barrier": 0.7, "irritation_risk": 0},
    "aloe vera": {"soothing": 1, "hydration": 0.8, "barrier": 0.5, "irritation_risk": 0},
    "panthenol": {"hydration": 0.8, "soothing": 0.7, "barrier": 0.6, "irritation_risk": 0},
    
    # Antioxidants
    "vitamin c": {"antioxidant": 1, "irritation_risk": 0.5},
    "ferulic acid": {"antioxidant": 1, "irritation_risk": 0.3},
    "green tea extract": {"antioxidant": 0.9, "soothing": 0.4, "irritation_risk": 0},
}

# Tier B (common ingredient functions)
TIER_B_SIGNALS = {
    "ceramide": {"barrier": 1, "hydration": 0.8, "irritation_risk": 0},
    "phenoxyethanol": {"irritation_risk": 0.4},
    "fragrance": {"irritation_risk": 0.7},
    "alcohol denat": {"irritation_risk": 0.6, "exfoliation": 0.3},
    "essential oil": {"irritation_risk": 0.8},
    "benzoyl peroxide": {"acne_control": 1, "irritation_risk": 0.9},
    "zinc": {"acne_control": 0.7, "irritation_risk": 0.3},
    "sulfur": {"acne_control": 0.8, "irritation_risk": 0.7},
}

def tokenize_ingredients(ingredients_str: str) -> list:
    """Parse comma-separated ingredients into list."""
    if not ingredients_str:
        return []
    try:
        return [ing.strip().lower() for ing in ingredients_str.split(",") if ing.strip()]
    except:
        return []

def compute_signal_vector(ingredients: list) -> dict:
    """Compute signal vector for a product based on its ingredients."""
    signals = {
        "hydration": 0.0,
        "barrier": 0.0,
        "acne_control": 0.0,
        "soothing": 0.0,
        "exfoliation": 0.0,
        "antioxidant": 0.0,
        "irritation_risk": 0.0,
    }
    
    if not ingredients:
        return signals
    
    matched_count = 0
    for ing in ingredients:
        ing_clean = ing.strip().lower()
        
        # Check Tier A
        if ing_clean in TIER_A_SIGNALS:
            for key, val in TIER_A_SIGNALS[ing_clean].items():
                signals[key] = min(1.0, signals[key] + val)
            matched_count += 1
            continue
        
        # Check Tier B (substring matching)
        matched = False
        for tier_ing, tier_signals in TIER_B_SIGNALS.items():
            if tier_ing in ing_clean or ing_clean in tier_ing:
                for key, val in tier_signals.items():
                    signals[key] = min(1.0, signals[key] + val)
                matched = True
                matched_count += 1
                break
        
        if not matched:
            # Default: small signal boost (common ingredient)
            signals["hydration"] = min(1.0, signals["hydration"] + 0.05)
    
    # Normalize by averaging if multiple matches
    if matched_count > 0:
        for key in signals:
            if key != "irritation_risk":
                signals[key] /= (matched_count * 0.5 + 1)  # Damping factor
    
    return signals

def compute_skin_type_scores(signal_vector: dict) -> dict:
    """Compute skin-type affinity scores from signal vector."""
    h = signal_vector["hydration"]
    b = signal_vector["barrier"]
    ac = signal_vector["acne_control"]
    so = signal_vector["soothing"]
    ex = signal_vector["exfoliation"]
    ir = signal_vector["irritation_risk"]
    
    scores = {
        "score_dry": min(1.0, (h + b) / 2),
        "score_oily": min(1.0, ac * (1 - b) * (1 - h * 0.5)),
        "score_sensitive": min(1.0, (so + (1 - ir)) / 2),
        "score_combination": min(1.0, (ac * 0.6 + h * 0.4)),
        "score_normal": min(1.0, (ac * 0.3 + h * 0.3 + so * 0.2 + ex * 0.2)),
    }
    return scores

def main():
    """Generate signals CSV."""
    print(f"Reading from: {INPUT_CSV}")
    if not INPUT_CSV.exists():
        print(f"ERROR: Input file not found: {INPUT_CSV}")
        return
    
    rows = []
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            if idx % 10000 == 0:
                print(f"  Processing row {idx}...")
            
            ingredients = tokenize_ingredients(row.get("ingredients", ""))
            signal_vector = compute_signal_vector(ingredients)
            skin_scores = compute_skin_type_scores(signal_vector)
            
            # Infer skin_type from highest score
            skin_type = max(skin_scores, key=lambda k: skin_scores[k]).replace("score_", "")
            
            new_row = dict(row)
            new_row["ingredient_tokens"] = json.dumps(ingredients)
            new_row["ingredient_tokens_syn"] = json.dumps(ingredients)
            new_row["ingredient_tokens_clean"] = json.dumps(ingredients)
            new_row["signal_vector"] = json.dumps(signal_vector)
            for key, val in skin_scores.items():
                new_row[key] = str(val)
            new_row["skin_type"] = skin_type
            for key in ["hydration", "barrier", "acne_control", "soothing", "exfoliation", "antioxidant", "irritation_risk"]:
                new_row[key] = str(signal_vector.get(key, 0))
            
            rows.append(new_row)
    
    if not rows:
        print("ERROR: No rows read from input CSV")
        return
    
    print(f"Loaded {len(rows)} products")
    
    # Write output
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    
    all_columns = set()
    for row in rows:
        all_columns.update(row.keys())
    columns = list(all_columns)
    
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\nSaved to: {OUTPUT_CSV}")
    print(f"Rows: {len(rows)}")
    print(f"Columns: {len(columns)}")
    print(f"Expected columns present:")
    expected = {"product_name", "brand", "category", "price", "ingredients", "signal_vector",
                "score_dry", "score_oily", "score_sensitive", "score_combination", "score_normal",
                "skin_type", "hydration", "barrier", "acne_control", "soothing", "exfoliation",
                "antioxidant", "irritation_risk"}
    for col in sorted(expected):
        print(f"  {'✓' if col in all_columns else '✗'} {col}")

if __name__ == "__main__":
    main()
