import pandas as pd
from typing import Optional
import unicodedata


def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

def add_price_column(products_df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    # drop duplicates in prices to ensure we have only one price per product
    prices = prices_df[['brand', 'product_name', 'price']].drop_duplicates(
        subset=['brand', 'product_name'],
        keep='first'
    )

    merged = products_df.merge(
        prices,
        on=['brand', 'product_name'],
        how='left',
        validate='many_to_one' #there may be duplicates in products, but only one price per product   
    )

    return merged

def standardize_prices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["brand"] = df["brand"].apply(normalize_text)
    df["product_name"] = df["product_name"].apply(normalize_text)
    return df

def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset=['brand', 'product_name'])

def clean_ingredient(ing: Optional[str]) -> str:
    if not isinstance(ing, str) or not ing.strip():
        return ""
    parts = [p.strip().lower() for p in ing.split(",") if p.strip()]
    return ", ".join(parts)

def normalize_text(x: Optional[str]) -> str:
    if not isinstance(x, str):
        return ""
    x = unicodedata.normalize("NFKC", x)
    return x.strip().lower()


def standardize_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ingredients'] = df['ingredients'].apply(clean_ingredient)
    df['brand'] = df['brand'].apply(normalize_text)
    df['product_name'] = df['product_name'].apply(normalize_text)
    return df

def run_pipeline(df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    """ simple pipeline to run all steps in sequence """
    df = standardize_data(df)
    prices_df = standardize_prices(prices_df)
    df = add_price_column(df, prices_df)
    df = remove_duplicates(df) 
    df = df.dropna(subset=["price"]) #just 0.08% prices missing
    return df 