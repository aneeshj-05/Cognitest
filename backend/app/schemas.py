from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal

# 1. Simplified Internal Representation
# Defined in design doc [cite: 67-72]
class EndpointMetadata(BaseModel):
    endpoint: str
    method: str
    hasRequestBody: bool
    requiresAuth: bool

# 2. Test Case JSON Schema
# Defined in design doc [cite: 87-98]
class TestCase(BaseModel):
    id: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    endpoint: str
    description: str
    headers: Optional[Dict[str, str]] = None
    pathParams: Optional[Dict[str, Any]] = None
    queryParams: Optional[Dict[str, Any]] = None
    body: Optional[Dict[str, Any]] = None
    expectedStatus: int

# 3. Execution Result Schema
# Defined in design doc [cite: 132-138]
class TestResult(BaseModel):
    id: str
    status: Literal["PASS", "FAIL", "ERROR"]
    expectedStatus: int
    actualStatus: Optional[int] = None
    responseTimeMs: Optional[int] = None
    responseBody: Optional[str] = None # Added for debugging

# Request payload for the Runner
# Defined in design doc [cite: 116-120]
class RunTestsRequest(BaseModel):
    baseUrl: str
    testCases: List[TestCase]