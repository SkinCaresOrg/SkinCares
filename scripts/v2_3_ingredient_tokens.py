# This script replaces the manual synonym JSON approach with a fuzzy matching pipeline.
# Uses the official CosIng INCI database as the reference list for fuzzy matching
# instead of building known ingredients from the dataset itself.
# Run this on products_dataset_processed.csv to generate the updated tokens.

from pathlib import Path
from v2_utils import (
    load_csv,
    load_cosing_ingredients,
    run_pipeline2,
    CANON_RULES_SMALL_COMPILED,
    smart_split_ingredients,   
    apply_fuzzy,               
)


def main():
    project_root = Path(__file__).resolve().parents[1]

    processed_data_path = project_root / "data" / "processed" / "products_dataset_processed.csv"
    cosing_path = project_root / "data" / "raw" / "cosing_ingredients.csv"
    output_path = project_root / "data" / "processed" / "products_dataset_clean_tokens.csv"

    df_processed = load_csv(processed_data_path)
    known_ingredients = load_cosing_ingredients(str(cosing_path))
    # print("CosIng ingredients loaded:", len(known_ingredients))
# print("Sample:", known_ingredients[:10])

# sample_tokens = df_processed["ingredients"].iloc[:5]
# #quick sanity check on the fuzzy matching before running the full pipeline
# for i, row in enumerate(sample_tokens):
#     tokens = smart_split_ingredients(row)
#     fuzzy = apply_fuzzy(tokens, known_ingredients)
#     print(f"\nExample {i}:")
#     print("Original:", tokens)
#     print("After fuzzy:", fuzzy)

    df_clean = run_pipeline2(
        df_processed,
        known_ingredients,
        CANON_RULES_SMALL_COMPILED,
    )

    df_clean.to_csv(output_path, index=False)
    print(f"File saved as {output_path}")


if __name__ == "__main__":
    main()
