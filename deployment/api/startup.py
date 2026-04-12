from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from skincarelib.ml_system.build_artifacts import build


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

REQUIRED_ARTIFACTS = [
    "product_vectors.npy",
    "product_index.json",
    "feature_schema.json",
    "tfidf.joblib",
    "faiss.index",
]

SIGNAL_KEYS = [
    "hydration",
    "barrier",
    "acne_control",
    "soothing",
    "exfoliation",
    "antioxidant",
    "irritation_risk",
]


def _is_truthy(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _missing_artifacts() -> list[str]:
    return [name for name in REQUIRED_ARTIFACTS if not (ARTIFACTS_DIR / name).exists()]


def _ensure_products_with_signals() -> None:
    target = PROCESSED_DIR / "products_with_signals.csv"
    if target.exists():
        print(f"[startup] Found dataset: {target}")
        return

    source = PROCESSED_DIR / "products_dataset_processed.csv"
    if not source.exists():
        raise FileNotFoundError(
            "Missing datasets required for artifact build. Expected one of: "
            f"{target} or {source}."
        )

    print(f"[startup] Creating fallback dataset: {target.name} from {source.name}")
    df = pd.read_csv(source)
    for signal_key in SIGNAL_KEYS:
        if signal_key not in df.columns:
            df[signal_key] = 0.0

    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False)


def _ensure_artifacts() -> None:
    missing = _missing_artifacts()
    if not missing:
        print("[startup] All required artifacts present.")
        return

    print(f"[startup] Missing artifacts: {', '.join(missing)}")
    _ensure_products_with_signals()
    schema_version = os.getenv("SKINCARES_ARTIFACT_SCHEMA_VERSION", "v1")
    manifest_path = build(schema_version=schema_version)
    print(f"[startup] Artifacts rebuilt. Manifest: {manifest_path}")

    still_missing = _missing_artifacts()
    if still_missing:
        raise RuntimeError(
            "Artifacts still missing after build: " + ", ".join(still_missing)
        )


def _start_uvicorn() -> None:
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = os.getenv("UVICORN_PORT", "8000")
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "deployment.api:app",
            "--host",
            host,
            "--port",
            port,
        ],
    )


def main() -> None:
    auto_build = _is_truthy(os.getenv("SKINCARES_AUTO_BUILD_ARTIFACTS"), default=True)
    require_artifacts = _is_truthy(
        os.getenv("SKINCARES_REQUIRE_ARTIFACTS"),
        default=False,
    )

    if auto_build:
        try:
            _ensure_artifacts()
        except Exception as exc:
            if require_artifacts:
                raise SystemExit(
                    "[startup] Artifact bootstrap failed and SKINCARES_REQUIRE_ARTIFACTS=true. "
                    f"Error: {exc}"
                ) from exc
            print(
                "[startup] Artifact bootstrap failed; continuing with runtime fallback in API. "
                f"Error: {exc}"
            )
    else:
        print("[startup] Auto-build disabled (SKINCARES_AUTO_BUILD_ARTIFACTS=false).")

    _start_uvicorn()


if __name__ == "__main__":
    main()
