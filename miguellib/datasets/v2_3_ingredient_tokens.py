from pathlib import Path
from v2_utils import (
    load_csv,
    load_synonyms,
    run_pipeline2,
    CANON_RULES_SMALL_COMPILED
)


def main():
    base_dir = Path(__file__).resolve().parent

    df_processed = load_csv(base_dir / "data" / "products_dataset_processed.csv")
    synonyms = load_synonyms(base_dir / "synonyms_v2.json")

    df_clean = run_pipeline2(
        df_processed,
        synonyms,
        CANON_RULES_SMALL_COMPILED
    )

    output_path = base_dir / "data" / "products_dataset_clean_tokens.csv"
    df_clean.to_csv(output_path, index=False)
    print(f"File saved as {output_path.name}")


if __name__ == "__main__":
    main()