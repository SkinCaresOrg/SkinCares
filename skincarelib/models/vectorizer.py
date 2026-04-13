import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder

try:
    import faiss  # type: ignore[import-not-found]
except ImportError:
    faiss = None

from skincarelib.ml_system.artifacts import find_project_root


ROOT = find_project_root()

GROUPS_PATH = ROOT / "features" / "ingredient_groups.json"
ARTIFACT_DIR = ROOT / "artifacts"

SIGNAL_KEYS = [
    "hydration",
    "barrier",
    "acne_control",
    "soothing",
    "exfoliation",
    "antioxidant",
    "irritation_risk",
]


def _resolve_products_path() -> Path:
    path = ROOT / "data" / "processed" / "products_with_signals.csv"
    if path.exists():
        return path
    raise FileNotFoundError(f"Missing dataset required for artifact build: {path}")


def load_data():
    data_products = _resolve_products_path()
    df = pd.read_csv(data_products)

    # product_id is derived from row index so it stays consistent
    # with product_index.json and dupe_finder.py
    if "product_id" not in df.columns:
        df["product_id"] = df.index.astype(str)

    required = ["product_id", "category", "price"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    token_column = None
    for candidate in ("ingredient_tokens_clean", "ingredient_tokens", "ingredients"):
        if candidate in df.columns:
            token_column = candidate
            break
    if token_column is None:
        raise ValueError(
            "Missing token text column. Expected one of: "
            "ingredient_tokens_clean, ingredient_tokens, ingredients"
        )

    # warn if tokens look unparsed (still a plain string rather than a list)
    non_empty_tokens = df[token_column].dropna().astype(str).str.strip()
    sample = non_empty_tokens.iloc[0] if not non_empty_tokens.empty else ""
    if sample and not sample.startswith("["):
        import warnings

        warnings.warn(
            f"{token_column} may not be in list format — check tokenization output"
        )

    df["ingredient_tokens"] = df[token_column]

    # fill any missing signal columns with zero
    for sig in SIGNAL_KEYS:
        if sig not in df.columns:
            df[sig] = 0.0

    return df.reset_index(drop=True)


def load_groups():
    with open(GROUPS_PATH) as f:
        return json.load(f)


def build_tfidf(token_series):
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


def build_signal_features(df):
    """Stack the 7 CosIng-derived signal columns into a dense feature block.

    Values are already normalised to [0, 1] by the skin-type mapping pipeline.
    """
    return csr_matrix(df[SIGNAL_KEYS].fillna(0.0).to_numpy(dtype=np.float32))


def stack_all(X_tfidf, X_groups, X_cat, X_price, X_signals):
    return hstack([X_tfidf, X_groups, X_cat, X_price, X_signals], format="csr")


def build_schema(tfidf_vec, group_names, cat_names):
    """Record where each feature block lives in the final vector.

    Groups are stored as {name: {start, end}} rather than a flat list so
    that DupeScorer can slice out each group's dimensions by name.
    Signals are stored the same way for use by user_profile.py.
    """
    tfidf_names = tfidf_vec.get_feature_names_out().tolist()
    n_tfidf = len(tfidf_names)
    n_groups = len(group_names)
    n_cats = len(cat_names)
    n_signals = len(SIGNAL_KEYS)

    group_start = n_tfidf
    cat_start = group_start + n_groups
    price_idx = cat_start + n_cats
    signal_start = price_idx + 1

    groups_schema = {
        name: {"start": group_start + i, "end": group_start + i + 1}
        for i, name in enumerate(group_names)
    }

    signals_schema = {
        name: {"start": signal_start + i, "end": signal_start + i + 1}
        for i, name in enumerate(SIGNAL_KEYS)
    }

    return {
        "tfidf": tfidf_names,
        "groups": groups_schema,
        "categories": cat_names,
        "price_index": price_idx,
        "signals": signals_schema,
        "total_features": signal_start + n_signals,
    }


def build_faiss_index(vectors: np.ndarray):
    """Build a FAISS flat inner-product index over L2-normalised vectors.

    Normalising first means inner product == cosine similarity, so the index
    returns the same neighbours as a cosine search but scales to much larger
    catalogues without slowing down.
    """
    if faiss is None:
        raise RuntimeError("faiss is not installed")

    vectors = vectors.copy().astype(np.float32)
    faiss.normalize_L2(vectors)
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    print(f"FAISS index built: {index.ntotal} vectors, dim={dim}")
    return index


def save_outputs(X, df, schema, tfidf_vec):
    ARTIFACT_DIR.mkdir(exist_ok=True)

    dense = X.toarray().astype(np.float32)
    np.save(ARTIFACT_DIR / "product_vectors.npy", dense)

    product_index = {pid: i for i, pid in enumerate(df["product_id"])}
    with open(ARTIFACT_DIR / "product_index.json", "w") as f:
        json.dump(product_index, f, indent=2)

    with open(ARTIFACT_DIR / "feature_schema.json", "w") as f:
        json.dump(schema, f, indent=2)

    joblib.dump(tfidf_vec, ARTIFACT_DIR / "tfidf.joblib")

    # FAISS index — used in dupe_finder for fast ANN candidate retrieval
    if faiss is not None:
        faiss_index = build_faiss_index(dense)
        faiss.write_index(faiss_index, str(ARTIFACT_DIR / "faiss.index"))
    else:
        print("FAISS not installed; skipping artifacts/faiss.index generation")

    print(f"Artifacts saved to {ARTIFACT_DIR}")


def run():
    df = load_data()
    groups = load_groups()

    X_tfidf, tfidf_vec = build_tfidf(df["ingredient_tokens"])
    X_groups, group_names = build_group_features(df["ingredient_tokens"], groups)
    X_cat, cat_names = build_category_features(df["category"])
    X_price = build_price_feature(df["price"])
    X_signals = build_signal_features(df)

    X = stack_all(X_tfidf, X_groups, X_cat, X_price, X_signals)
    schema = build_schema(tfidf_vec, group_names, cat_names)

    save_outputs(X, df, schema, tfidf_vec)
    print("Vectorization finished:", X.shape)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print("Pipeline failed:", e)
        sys.exit(1)
