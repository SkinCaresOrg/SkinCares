#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ARTIFACTS: list[tuple[str, Path]] = [
    ("feature_schema.json", ROOT / "artifacts" / "feature_schema.json"),
    ("product_index.json", ROOT / "artifacts" / "product_index.json"),
    ("product_vectors.npy", ROOT / "artifacts" / "product_vectors.npy"),
    ("tfidf.joblib", ROOT / "artifacts" / "tfidf.joblib"),
    ("manifest.json", ROOT / "artifacts" / "manifest.json"),
]

OPTIONAL_ARTIFACTS: list[tuple[str, Path]] = [
    ("faiss.index", ROOT / "artifacts" / "faiss.index"),
]

REQUIRED_DATASETS: list[tuple[str, Path]] = [
    (
        "products_with_signals.csv",
        ROOT / "data" / "processed" / "products_with_signals.csv",
    ),
]


def _all_required_present() -> bool:
    required_files = REQUIRED_ARTIFACTS + REQUIRED_DATASETS
    return all(local_path.exists() for _, local_path in required_files)


def _build_asset_url(
    supabase_url: str,
    bucket: str,
    prefix: str,
    remote_rel_path: str,
    public_bucket: bool,
) -> str:
    clean_base = supabase_url.rstrip("/")
    clean_prefix = prefix.strip("/")
    remote_part = remote_rel_path.strip("/")
    object_path = f"{clean_prefix}/{remote_part}" if clean_prefix else remote_part

    if public_bucket:
        return f"{clean_base}/storage/v1/object/public/{bucket}/{object_path}"
    return f"{clean_base}/storage/v1/object/{bucket}/{object_path}"


def _download_file(
    url: str,
    destination: Path,
    headers: dict[str, str],
    timeout_sec: int,
    retries: int = 3,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    attempt = 0
    while attempt < retries:
        attempt += 1
        response = requests.get(url, headers=headers, timeout=timeout_sec, stream=True)
        if response.status_code == 200:
            with destination.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output_file.write(chunk)
            return

        if attempt >= retries:
            raise RuntimeError(f"HTTP {response.status_code} downloading {url}")

        time.sleep(min(2**attempt, 5))


def _download_assets(
    items: Iterable[tuple[str, Path]],
    *,
    supabase_url: str,
    bucket: str,
    prefix: str,
    public_bucket: bool,
    headers: dict[str, str],
    timeout_sec: int,
    required: bool,
) -> bool:
    all_ok = True

    for remote_rel, local_path in items:
        if local_path.exists():
            print(f"[skip] {local_path} already exists")
            continue

        asset_url = _build_asset_url(
            supabase_url=supabase_url,
            bucket=bucket,
            prefix=prefix,
            remote_rel_path=remote_rel,
            public_bucket=public_bucket,
        )

        print(f"[download] {remote_rel} -> {local_path}")
        try:
            _download_file(
                url=asset_url,
                destination=local_path,
                headers=headers,
                timeout_sec=timeout_sec,
            )
        except Exception as exc:
            all_ok = False
            level = "error" if required else "warn"
            print(f"[{level}] Failed to download {remote_rel}: {exc}")
            if required:
                break

    return all_ok


def main() -> int:
    if _all_required_present():
        print("All required assets already exist. Skipping download.")
        return 0

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()
    artifacts_bucket = os.getenv(
        "SUPABASE_ARTIFACTS_BUCKET", "skincares-artifacts"
    ).strip()
    datasets_bucket = os.getenv(
        "SUPABASE_DATASETS_BUCKET", "skincares-datasets"
    ).strip()
    artifacts_prefix = os.getenv("SUPABASE_ARTIFACTS_PREFIX", "v2").strip()
    datasets_prefix = os.getenv("SUPABASE_DATASETS_PREFIX", "v2").strip()
    timeout_sec = int(os.getenv("SUPABASE_DOWNLOAD_TIMEOUT", "120"))
    public_bucket = os.getenv("SUPABASE_ASSETS_PUBLIC", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }

    if not supabase_url:
        print("Missing SUPABASE_URL and required assets are not present.")
        return 1

    headers: dict[str, str] = {}
    if not public_bucket:
        if not supabase_key:
            print("Missing SUPABASE_KEY for private bucket download.")
            return 1
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }

    print(
        "Bootstrapping artifacts from "
        f"bucket '{artifacts_bucket}' prefix '{artifacts_prefix}' "
        f"(public={public_bucket})"
    )

    artifacts_ok = _download_assets(
        REQUIRED_ARTIFACTS,
        supabase_url=supabase_url,
        bucket=artifacts_bucket,
        prefix=artifacts_prefix,
        public_bucket=public_bucket,
        headers=headers,
        timeout_sec=timeout_sec,
        required=True,
    )
    if not artifacts_ok:
        print("Required artifacts could not be downloaded.")
        return 1

    _download_assets(
        OPTIONAL_ARTIFACTS,
        supabase_url=supabase_url,
        bucket=artifacts_bucket,
        prefix=artifacts_prefix,
        public_bucket=public_bucket,
        headers=headers,
        timeout_sec=timeout_sec,
        required=False,
    )

    print(
        "Bootstrapping datasets from "
        f"bucket '{datasets_bucket}' prefix '{datasets_prefix}' "
        f"(public={public_bucket})"
    )

    datasets_ok = _download_assets(
        REQUIRED_DATASETS,
        supabase_url=supabase_url,
        bucket=datasets_bucket,
        prefix=datasets_prefix,
        public_bucket=public_bucket,
        headers=headers,
        timeout_sec=timeout_sec,
        required=True,
    )
    if not datasets_ok:
        print("Required datasets could not be downloaded.")
        return 1

    print("Asset bootstrap complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
