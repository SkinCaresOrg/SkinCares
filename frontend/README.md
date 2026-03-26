# Frontend Setup

- Run backend API first (local default `http://localhost:8000`).
- Frontend fetches from `VITE_API_BASE_URL` if set, otherwise `http://localhost:8000/api`.

## Local run

1. `cd ../deployment && uvicorn api.app:app --reload --host 0.0.0.0 --port 8000`
2. `cd ../frontend && npm install && npm run dev`

## Testing

- `cd frontend && npm run test`

## Production

- Set `VITE_API_BASE_URL` in environment or `.env` and run `npm run build`.
