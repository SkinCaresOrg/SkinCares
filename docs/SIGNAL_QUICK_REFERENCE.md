# Product Signals - Quick Reference

## What Are Product Signals?

Precomputed vectors representing key product properties across 7 dimensions:

| Signal | Scale | Meaning |
|--------|-------|---------|
| `hydration` | 0-1 | How moisturizing is this product? |
| `barrier` | 0-1 | Does it strengthen the skin barrier? |
| `acne_control` | 0-1 | How effective against acne/breakouts? |
| `soothing` | 0-1 | Is it calming/anti-inflammatory? |
| `exfoliation` | 0-1 | Does it remove dead skin cells? |
| `antioxidant` | 0-1 | Does it provide antioxidant protection? |
| `irritation_risk` | 0-1 | How likely to cause irritation? (lower is better) |

Plus **skin-type specific scores** (0-1 scale):
- `score_dry` - Rating for dry skin
- `score_oily` - Rating for oily skin  
- `score_sensitive` - Rating for sensitive skin
- `score_combination` - Rating for combination skin
- `score_normal` - Rating for normal skin

## How Are Signals Used?

When you request product recommendations:

```bash
GET /api/recommendations/{user_id}
```

The API:

1. **Loads your profile**: Skin type, concerns (acne, dryness, etc.), sensitivity level
2. **Scores each product** using:
   - ML model (trained on your past swipes): 70% weight
   - Signal vectors (matching your profile): 30% weight
3. **Returns ranked products** best for YOUR profile

## Example: How Signals Work

### User Profile: Dry, Sensitive Skin with Acne Concerns

**Product A Signals**:
```json
{
  "score_dry": 0.90,         ← Great for dry skin!
  "score_sensitive": 0.85,   ← Good for sensitive
  "hydration": 0.88,         ← Very hydrating ✓
  "irritation_risk": 0.15,   ← Low irritation risk ✓
  "acne_control": 0.72       ← Decent for acne ✓
}
```

**Product B Signals**:
```json
{
  "score_dry": 0.45,         ← Not great for dry
  "score_sensitive": 0.30,   ← Poor for sensitive ✗
  "exfoliation": 0.85,       ← High exfoliation
  "irritation_risk": 0.60,   ← Higher irritation risk ✗
  "acne_control": 0.90       ← Very effective for acne
}
```

**Result**: Product A scores higher for this user (better match for dry + sensitive profile)

## Where Are Signals Defined?

File: `data/processed/products_with_signals.csv`

```csv
product_id,product_name,hydration,barrier,acne_control,...,score_dry,score_oily,...
1,Cleanser A,0.7,0.6,0.8,...,0.75,0.6,...
2,Moisturizer B,0.9,0.8,0.4,...,0.95,0.4,...
```

## How Are Signals Loaded?

**At API startup**:
```python
# In deployment/api/app.py
PRODUCT_SIGNALS = load_product_signals_from_csv()
```

**Status Messages**:
```
✓ Loaded signal vectors for 5127 products
⚠️  Signal vectors not found at {path}. Running in degraded mode.
```

## Performance Impact

- **Load Time**: < 100ms (one-time at startup)
- **Per-Request Overhead**: < 50ms (scoring 12 recommendations)
- **Memory**: ~1MB for 5000 products

## If Signals Are Missing

The API gracefully falls back:
- ✓ Still shows recommendations
- ✓ Uses only ML model scores
- ✓ Logs warning indicating degraded mode
- ✓ No errors or crashes

## Concern-to-Signal Mapping

When you have specific concerns:

| Your Concern | Signals We Check |
|-------------|-----------------|
| **Acne** | `acne_control` |
| **Dryness** | `hydration`, `score_dry` |
| **Oiliness** | `barrier`, `score_oily` |
| **Redness** | `soothing`, `score_sensitive` |
| **Dark Spots** | `antioxidant` |
| **Fine Lines** | `hydration` |
| **Dullness** | `exfoliation` |
| **Large Pores** | `barrier` |

## Sensitivity Level Impact

For **sensitive** users:
- We apply a penalty for high `irritation_risk` products
- Preference for products with low `irritation_risk` scores
- Favor products with higher `score_sensitive`

## How to Generate Signals

For your own product database:

1. **Extract ingredients** from product data
2. **Score each ingredient** for the 7 dimensions (hydration, barrier, etc.)
3. **Aggregate** ingredient scores by product
4. **Save to CSV** with format shown above

See: `notebooks/` for example preprocessing pipelines

## Testing Signals

```bash
# Run signal tests
pytest tests/test_product_signals.py -v

# Output:
# test_signal_loading PASSED
# test_skin_type_signal_score PASSED
# test_concern_to_signal_mapping PASSED
# test_signal_score_computation PASSED
```

## Environment Variables

```bash
# Use custom signals CSV path
export PRODUCTS_SIGNALS_CSV_PATH="/custom/path/products_with_signals.csv"

# Default is: data/processed/products_with_signals.csv
```

## Common Questions

**Q: What if two products have the same ML score?**  
A: Signals provide additional nuance to break ties and personalize further.

**Q: Do signals replace the ML model?**  
A: No! Signals complement ML (70% ML + 30% signals). Both are important.

**Q: Can I see which signals influenced a recommendation?**  
A: Currently signals are used internally. Check `explanation` field for rationale.

**Q: Are signals updated automatically?**  
A: Currently static from CSV. Can be regenerated via preprocessing pipeline.

**Q: What if a product has no signal data?**  
A: Uses neutral default 0.5 score, falls back to other scoring methods.

## Architecture Diagram

```
User Profile (skin type, concerns, sensitivity)
    ↓
Get Recommendations Request
    ↓
For Each Product:
    ├─ Load Signals → {hydration: 0.8, barrier: 0.6, ...}
    ├─ Match Signals to Profile
    │   ├─ Check skin-type score
    │   ├─ Check concern-related signals
    │   └─ Apply sensitivity penalty
    ├─ Get ML Score
    └─ Combine: 70% ML + 30% Signals
    ↓
Sort by Combined Score
    ↓
Return Top Recommendations
```

## Next Steps

1. **Verify signals are loaded**: Check API logs for signal loading messages
2. **Test recommendations**: Compare with/without signals using A/B test framework
3. **Collect feedback**: Monitor if signal-weighted recs improve user satisfaction
4. **Iterate**: Refine signal dimensions based on user behavior

---

For technical details, see: `docs/SIGNAL_INTEGRATION.md`  
For implementation status, see: `SIGNAL_IMPLEMENTATION_SUMMARY.md`
