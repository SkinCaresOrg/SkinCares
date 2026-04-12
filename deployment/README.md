# Deployment Skeleton

This folder captures deployment placeholders and run instructions for the project.

## Docker (local)
Build artifacts, then run the evaluation container with Compose:

```bash
python -m pip install -e .
python scripts/build_artifacts.py --schema-version v1
docker compose up --build
```

To run only API + frontend locally:

```bash
docker compose up --build api frontend
```

## Local staging DB (Supabase-like)

`docker compose up` now includes a local Postgres service (`db`) that initializes
the Supabase-like staging schema from:

- `deployment/sql/002_local_staging_supabase_schema.sql`

Connection settings used by the API container in compose:

- Host: `db`
- Port: `5432`
- DB: `skincares`
- User: `skincares`
- Password: `skincares`

Run full local stack:

```bash
docker compose up --build
```

If you change init SQL and need a fresh database initialization, reset the volume:

```bash
docker compose down -v
docker compose up --build
```

The API image no longer bakes in the full `data/` directory. In local compose, the required
product CSV is mounted as a read-only volume. You can also override the CSV path with:

```bash
PRODUCTS_CSV_PATH=/absolute/path/to/products_dataset_processed.csv
```

### API artifact bootstrap on startup

The API container now starts through `deployment.api.startup`, which checks for required
artifacts and rebuilds them if missing before launching `uvicorn`.

Startup checks for:
- `artifacts/product_vectors.npy`
- `artifacts/product_index.json`
- `artifacts/feature_schema.json`
- `artifacts/tfidf.joblib`
- `artifacts/faiss.index`

If `data/processed/products_with_signals.csv` is missing but
`data/processed/products_dataset_processed.csv` exists, it auto-creates a fallback
signals dataset and then runs:

```bash
python scripts/build_artifacts.py --schema-version v1
```

Optional environment controls:
- `SKINCARES_AUTO_BUILD_ARTIFACTS` (default: `true`) — set to `false` to skip auto-build.
- `SKINCARES_REQUIRE_ARTIFACTS` (default: `false`) — set to `true` to fail container startup if artifact bootstrap fails.
- `SKINCARES_ARTIFACT_SCHEMA_VERSION` (default: `v1`) — schema version passed to artifact build.

Local URLs:
- Frontend: `http://localhost:8080`
- API docs: `http://localhost:8000/docs`

The frontend container proxies `/api/*` to the API container, so app requests work at `http://localhost:8080`.

If you want a one-off run without Compose:

```bash
docker build -t skincares:latest .
docker run --rm skincares:latest
```

## Notes
- This is a lightweight skeleton for midterm readiness.
- Add an API server and logging before production deployment.

## API Contract Server (local)

Install API dependencies:

```bash
pip install -e .[api]
```

Run server:

```bash
uvicorn deployment.api:app --reload --host 0.0.0.0 --port 8000
```

Open docs:
- `http://localhost:8000/docs`
- `http://localhost:8000/openapi.json`

## Auth/API environment variables

When auth is enabled, backend startup requires:
- `SECRET_KEY`
- Database URL via `DATABASE_URL`

If you created Postgres through Vercel Integrations, Vercel usually injects one of:
- `POSTGRES_URL`
- `POSTGRES_PRISMA_URL`
- `POSTGRES_URL_NON_POOLING`

For a backend running on Render, copy the connection string value into Render env vars
as `DATABASE_URL` (or set one of the `POSTGRES_*` vars above).

Also set CORS on Render:
- `CORS_ALLOW_ORIGINS=https://skinscares.es,https://www.skinscares.es`
