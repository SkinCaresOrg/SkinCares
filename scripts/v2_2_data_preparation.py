from v2_utils import load_csv, run_pipeline

"""
Data Preparation Process

What it covers:
1. Loads raw dataset
2 Merges price information from separate file
3. Normalizes text fields
4. Cleans ingredients
5. Adds price column (empty placeholder for now)
6. Removes duplicates
7. Save cleaned dataset
"""


def main():
    df_products = load_csv("../data/raw/products_dataset_raw.csv")
    df_prices = load_csv("../data/raw/prices_raw.csv")

    df_processed = run_pipeline(df_products, df_prices)

    df_processed.to_csv("../data/processed/products_dataset_processed.csv", index=False)
    print("File saved as products_dataset_processed.csv")


if __name__ == "__main__":
    main()
