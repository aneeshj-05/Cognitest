from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict

from src.swagger_parser import parse_swagger
from src.gemini_generator import generate_testcases_from_gemini
from src.postman_builder import build_postman_collection
from src.report_analyzer import analyze_report

app = FastAPI(title="FastAPI Worker - Swagger → Gemini → Newman")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SwaggerReq(BaseModel):
    swaggerUrl: str

class SwaggerSpecReq(BaseModel):
    spec: Dict[str, Any]

class GenerateReq(BaseModel):
    parsed: Dict[str, Any]

class ReportReq(BaseModel):
    report: Dict[str, Any]


@app.get("/health")
def health():
    return {"status": "ok", "service": "python-service"}


@app.post("/parse-swagger")
async def parse_swagger_api(req: SwaggerReq):
    parsed = await parse_swagger(req.swaggerUrl)
    return parsed


@app.post("/parse-swagger-spec")
async def parse_swagger_spec(req: SwaggerSpecReq):
    """Parse a Swagger spec directly (for file uploads)"""
    spec = req.spec
    
    base_url = ""
    if "servers" in spec and spec["servers"]:
        base_url = spec["servers"][0]["url"]
    elif "host" in spec:
        # Swagger 2.0 format
        scheme = spec.get("schemes", ["https"])[0]
        base_url = f"{scheme}://{spec['host']}{spec.get('basePath', '')}"
    
    endpoints = []
    for path, methods in spec.get("paths", {}).items():
        for method, details in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                endpoints.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": details.get("summary", "")
                })
    
    return {
        "baseUrl": base_url,
        "endpoints": endpoints
    }


@app.post("/generate-tests")
async def generate_tests(req: GenerateReq):
    testcases = await generate_testcases_from_gemini(req.parsed)
    collection = build_postman_collection(req.parsed, testcases)

    return {
        "testcases": testcases,
        "collection": collection
    }


@app.post("/analyze-report")
def analyze(req: ReportReq):
    return analyze_report(req.report)