from v2_utils import (
    load_csv,
    load_synonyms,
    run_pipeline2,
    CANON_RULES_SMALL_COMPILED
)


    
def main():
    df_processed = load_csv("data/products_dataset_processed.csv")
    synonyms = load_synonyms("synonyms_v2.json")

    df_clean = run_pipeline2(
        df_processed,
        synonyms,
        CANON_RULES_SMALL_COMPILED
    )

    df_clean.to_csv("data/products_dataset_clean_tokens.csv", index=False)
    print("File saved as products_dataset_clean_tokens.csv")


if __name__ == "__main__":
    main()