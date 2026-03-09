from v2_utils import load_csv, run_pipeline

"""
Data Preparation Process

What it covers:
1. Loads raw dataset
2. Normalizes text fields
3. Cleans ingredients
4. Adds price column (empty placeholder for now)
5. Removes duplicates
6. Save cleaned dataset
"""

def main():
    df = load_csv("data/products_dataset_raw.csv")
    
    df_processed = run_pipeline(df)
    
    df_processed.to_csv("data/products_dataset_processed.csv", index=False)
    print("File saved as products_dataset_processed.csv")

if __name__ == "__main__":
    main()