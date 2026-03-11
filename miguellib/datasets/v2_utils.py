import json
import re
import unicodedata
import pandas as pd
from typing import Optional, List, Tuple, Pattern

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


def smart_split_ingredients(ingredients: Optional[str]) -> List[str]:
    """
    Split an ingredient string into tokens while protecting common
    numeric ingredient patterns such as '1, 2-hexanediol'.
    Deduplicates tokens while preserving order.
    """
    if not isinstance(ingredients, str) or not ingredients.strip():
        return []

    text = ingredients.strip().lower()

    # protect numeric ingredient names like "1, 2-hexanediol"
    text = re.sub(r'(\d)\s*,\s*(\d-\w)', r'\1@@\2', text)

    parts = [p.strip() for p in text.split(",") if p.strip()]

    tokens = []
    seen = set()

    for p in parts:
        t = p.replace("@@", ", ")
        t = re.sub(r"\s+", " ", t).strip()

        if t and t not in seen:
            tokens.append(t)
            seen.add(t)

    return tokens

def load_synonyms(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def apply_synonyms(tokens: List[str], synonym_map: dict) -> List[str]:
    """
    Replace tokens using a synonym dictionary and deduplicate
    while preserving order.
    """
    mapped = []
    seen = set()

    for t in tokens:
        new = synonym_map.get(t, t)

        if new and new not in seen:
            mapped.append(new)
            seen.add(new)

    return mapped

CANON_RULES_SMALL = [
    ("water", [
        r"^\s*aqua\s*$",
        r"^\s*water\s*$",
        r"^\s*eau\s*$",
        r"aqua\s*/\s*water\s*/\s*eau",
        r"water\s*/\s*aqua\s*/\s*eau",
        r"water\s*\\\s*aqua\s*\\\s*eau",
        r"aqua\s*\\\s*water\s*\\\s*eau",
        r"water/aqua/eau",
        r"aqua/water/eau",
        r"water\\aqua\\eau",
        r"water\s*\(aqua\)",
        r"aqua\s*\(water\)",
        r"water\s*\(aqua/eau\)",
        r"aqua\s*\(water/eau\)",
        r"water/eau",
        r"water/aqua",
        r"aqua/water",
        r"purified\s+water",
        r"^water\s*\(aqua$",
        r"^eau\)$"
    ]),

    ("fragrance", [
        r"^\s*parfum\s*$",
        r"^\s*fragrance\s*$",
        r"^\s*perfume\s*$",
        r"parfum\s*\(fragrance\)",
        r"fragrance\s*\(parfum\)",
        r"fragrance\s*/\s*parfum",
        r"parfum\s*/\s*fragrance",
        r"parfum/fragrance",
        r"fragrance/parfum",
        r"natural\s+fragrance",
        r"^\s*aroma\s*$",
        r"^\s*flavor\s*$",
        r"^\s*flavors\s*$",
        r"flavor\s*\(aroma\)",
        r"aroma\s*\(flavor\)",
        r"flavor/aroma",
        r"aroma/flavor"
    ]),

    ("vitamin e", [
        r"\btocopherol\b",
        r"\btocopheryl\s+acetate\b",
        r"\btocopheryl\s+succinate\b",
        r"\btocotrienols\b",
        r"\btocopherol\s*\(vitamin e\)",
        r"\btocopheryl acetate\s*\(vitamin e\)",
        r"\btocopherol\s*\(natural vitamin e\)",
        r"\bmixed tocopherols\b",
        r"\btocopherols\b",
        r"\btocopheryl\b"
    ]),

    ("mica", [
        r"\bmica\b",
        r"\bmica\s*\(ci\s*77019\)",
        r"\bci\s*77019\b",
        r"\bci\s*77019\s*\(mica\)"
    ]),

    ("titanium dioxide", [
        r"titanium\s+dioxide",
        r"titanium dioxide\s*\(ci\s*77891\)",
        r"ci\s*77891\s*\(titanium dioxide\)",
        r"ci\s*77891/titanium dioxide",
        r"ci\s*77891\s*/\s*titanium dioxide",
        r"\bci\s*77891\b"
    ]),

    ("iron oxides", [
        r"iron\s+oxides",
        r"iron oxide",
        r"iron oxides\s*\(ci\s*77491\)?",
        r"iron oxides\s*\(ci\s*77492\)?",
        r"iron oxides\s*\(ci\s*77499\)?",
        r"ci\s*77491\s*\(iron oxides\)",
        r"ci\s*77492\s*\(iron oxides\)",
        r"ci\s*77499\s*\(iron oxides\)",
        r"iron oxides ci\s*77491",
        r"ci\s*77491/iron oxides",
        r"\bci\s*77491\b",
        r"\bci\s*77492\b",
        r"\bci\s*77499\b"
    ]),
]
def apply_canon_to_tokens(
    tokens: List[str],
    canon_rules_compiled: List[Tuple[str, List[Pattern]]]
) -> List[str]:
    """
    Apply canonical ingredient mapping to a list of tokens.

    Each token is checked against compiled regex rule groups.
    If a token matches one of the canonical groups, it is replaced
    by the canonical token name.

    Deduplicates while preserving original order.
    """
    if not isinstance(tokens, list):
        return []

    out = []
    seen = set()

    for tok in tokens:
        if not isinstance(tok, str):
            continue

        t = tok.strip()
        if not t:
            continue

        canon = None
        for canon_token, patterns in canon_rules_compiled:
            if any(p.search(t) for p in patterns):
                canon = canon_token
                break

        final_tok = canon if canon else t

        if final_tok not in seen:
            out.append(final_tok)
            seen.add(final_tok)

    return out

CANON_RULES_SMALL_COMPILED: List[Tuple[str, List[Pattern]]] = [
    (canon, [re.compile(pat, flags=re.IGNORECASE) for pat in pats])
    for canon, pats in CANON_RULES_SMALL
]


def run_pipeline2(
    df: pd.DataFrame,
    synonym_map: dict,
    canon_rules_compiled: List[Tuple[str, List[Pattern]]]
) -> pd.DataFrame:
    """
    Run the ingredient-standardization pipeline.

    Steps:
    1. Tokenize ingredient strings
    2. Apply synonym normalization
    3. Apply canonical ingredient mapping
    """
    df = df.copy()

    df["ingredient_tokens"] = df["ingredients"].apply(smart_split_ingredients)
    df["ingredient_tokens_syn"] = df["ingredient_tokens"].apply(
        lambda toks: apply_synonyms(toks, synonym_map)
    )
    df["ingredient_tokens_clean"] = df["ingredient_tokens_syn"].apply(
        lambda toks: apply_canon_to_tokens(toks, canon_rules_compiled)
    )

    return df