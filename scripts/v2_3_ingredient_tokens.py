from pathlib import Path
from v2_utils import (
    load_csv,
    load_synonyms,
    run_pipeline2,
    CANON_RULES_SMALL_COMPILED
)

def main():
    project_root = Path(__file__).resolve().parents[1]

    processed_data_path = project_root / "data" / "processed" / "products_dataset_processed.csv"
    synonyms_path = project_root / "features" / "synonyms_v2.json"
    output_path = project_root / "data" / "processed" / "products_dataset_clean_tokens.csv"

    df_processed = load_csv(processed_data_path)
    synonyms = load_synonyms(synonyms_path)

    df_clean = run_pipeline2(
        df_processed,
        synonyms,
        CANON_RULES_SMALL_COMPILED
    )

    df_clean.to_csv(output_path, index=False)
    print(f"File saved as {output_path}")

if __name__ == "__main__":
    main()