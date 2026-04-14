# SkinCares

SkinCares is a skincare recommendation system that combines:

- ingredient- and profile-aware ranking,
- feedback-aware ML updates, and
- a FastAPI backend with a React frontend.

It includes local experimentation tooling, artifact generation for retrieval/ranking, and deployment-oriented API wiring.

## Repository Structure

## Key Markdown Documentation Files

- `QUICK_START.md`: Fast instructions for getting up and running with ML feedback and core features.
- `IMPLEMENTATION_SUMMARY.md`: High-level summary of the system’s implementation and main design choices.
- `ADAPTIVE_MODEL_SELECTION.md`: Details on adaptive model selection strategies used in the ML system.
- `COMPLETION_REPORT.md`: Report on project completion status, deliverables, and evaluation.


```text
SkinCares/
├── skincarelib/            # Core recommendation and ML modules
├── deployment/             # FastAPI app, DB models, SQL migrations, Docker API image
├── frontend/               # React + Vite frontend
├── scripts/                # Utility scripts (artifact build, manifest verify, seeding, eval)
├── data/processed/         # Processed datasets (including products_with_signals.csv)
├── artifacts/              # Generated model/retrieval artifacts (mostly ignored in git)
├── docs/                   # Architecture and integration docs
├── tests/                  # Python tests
├── docker-compose.yml
└── setup.py
```

## Quick Start (Local)

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
```

### 2) Run backend API

```bash
uvicorn deployment.api:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI docs: `http://localhost:8000/docs`

### 3) Run frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

## Data and Artifacts

- Source data for API/product metadata lives in `data/processed/`.
- `products_with_signals.csv` is kept in the repo for reproducibility.
- Large generated binaries (for example FAISS indexes) should stay out of git.

Current artifact schema version: `v2`.

Build artifacts manually:

```bash
python scripts/build_artifacts.py --schema-version v2
```

If `faiss` is not installed, the build still succeeds and skips `artifacts/faiss.index`.
Install FAISS when you need ANN/dupe retrieval:

```bash
pip install faiss-cpu
```

Verify artifact manifest:

```bash
python scripts/verify_manifest.py
```

## Docker

Run API + frontend with Docker Compose:

```bash
docker compose up --build api frontend
```

Run evaluation container:

```bash
docker compose up --build evaluation
```

## Development

Run Python tests:

```bash
python -m pytest tests --disable-warnings --maxfail=1
```

Run lint:

```bash
ruff check .
```

Run frontend tests:

```bash
cd frontend && npm test
```

Install and run pre-commit hooks:

```bash
pre-commit install --hook-type pre-commit --hook-type pre-push
pre-commit install-hooks
pre-commit run --all-files
```

## Configuration Notes

- Copy `.env.example` to `.env` and set required values.
- For database-backed auth/persistence, set `DATABASE_URL` and `SECRET_KEY`.
- API product CSV can be overridden with `PRODUCTS_CSV_PATH`.

## Documentation

- Main docs index: `docs/README.md`
- Deployment notes: `deployment/README.md`
- ML feedback quickstart: `QUICK_START.md`

## License

MIT License (see `LICENSE`).