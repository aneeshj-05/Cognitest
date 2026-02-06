# CogniTest - Project Flow Documentation

## Overview
CogniTest is an AI-powered API testing platform that automatically generates and executes test cases from Swagger/OpenAPI specifications using Google Gemini AI.

## Architecture Components

### 1. **Frontend** (React + Vite - Port 5173)
- User interface for uploading Swagger specs
- Test case management (edit/delete tests)
- Progressive results display
- Real-time batch execution progress

### 2. **Backend** (Node.js + Express - Port 5000)
- API orchestration layer
- File storage management
- Newman test runner integration
- Batch execution controller

### 3. **Python Service** (FastAPI - Port 8000)
- Swagger/OpenAPI parser
- Google Gemini AI integration
- Postman collection builder
- Newman report analyzer

### 4. **Core Services**
- **Google Gemini AI**: Generates intelligent test cases
- **Newman**: Executes Postman collections and generates reports
- **File Storage**: Stores collections, reports, and summaries

---

## Complete Flow Diagram

See [project-flow.mmd](./project-flow.mmd) for the detailed Mermaid diagram.

---

## Two Main Workflows

### **FLOW 1: Generate Test Cases** 

```
┌─────────────┐
│    User     │ Provides Swagger URL or uploads JSON file
└──────┬──────┘
       ↓
┌─────────────────────────────────────────────────────┐
│              Frontend (React)                        │
│  - Accepts URL or file upload                       │
│  - Validates input                                  │
└──────┬──────────────────────────────────────────────┘
       ↓
       POST /api/runs/generate or /generate-from-spec
       ↓
┌─────────────────────────────────────────────────────┐
│          Backend (Node.js)                          │
│  - Creates unique runId (UUID)                      │
│  - Forwards request to Python service               │
└──────┬──────────────────────────────────────────────┘
       ↓
       POST /parse-swagger or /parse-swagger-spec
       ↓
┌─────────────────────────────────────────────────────┐
│       Python Service (FastAPI)                      │
│  Step 1: Parse Swagger                              │
│    - SwaggerParser extracts:                        │
│      * Base URL                                     │
│      * All endpoints (method + path)                │
│      * Endpoint summaries                           │
└──────┬──────────────────────────────────────────────┘
       ↓
       POST /generate-tests with parsed data
       ↓
┌─────────────────────────────────────────────────────┐
│       Python Service (FastAPI)                      │
│  Step 2: Generate Tests                             │
│    - TestGenerator creates AI prompt                │
│    - Sends to Google Gemini AI                      │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│         Google Gemini AI                            │
│  - Analyzes API endpoints                           │
│  - Generates comprehensive test cases:              │
│    * Positive tests (success scenarios)             │
│    * Negative tests (failure scenarios)             │
│    * Authentication flows                           │
│    * Priority ordering (auth first)                 │
└──────┬──────────────────────────────────────────────┘
       ↓
       Returns AI-generated test cases
       ↓
┌─────────────────────────────────────────────────────┐
│       Python Service (FastAPI)                      │
│  Step 3: Build Collection                           │
│    - PostmanBuilder creates Postman collection:     │
│      * Adds authentication handling                 │
│      * Token capture from login responses           │
│      * Authorization headers for protected routes   │
│      * Request bodies with sample data              │
│      * Test assertions                              │
└──────┬──────────────────────────────────────────────┘
       ↓
       Returns {testcases, collection}
       ↓
┌─────────────────────────────────────────────────────┐
│          Backend (Node.js)                          │
│  - Stores collection as JSON file:                  │
│    storage/collections/{runId}.json                 │
│  - Returns to frontend:                             │
│    {runId, testcases, message}                      │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│              Frontend (React)                        │
│  - Displays test cases in editable table           │
│  - User can:                                        │
│    * View all generated tests                       │
│    * Edit test details                              │
│    * Delete unwanted tests                          │
│    * Select/deselect tests                          │
└─────────────────────────────────────────────────────┘
```

---

### **FLOW 2: Execute Tests**

