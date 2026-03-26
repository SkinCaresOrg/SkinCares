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

## Hosted deployment (no server): Vercel + Render

This repo is ready for:
- Frontend on Vercel from `frontend/`
- API on Render from repo root using `render.yaml`

### Render (API)

1. Connect this GitHub repository in Render.
2. Create a Web Service using `render.yaml`.
3. Confirm:
	- Build command: `pip install -e .[api]`
	- Start command: `uvicorn deployment.api:app --host 0.0.0.0 --port $PORT`
4. Set `CORS_ALLOW_ORIGINS` to your frontend domains.

### Vercel (Frontend)

1. Import the same repository in Vercel.
2. Set Root Directory to `frontend`.
3. Add environment variable:
	- `VITE_API_BASE_URL=https://api.skinscares.es/api`
4. Deploy.

### GoDaddy DNS

- Point `@` and `www` to Vercel (values shown in Vercel domains setup).
- Point `api` to your Render backend host (CNAME).
