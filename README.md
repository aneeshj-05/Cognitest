# Cognitest - AI-Powered API Testing Platform

An intelligent API testing platform that uses Google Gemini AI to automatically generate and execute test cases from Swagger/OpenAPI specifications.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    Backend      │────▶│  Python Service │
│   (React/Vite)  │     │   (Node.js)     │     │    (FastAPI)    │
│   Port: 5173    │     │   Port: 5000    │     │   Port: 8000    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │     Newman      │
                        │  (Test Runner)  │
                        └─────────────────┘
```

## Flow

### Flow 1: Generate Test Cases
```
Swagger URL → FastAPI parses → Gemini AI generates tests → FastAPI builds Postman collection → Node stores it
```

### Flow 2: Execute Tests
```
Node loads collection → Newman runs tests → Report produced → FastAPI analyzes → Node stores summary
```

## Prerequisites

- **Node.js** v18+ 
- **Python** 3.10+
- **Google Gemini API Key** (Get from https://makersuite.google.com/app/apikey)

## Quick Start

### 1. Setup Python Service (FastAPI)

```bash
cd python-service
pip install -r requirements.txt
```

Edit `.env` and add your Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Start the service:
```bash
uvicorn src.main:app --reload --port 8000
```

### 2. Setup Backend (Node.js)

```bash
cd backend
npm install
```

The `.env` file should already be configured:
```env
PORT=5000
FASTAPI_URL=http://localhost:8000
STORAGE_DIR=./storage
```

Start the service:
```bash
npm run dev
```

### 3. Setup Frontend (React/Vite)

```bash
cd frontend
npm install
```

The `.env` file should already be configured:
```env
VITE_API_URL=http://localhost:5000
```

Start the service:
```bash
npm run dev
```

### 4. Access the Application

Open your browser and go to: **http://localhost:5173**

## Usage

1. Navigate to the **Testing** page
2. Enter a Swagger/OpenAPI URL (e.g., `https://petstore.swagger.io/v2/swagger.json`)
3. Click **Generate Test Cases** - AI will analyze the API and create test cases
4. Review and modify test cases as needed (toggle selection, delete)
5. Click **Run Tests** to execute the tests
6. View the test results summary

## API Endpoints

### Backend (Port 5000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/runs/generate` | Generate test cases from Swagger URL |
| POST | `/api/runs/update` | Update test cases for a run |
| POST | `/api/runs/:runId/execute` | Execute tests and get results |

### Python Service (Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/parse-swagger` | Parse Swagger/OpenAPI spec |
| POST | `/generate-tests` | Generate tests using Gemini AI |
| POST | `/analyze-report` | Analyze Newman test report |

## Project Structure

```
Cognitest/
├── frontend/              # React + Vite frontend
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API service layer
│   │   └── hooks/         # Custom React hooks
│   └── .env               # Frontend environment config
│
├── backend/               # Node.js + Express backend
│   ├── src/
│   │   ├── controllers/   # Request handlers
│   │   ├── modules/       # Business logic (runs, newman)
│   │   ├── routes/        # API routes
│   │   ├── clients/       # External service clients (FastAPI)
│   │   └── utils/         # Utility functions
│   ├── storage/           # File storage for collections/reports
│   └── .env               # Backend environment config
│
└── python-service/        # FastAPI + Gemini AI service
    ├── src/
    │   ├── main.py            # FastAPI app
    │   ├── swagger_parser.py  # Swagger parsing
    │   ├── gemini_generator.py # Gemini AI integration
    │   ├── postman_builder.py  # Postman collection builder
    │   └── report_analyzer.py  # Test report analyzer
    └── .env               # Python service config (Gemini API key)
```

## Troubleshooting

### CORS Issues
The backend already has CORS enabled. If you still face issues, ensure all services are running on the correct ports.

### Gemini API Errors
- Verify your API key is correctly set in `python-service/.env`
- Check your Gemini API quota at https://makersuite.google.com/

### Newman Errors
- Ensure the target API is accessible from your machine
- Check that the baseUrl in the Swagger spec is correct

## License

MIT

## run bat file

.\start-all.bat