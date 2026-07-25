# Cognitest Backend API

uv run uvicorn src.main:app --port 5000

Backend API for Cognitest - migrated from Node.js/Express to Python/FastAPI.

## Features

- 🔐 **Authentication**: JWT-based user authentication with bcrypt password hashing
- 🗄️ **Database**: PostgreSQL with Prisma ORM
- 🚪 **API Gateway**: HTTP proxy to forward requests to target services
- 🌐 **CORS**: Configurable Cross-Origin Resource Sharing
- 📝 **Auto-Documentation**: Interactive API docs at `/docs`

## Tech Stack

- **Framework**: FastAPI 0.115.0
- **Database**: PostgreSQL with Prisma Client Python
- **Authentication**: JWT tokens with python-jose, bcrypt password hashing
- **Server**: Uvicorn (ASGI server)

## Prerequisites

- Python 3.10 or higher
- PostgreSQL database
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager (recommended)
- Node.js (for Prisma CLI)

## Installation

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Create Virtual Environment & Install Dependencies

```bash
cd /home/aneeshj/Cognitest/backend

# Create virtual environment and install all dependencies in one command
uv sync
```

This will:
- Create a `.venv` virtual environment
- Install all dependencies from `pyproject.toml`
- Lock dependencies in `uv.lock`

### 3. Generate Prisma Client

```bash
# Activate virtual environment
source .venv/bin/activate

# Generate Prisma Client for Python
## Create a .env file in the backend folder:
  DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
###Apply Pending Changes: 
  uv run prisma migrate dev
###Generate Prisma Client: 
  uv run prisma generate

```

### 4. Configure Environment Variables

The `.env` file should contain:

```env
# Server
PORT=5000
NODE_ENV=development

# Database
DATABASE_URL="postgresql://user:password@host:port/database"

# JWT
JWT_SECRET=your-secret-key-here

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Gateway/Proxy
TARGET_SERVICE_URL=http://localhost:6000
```

### 5. Run Database Migrations

```bash
prisma migrate deploy
```

## Using uv for Package Management

Now that the project uses `uv`, you can manage dependencies much faster than with `pip`:

### Add a new dependency
```bash
uv add package-name
```

### Add a dev dependency
```bash
uv add --dev package-name
```

### Remove a dependency
```bash
uv remove package-name
```

### Upgrade dependencies
```bash
uv sync --upgrade
```

### Install from pyproject.toml
```bash
uv sync
```

All dependency changes are automatically recorded in `pyproject.toml` and `uv.lock`.

## Running the Server

### Development Mode (with auto-reload)

```bash
# Recommended (ensures you use the project environment)
uv run uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload

# Windows alternative (explicitly uses the local .venv)
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload
```

### Production Mode

```bash
uvicorn src.main:app --host 0.0.0.0 --port 5000 --workers 4
```

## API Endpoints

### Health Check
- `GET /api/v1/health` - Check API health status

### Authentication
- `POST /api/v1/auth/signup` - Register a new user
- `POST /api/v1/auth/login` - Login and get JWT token

### Gateway/Proxy
- `ALL /api/v1/gateway/*` - Proxy requests to TARGET_SERVICE_URL

## Interactive API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc

## Project Structure

```
backend/
├── src/
│   ├── config/           # Configuration and settings
│   │   ├── settings.py   # Environment variables and app settings
│   │   └── database.py   # Database connection management
│   ├── middleware/       # Custom middleware
│   │   ├── auth_middleware.py    # JWT authentication
│   │   └── error_handler.py      # Global error handling
│   ├── routers/          # API route handlers
│   │   ├── auth.py       # Authentication routes
│   │   ├── health.py     # Health check route
│   │   └── gateway.py    # Proxy gateway routes
│   ├── schemas/          # Pydantic models for validation
│   │   └── auth.py       # Auth request/response schemas
│   ├── services/         # Business logic
│   │   └── auth_service.py   # Auth service (signup, login)
│   └── main.py           # FastAPI application entry point
├── prisma/
│   └── schema.prisma     # Database schema
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables
└── README.md            # This file
```

## Database Schema

The application uses the existing Prisma schema with the following models:
- **User**: User accounts
- **Workspace**: User workspaces
- **WorkspaceMember**: Workspace membership
- **Project**: Projects within workspaces
- **ProjectMember**: Project membership

## Migration Notes

### From Node.js to FastAPI

This backend was migrated from Node.js/Express to Python/FastAPI while maintaining:
- ✅ Same database schema (no migrations needed)
- ✅ Same API endpoints and routes
- ✅ Same authentication flow (JWT with bcrypt)
- ✅ Same CORS configuration
- ✅ Same proxy/gateway functionality
- ✅ Same environment variables

### Key Differences

| Aspect | Node.js | FastAPI |
|--------|---------|---------|
| Framework | Express.js | FastAPI |
| Server | Node.js | Uvicorn (ASGI) |
| ORM | Prisma JS | Prisma Python |
| JWT | jsonwebtoken | python-jose |
| Password | bcrypt | passlib[bcrypt] |
| Proxy | http-proxy-middleware | httpx |
| Validation | Manual | Pydantic (automatic) |

## Testing

### Contract-testing engine (under src/modules/generator)

This repo includes a contract-testing engine under `src/modules/generator`.

Run only the contract-testing unit tests from the backend repo root:

```bash
pytest -q src/modules/test/contract
```

Run the contract-testing API (as a separate FastAPI app):

```bash
uvicorn src.modules.generator.engines.contract.contract_app:app --reload --port 8001
```

Test the endpoints using curl:

```bash
# Health check
curl http://localhost:5000/api/v1/health

# Signup
curl -X POST http://localhost:5000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "Test User",
    "passcode": "password123",
    "company": "Test Co"
  }'

# Login
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "passcode": "password123"
  }'
```

## Troubleshooting

### Prisma Client Not Found

If you get `ModuleNotFoundError: No module named 'prisma'`:
```bash
pip install prisma
prisma generate
```

### Database Connection Error

Verify your `DATABASE_URL` in `.env` is correct and the database is accessible.

### Import Errors

Make sure you're running commands from the `backend` directory and the virtual environment is activated.

## License

Private - Cognitest Project
uv run uvicorn src.main:app --reload --port 5000 