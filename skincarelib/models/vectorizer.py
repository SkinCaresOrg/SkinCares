import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder


ROOT = Path(__file__).resolve().parent.parent.parent

DATA_PRODUCTS = ROOT / "data" / "processed" / "cosmetics_processed_clean_tokens.csv"
GROUPS_PATH = ROOT / "features" / "ingredient_groups.json"
ARTIFACT_DIR = ROOT / "artifacts"


def load_data():
    df = pd.read_csv(DATA_PRODUCTS)

    # product_id is derived from row index so it stays consistent
    # with product_index.json and dupe_finder.py
    df["product_id"] = df.index.astype(str)

    required = ["product_id", "category", "price", "ingredient_tokens_clean"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    # warn if tokens look unparsed (still a plain string rather than a list)
    sample = df["ingredient_tokens_clean"].dropna().iloc[0]
    if not sample.strip().startswith("["):
        import warnings

        warnings.warn(
            "ingredient_tokens_clean may not be in list format — check tokenization output"
        )

    # use the clean tokens column as the ingredient text
    df["ingredient_tokens"] = df["ingredient_tokens_clean"]

    return df.reset_index(drop=True)


def load_groups():
    with open(GROUPS_PATH) as f:
        return json.load(f)


def build_tfidf(token_series):
    # tokens are stored as Python list strings: "['glycerin', 'water', ...]"
    # parse them properly before joining into text for TF-IDF
    import ast

    def parse_tokens(row):
        try:
            parsed = ast.literal_eval(row)
            return " ".join(t.strip().lower() for t in parsed if isinstance(t, str))
        except (ValueError, SyntaxError):
            return row.lower().strip()

    text = token_series.fillna("").apply(parse_tokens)

    vectorizer = TfidfVectorizer(
        max_features=512,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )

    X = vectorizer.fit_transform(text)
    return X, vectorizer


def build_group_features(token_series, group_map):
    """Count how many ingredients per product belong to each functional group.

    Each group (humectant, emollient, exfoliant, etc.) becomes one dimension.
    Used downstream by DupeScorer to compute ingredient group overlap.
    """
    groups = sorted(set(group_map.values()))
    group_idx = {g: i for i, g in enumerate(groups)}

    rows, cols, data = [], [], []

    for i, row in enumerate(token_series.fillna("")):
        # tokens are stored as a Python list string: "['glycerin', 'water', ...]"
        # ast.literal_eval parses this safely; fall back to comma-split if it fails
        try:
            import ast

            parsed = ast.literal_eval(row)
            tokens = [t.strip().lower() for t in parsed if isinstance(t, str)]
        except (ValueError, SyntaxError):
            tokens = [t.strip().lower() for t in row.split(",") if t.strip()]
        counts = {}

        for tok in tokens:
            if tok in group_map:
                idx = group_idx[group_map[tok]]
                counts[idx] = counts.get(idx, 0) + 1

        for c, v in counts.items():
            rows.append(i)
            cols.append(c)
            data.append(v)

    X = csr_matrix((data, (rows, cols)), shape=(len(token_series), len(groups)))
    names = [f"group_{g}" for g in groups]

    return X, names


def build_category_features(series):
    encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    X = encoder.fit_transform(series.fillna("unknown").to_frame())
    names = [f"cat_{c}" for c in encoder.categories_[0]]
    return X, names


def build_price_feature(series):
    values = (
        pd.to_numeric(series, errors="coerce")
        .fillna(pd.to_numeric(series, errors="coerce").median())
        .to_numpy()
        .reshape(-1, 1)
    )
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(values)
    return csr_matrix(scaled)


def stack_all(X_tfidf, X_groups, X_cat, X_price):
    return hstack([X_tfidf, X_groups, X_cat, X_price], format="csr")


def build_schema(tfidf_vec, group_names, cat_names):
    """Record where each feature block lives in the final vector.

    Groups are stored as {name: {start, end}} rather than a flat list so
    that DupeScorer can slice out each group's dimensions by name.
    """
    tfidf_names = tfidf_vec.get_feature_names_out().tolist()
    n_tfidf = len(tfidf_names)
    n_groups = len(group_names)
    n_cats = len(cat_names)

    group_start = n_tfidf
    cat_start = group_start + n_groups
    price_idx = cat_start + n_cats

    groups_schema = {
        name: {"start": group_start + i, "end": group_start + i + 1}
        for i, name in enumerate(group_names)
    }

    return {
        "tfidf": tfidf_names,
        "groups": groups_schema,
        "categories": cat_names,
        "price_index": price_idx,
        "total_features": price_idx + 1,
    }


def save_outputs(X, df, schema, tfidf_vec):
    ARTIFACT_DIR.mkdir(exist_ok=True)

    np.save(ARTIFACT_DIR / "product_vectors.npy", X.toarray().astype(np.float32))

    product_index = {pid: i for i, pid in enumerate(df["product_id"])}
    with open(ARTIFACT_DIR / "product_index.json", "w") as f:
        json.dump(product_index, f, indent=2)

    with open(ARTIFACT_DIR / "feature_schema.json", "w") as f:
        json.dump(schema, f, indent=2)

    joblib.dump(tfidf_vec, ARTIFACT_DIR / "tfidf.joblib")

    print(f"Artifacts saved to {ARTIFACT_DIR}")


def run():
    df = load_data()
    groups = load_groups()

    X_tfidf, tfidf_vec = build_tfidf(df["ingredient_tokens"])
    X_groups, group_names = build_group_features(df["ingredient_tokens"], groups)
    X_cat, cat_names = build_category_features(df["category"])
    X_price = build_price_feature(df["price"])

    X = stack_all(X_tfidf, X_groups, X_cat, X_price)
    schema = build_schema(tfidf_vec, group_names, cat_names)

    save_outputs(X, df, schema, tfidf_vec)
    print("Vectorization finished:", X.shape)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print("Pipeline failed:", e)
        sys.exit(1)
