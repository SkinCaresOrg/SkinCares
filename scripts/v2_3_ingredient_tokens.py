# Run this on products_dataset_processed.csv to generate the updated tokens.
from rapidfuzz import process, fuzz
from pathlib import Path
from v2_utils import (
    load_csv,
    build_known_ingredients,
    run_pipeline2,
    CANON_RULES_SMALL_COMPILED,
)

def main():
    project_root = Path(__file__).resolve().parents[1]

    processed_data_path = project_root / "data" / "processed" / "products_dataset_processed.csv"
    output_path = project_root / "data" / "processed" / "products_dataset_clean_tokens.csv"

    df_processed = load_csv(processed_data_path)
    known_ingredients = build_known_ingredients(df_processed)

    df_clean = run_pipeline2(
        df_processed,
        known_ingredients,
        CANON_RULES_SMALL_COMPILED,
    )

    df_clean.to_csv(output_path, index=False)
    print(f"File saved as {output_path}")

if __name__ == "__main__":
    main()