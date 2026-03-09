import pandas as pd
from typing import Optional

def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

def add_price_column(df: pd.DataFrame) -> pd.DataFrame:
    if 'price' not in df.columns:
        df['price'] = None
    return df

def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset=['brand', 'product_name'])

def clean_ingredient(ing: Optional[str]) -> str:
    if not isinstance(ing, str) or not ing.strip():
        return ""
    parts = [p.strip().lower() for p in ing.split(",") if p.strip()]
    return ", ".join(parts)

def standardize_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ingredients'] = df['ingredients'].apply(clean_ingredient)
    df['brand'] = df['brand'].str.strip().str.title()
    df['product_name'] = df['product_name'].str.strip()
    return df

def run_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """ simple pipeline to run all steps in sequence """
    df = add_price_column(df)
    df = remove_duplicates(df)
    df = standardize_data(df)
    
    return df