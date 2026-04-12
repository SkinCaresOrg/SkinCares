from __future__ import annotations

from pathlib import Path

import pandas as pd


SIGNAL_KEYS = [
    "hydration",
    "barrier",
    "acne_control",
    "soothing",
    "exfoliation",
    "antioxidant",
    "irritation_risk",
]


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    processed_dir = project_root / "data" / "processed"

    target = processed_dir / "products_with_signals.csv"
    if target.exists():
        print(f"Found: {target}")
        return

    source = processed_dir / "products_dataset_processed.csv"
    if not source.exists():
        raise FileNotFoundError(
            f"Missing required source dataset: {source}. "
            "Generate products_with_signals.csv locally from notebook first."
        )

    df = pd.read_csv(source)
    for signal_key in SIGNAL_KEYS:
        if signal_key not in df.columns:
            df[signal_key] = 0.0

    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False)
    print(f"Created fallback products_with_signals.csv from {source}")


if __name__ == "__main__":
    main()
