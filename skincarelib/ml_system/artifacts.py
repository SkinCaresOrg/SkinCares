import json
import os
from pathlib import Path

import numpy as np


def find_project_root() -> Path:
    candidates = []

    configured_root = os.getenv("SKINCARES_PROJECT_ROOT")
    if configured_root:
        candidates.append(Path(configured_root).expanduser().resolve())

    github_workspace = os.getenv("GITHUB_WORKSPACE")
    if github_workspace:
        candidates.append(Path(github_workspace).expanduser().resolve())

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    here = Path(__file__).resolve()
    candidates.extend([here, *here.parents])

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)

        root = candidate if candidate.is_dir() else candidate.parent
        if (root / "artifacts").exists():
            return root

    raise FileNotFoundError(
        "Could not find project root (folder containing 'artifacts/'). "
        "Set SKINCARES_PROJECT_ROOT or run from repository root."
    )


def load_artifacts():
    root = find_project_root()

    vectors = np.load(root / "artifacts" / "product_vectors.npy")

    with open(root / "artifacts" / "product_index.json", "r", encoding="utf-8") as f:
        product_index = json.load(f)

    schema = None
    schema_path = root / "artifacts" / "feature_schema.json"
    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

    index_to_id = {v: k for k, v in product_index.items()}
    return vectors, product_index, index_to_id, schema
