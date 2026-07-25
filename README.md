# Cognitest

Cognitest is an internal platform that provides a FastAPI-based backend and a modern TypeScript/Vite frontend for managing workspaces, projects, and members. It includes JWT authentication, a PostgreSQL database (Prisma schema), and a proxy/gateway for forwarding requests to target services. This repository holds both the Backend (FastAPI + Prisma Python) and the Frontend (TypeScript + Vite/React) components.

## Quick links
- Backend: `Backend/` (FastAPI)
- Frontend: `frontend/` (Vite + TypeScript)
- Backend interactive docs (when running): `http://localhost:5000/docs` (Swagger) and `/redoc`

## Stack
- Language(s): Python (backend), TypeScript (frontend)
- Framework / runtime:
  - Backend: FastAPI (Uvicorn ASGI)
  - Frontend: Vite + React/TypeScript
- Notable libraries:
  - Backend: FastAPI, Uvicorn, Pydantic, Prisma (Python), python-jose (JWT), passlib[bcrypt]
  - Frontend: (standard Vite/React/TypeScript stack — see `frontend/package.json`)

## What this repository contains
```
Backend/         # FastAPI backend (src/ contains app code, prisma/ contains schema)
frontend/        # Vite + TypeScript frontend application
README.md        # This file
.gitignore
```

How it fits together: the frontend talks to the backend API (configured via VITE_API_URL / VITE env). The backend exposes REST endpoints (auth, health, gateway/proxy) and uses Prisma + PostgreSQL for persistence. The backend also contains a contract-testing engine under `src/modules/generator`.

## Features
- JWT-based authentication (signup/login) with bcrypt/passlib hashing
- PostgreSQL database managed by Prisma
- API gateway / proxy endpoints to forward requests to TARGET_SERVICE_URL
- Interactive API docs via FastAPI (/docs, /redoc)
- Contract-testing engine (unit tests + a small FastAPI app) under `src/modules/generator`

## Getting started (shortest path)
Prerequisites:
- Git
- Python 3.10+
- Node.js (for Prisma CLI and frontend)
- PostgreSQL

Clone the repo:

```bash
git clone https://github.com/aneeshj-05/Cognitest.git
cd Cognitest
```

### Backend setup
1. Change into the backend folder and install dependencies (the project uses `uv` by recommendation but you can use pip/env too):

```bash
cd Backend
# If you use uv (recommended):
# install uv first (see https://astral.sh/uv/) then:
uv sync
# or with virtualenv + pip:
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment variables in `Backend/.env` (or export them):

```env
PORT=5000
NODE_ENV=development
DATABASE_URL="postgresql://user:password@host:port/database"
JWT_SECRET=your-secret-key-here
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
TARGET_SERVICE_URL=http://localhost:6000
```

3. Generate Prisma client (requires Node.js and the Prisma CLI):

```bash
# from Backend/
source .venv/bin/activate
uv run prisma migrate dev    # applies migrations
uv run prisma generate       # generates the Python Prisma client
```

4. Run the backend (development):

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
# or
python -m uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
```

Production example:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 5000 --workers 4
```

### Frontend setup
1. Change into frontend and install deps:

```bash
cd ../frontend
npm install
```

2. Set VITE_API_URL in `.env` or your shell to point to the backend API, e.g. `http://localhost:5000/api/v1`.

3. Run frontend in development:

```bash
npm run dev
```

4. Build for production:

```bash
npm run build
npm run preview   # optional to test the build locally
```

Front-end production gates (lint/typecheck/test/build) are described in `frontend/README.md` and enforced by scripts:
- `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`, `npm run check`

## API (high level)
- Health: GET /api/v1/health
- Auth: POST /api/v1/auth/signup, POST /api/v1/auth/login
- Gateway/Proxy: ALL /api/v1/gateway/* -> forwarded to TARGET_SERVICE_URL

For exact routes and request/response schemas, run the backend and visit `/docs`.

## Testing
- Backend unit/contract tests (example contract tests):

```bash
# from Backend/
pytest -q src/modules/test/contract
```

- Run contract-testing API (separate FastAPI app):

```bash
uvicorn src.modules.generator.engines.contract.contract_app:app --reload --port 8001
```

- Frontend tests / E2E: see `frontend/package.json` scripts (e.g. `npm run test`, `npm run test:e2e`).

## Troubleshooting
- Prisma client not found:

```bash
pip install prisma
prisma generate
```

- Database connection errors: verify `DATABASE_URL` and that PostgreSQL is reachable.
- Import errors: ensure you're running commands from `Backend/` and have activated the virtual environment.

## Project structure (representative)
```
Backend/
  src/
    config/           # settings and DB connection
    middleware/       # auth, error handling
    routers/          # auth, health, gateway routes
    schemas/          # pydantic models
    services/         # business logic (auth_service, etc.)
    main.py           # FastAPI app entry
  prisma/
    schema.prisma
frontend/
  (Vite + TS app)
```

## Environment variables (summary)
- DATABASE_URL: PostgreSQL connection string
- JWT_SECRET: secret for signing tokens
- CORS_ORIGINS: comma-separated list of allowed origins
- VITE_API_URL: frontend -> backend base URL
- TARGET_SERVICE_URL: backend gateway proxy target

## Contributing
This repository is currently Private. If you plan to contribute:
- Follow the frontend production gates and tests before opening PRs.
- Keep backend schema changes coordinated (Prisma migrations + `prisma generate`).

## License
Private - Cognitest Project

## Contact / Owner
Repository: aneeshj-05/Cognitest


---

For more implementation details, see `Backend/README.md` and `frontend/README.md`.
