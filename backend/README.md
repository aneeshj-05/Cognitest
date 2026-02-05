# Backend (FastAPI)

This repository uses FastAPI for the backend implementation. The previous Node/Express backend files were removed to avoid redundancy — if you need them later, they remain in Git history.

Run the FastAPI app locally:

```bash
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API entrypoint: `GET /` (health check).

Frontend: the frontend lives in the `frontend/` folder. Run it separately with `npm install` and `npm run dev`.

Notes:
- `.env` files (if present) may contain secrets — ensure they are not committed.
- Node/Express files under `backend/` were removed because the project standard is FastAPI.
