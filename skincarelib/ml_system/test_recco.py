from skincarelib.models.recommender_ranker import recommend

print("\n=== TEST RECOMMENDER ===\n")

results = recommend(
    liked_product_ids=[],
    explicit_prefs={
        "skin_type": "dry",
        "preferred_categories": ["serum"],
    },
    constraints={"budget": 50},
    top_n=5,
)

print(results)
print("\nEmpty?", results.empty)
