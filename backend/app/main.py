from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import EndpointMetadata, TestCase, RunTestsRequest, TestResult
from app.services.parser import parse_swagger
from app.services.llm_engine import generate_test_cases
from typing import List

app = FastAPI(title="Cognitest API", version="0.1.0")

# Setup CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "running", "service": "Cognitest Backend"}

# Placeholder for Phase 2: Upload & Parse
# [cite: 61] "After upload, the backend parses the Swagger/OpenAPI file"
@app.post("/upload-swagger", response_model=List[EndpointMetadata])
def upload_swagger(file: UploadFile = File(...)):
    # Read file content
    content = file.file.read()

    # Parse using the service we just wrote
    # Logic: "The backend parses the Swagger/OpenAPI file... and extracts endpoint paths" [cite: 61]
    try:
        metadata = parse_swagger(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse swagger file: {e}")

    return metadata

# Placeholder for Phase 2: Generate Tests
# [cite: 51] "Generate Tests button"
@app.post("/generate-tests", response_model=List[TestCase])
async def generate_tests(metadata: List[EndpointMetadata]):
    # Logic: "The backend constructs a strict prompt... [and] converts endpoint metadata"
    # Reference: Design Doc [cite: 80-81]
    test_cases = generate_test_cases(metadata)
    return test_cases

# Placeholder for Phase 3: Run Tests
# [cite: 53] "Run Tests button"
@app.post("/run-tests", response_model=List[TestResult])
async def run_tests(request: RunTestsRequest):
    # TODO: Implement Test Runner Logic
    return []