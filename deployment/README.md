# Deployment Skeleton

This folder captures deployment placeholders and run instructions for the project.

## Docker (local)
Build artifacts, then run the evaluation container with Compose:

```bash
python -m pip install -e .
python scripts/build_artifacts.py --schema-version v1
docker compose up --build
```

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