```
┌─────────────┐
│    User     │ Clicks "Run Tests" button
└──────┬──────┘
       ↓
┌─────────────────────────────────────────────────────┐
│              Frontend (React)                        │
│  Step 1: Get current collection                     │
│    GET /api/runs/{runId}/collection                 │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│          Backend (Node.js)                          │
│  - Loads collection from storage                    │
│  - Returns collection JSON                          │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│              Frontend (React)                        │
│  Step 2: Apply user edits                           │
│    - Filters deleted tests                          │
│    - Creates updated collection                     │
│    PUT /api/runs/{runId}/testcases                  │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│          Backend (Node.js)                          │
│  - Updates stored collection                        │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│              Frontend (React)                        │
│  Step 3: Execute in batches                         │
│    POST /api/runs/{runId}/execute-batch             │
│    {batchIndex: 0, batchSize: 10}                   │
│                                                     │
│  Repeats for each batch until complete              │
└──────┬──────────────────────────────────────────────┘
       ↓
       For each batch:
       ↓
┌─────────────────────────────────────────────────────┐
│          Backend (Node.js)                          │
│  Step 4: Run batch with Newman                      │
│    - Loads collection                               │
│    - Extracts batch of 10 tests                     │
│    - Creates batch collection                       │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│            Newman Test Runner                       │
│  - Executes HTTP requests to target API            │
│  - Runs test assertions                             │
│  - Captures responses and timings                   │
│  - Generates reports:                               │
│    * JSON report (machine-readable)                 │
│    * HTML report (human-readable)                   │
│  - Stores in storage/reports/                       │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│          Backend (Node.js)                          │
│  Step 5: Analyze results                            │
│    POST /analyze-report to Python service           │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│       Python Service (FastAPI)                      │
│  ReportAnalyzer processes Newman report:            │
│    - Counts total requests                          │
│    - Identifies passed tests                        │
│    - Identifies failed tests with messages          │
│    - Captures response times                        │
│    - Creates summary object                         │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│          Backend (Node.js)                          │
│  - Stores summary in storage/summaries/             │
│  - Returns batch results with progress:             │
│    {                                                │
│      summary: {total, passed, failed, endpoints},   │
│      progress: {currentBatch, totalBatches},        │
│      isComplete: true/false                         │
│    }                                                │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────┐
│              Frontend (React)                        │
│  Step 6: Display results                            │
│    - Shows batch-by-batch progress                  │
│    - Aggregates results across all batches          │
│    - Displays:                                      │
│      * Total/Passed/Failed counts                   │
│      * Success endpoints with response times        │
│      * Failed endpoints with error messages         │
│    - Updates UI progressively                       │
└──────┬──────────────────────────────────────────────┘
       ↓
┌─────────────┐
│    User     │ Views comprehensive test results
└─────────────┘
```

---

## Key Features

### 1. **AI-Powered Test Generation**
- Leverages Google Gemini AI (gemini-2.5-flash model)
- Generates both positive and negative test cases
- Intelligently orders tests (authentication first)
- Creates realistic test scenarios

### 2. **Smart Authentication Handling**
- Automatically identifies auth endpoints
- Captures tokens from login responses
- Injects Bearer tokens into protected requests
- Supports various token response formats

### 3. **Batch Execution**
- Executes 10 tests per batch
- Prevents timeout issues
- Progressive result updates
- Shows real-time progress

### 4. **Flexible Input**
- Accepts Swagger/OpenAPI URL
- Supports JSON file upload
- Handles Swagger 2.0 and OpenAPI 3.0 formats

### 5. **Comprehensive Reporting**
- JSON reports for automation
- HTML reports for manual review
- Detailed success/failure analysis
- Response time metrics

---

## Data Storage Structure

```
storage/
├── collections/
│   ├── {runId-1}.json          # Postman collection with test cases
│   ├── {runId-2}.json
│   └── ...
├── reports/
│   ├── {runId-1}.json          # Newman JSON report
│   ├── {runId-1}.html          # Newman HTML report
│   ├── {runId-1-batch-0}.json  # Batch reports
│   └── ...
└── summaries/
    ├── {runId-1}.json          # Analyzed summary
    └── ...
```

---

## API Endpoints

### Backend (Node.js - Port 5000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/runs/generate` | Generate tests from Swagger URL |
| POST | `/api/runs/generate-from-spec` | Generate tests from uploaded JSON |
| GET | `/api/runs/:runId/collection` | Get stored collection |
| PUT | `/api/runs/:runId/testcases` | Update collection with edits |
| POST | `/api/runs/:runId/execute-batch` | Execute batch of tests |
| GET | `/api/runs/:runId/test-count` | Get total test count |

### Python Service (FastAPI - Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/parse-swagger` | Parse Swagger from URL |
| POST | `/parse-swagger-spec` | Parse uploaded Swagger JSON |
| POST | `/generate-tests` | Generate tests using Gemini AI |
| POST | `/analyze-report` | Analyze Newman report |

---

## Technologies Used

### Frontend
- **React 19**: UI framework
- **Vite**: Build tool and dev server
- **TailwindCSS**: Styling
- **Lucide React**: Icons

### Backend
- **Node.js**: Runtime
- **Express**: Web framework
- **Newman**: Postman collection runner
- **Axios**: HTTP client
- **UUID**: Unique ID generation

### Python Service
- **FastAPI**: Web framework
- **Uvicorn**: ASGI server
- **Google Generative AI**: Gemini AI SDK
- **Httpx**: Async HTTP client

---

## Environment Configuration

### Backend (.env)
```env
PORT=5000
FASTAPI_URL=http://localhost:8000
STORAGE_DIR=./storage
```

### Python Service (.env)
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:5000
```

---

## Improvements Over Original Sketch

1. **Added Batch Execution Flow**: Original sketch didn't show the batch processing mechanism
2. **Detailed Storage Layer**: Shows all three storage categories (collections, reports, summaries)
3. **Step-by-Step Numbering**: Each step is numbered for easy tracking (1-30)
4. **Authentication Flow**: Explicitly shows token capture and injection
5. **Bi-directional Communication**: Clear request/response flows
6. **Component Breakdown**: Shows internal services (Parser, Generator, Builder, Analyzer)
7. **Color-Coded Components**: Visual distinction between layers
8. **Progress Tracking**: Shows how batch progress is communicated to user
9. **File Operations**: Explicit read/write operations to storage

---

## Generated: February 6, 2026
