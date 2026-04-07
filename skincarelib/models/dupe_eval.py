"""
Evaluation harness for the dupe finder.

Metrics
-------
precision@k : of the top-k results, what fraction are labeled relevant?
ndcg@k      : are the most relevant results ranked highest?

Benchmark CSV format
--------------------
query_product_id, relevant_product_id, relevance

relevance scale:
    2 = clear dupe (same key actives, same category, cheaper)
    1 = acceptable alternative (same category, cheaper, different formulation)
    omit rows for non-dupes — absence implies 0

Usage
-----
    python dupe_eval.py --template          # generate CSV to fill in
    python dupe_eval.py --benchmark benchmark.csv --k 3 5 10
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


def load_benchmark(path):
    bench = defaultdict(dict)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            qid = row["query_product_id"].strip()
            rid = row["relevant_product_id"].strip()
            rel = int(row.get("relevance", 1))
            bench[qid][rid] = rel
    return dict(bench)


def write_template(product_ids, path="benchmark_template.csv", n=20):
    """Sample n products at random and write an empty benchmark CSV to label."""
    rng = np.random.default_rng(42)
    sample = rng.choice(product_ids, size=min(n, len(product_ids)), replace=False)
    rows = [
        {"query_product_id": pid, "relevant_product_id": "", "relevance": ""}
        for pid in sample
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["query_product_id", "relevant_product_id", "relevance"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Template written to {path} ({len(sample)} queries)")


def precision_at_k(retrieved, relevant, k):
    hits = sum(1 for pid in retrieved[:k] if relevant.get(pid, 0) >= 1)
    return hits / k if k > 0 else 0.0


def ndcg_at_k(retrieved, relevant, k):
    dcg = sum(
        relevant.get(pid, 0) / math.log2(rank + 1)
        for rank, pid in enumerate(retrieved[:k], start=1)
    )
    ideal = sorted(relevant.values(), reverse=True)
    idcg = sum(rel / math.log2(rank + 1) for rank, rel in enumerate(ideal[:k], start=1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate(benchmark, k_values=(3, 5, 10), find_dupes_kwargs=None):
    """Run find_dupes over every query in the benchmark and compute metrics."""
    from dupe_finder import find_dupes

    kwargs = find_dupes_kwargs or {}
    max_k = max(k_values)
    rows = []

    for query_id, relevant in benchmark.items():
        try:
            results = find_dupes(query_id, top_n=max_k, explain=False, **kwargs)
            retrieved = results["product_id"].tolist()
        except ValueError:
            print(f"  [skip] {query_id} not in product index", file=sys.stderr)
            continue

        for k in k_values:
            rows.append(
                {
                    "query_id": query_id,
                    "k": k,
                    "precision@k": precision_at_k(retrieved, relevant, k),
                    "ndcg@k": ndcg_at_k(retrieved, relevant, k),
                }
            )

    if not rows:
        print("No results — check that benchmark product IDs exist in the index.")
        return pd.DataFrame()

    return pd.DataFrame(rows)


def print_summary(df):
    if df.empty:
        return
    summary = df.groupby("k")[["precision@k", "ndcg@k"]].mean().reset_index()
    print("\n=== Dupe Finder Evaluation ===")
    print(summary.to_string(index=False, float_format="%.4f"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default="benchmark.csv")
    parser.add_argument("--k", nargs="+", type=int, default=[3, 5, 10])
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.template:
        from dupe_finder import PRODUCT_INDEX

        write_template(list(PRODUCT_INDEX.keys()))
        sys.exit(0)

    bench_path = Path(args.benchmark)
    if not bench_path.exists():
        print(f"Benchmark not found: {bench_path}", file=sys.stderr)
        sys.exit(1)

    benchmark = load_benchmark(bench_path)
    print(f"Loaded {len(benchmark)} query products from {bench_path}")

    df = evaluate(benchmark, k_values=args.k)
    print_summary(df)

    if args.out:
        df.to_csv(args.out, index=False)
        print(f"Full results saved to {args.out}")
