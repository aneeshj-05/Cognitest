from pydantic import BaseModel
from typing import List, Optional, Any

class AuthConfig(BaseModel):
    """Authentication configuration for fuzzing protected endpoints."""
    type: str = "none"            # "bearer", "apiKey", "none"
    login_url: str | None = None  # URL to call for JWT acquisition
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    token: str | None = None      # pre-provided JWT token
    token_path: str = "token"     # JSON path in login response (e.g. "data.accessToken")
    key_name: str = "Authorization"  # header name for apiKey
    key_in: str = "header"        # "header" or "query"


class FuzzGenerateRequest(BaseModel):
    """Request body for POST /generator/fuzz/{project_id}."""
    spec_id: str
    base_url: str | None = None           # override project baseUrl
    run_tests: bool = True                 # also execute via Newman?
    use_ai: bool = True                    # use AI for test generation?
    auth: AuthConfig | None = None         # auth configuration
    delay_ms: int = 200                    # delay between requests (rate control)


class FuzzTestCaseOut(BaseModel):
    """Single fuzz test case returned by the engine."""
    id: str
    name: str
    fuzz_type: str
    endpoint_path: str
    method: str
    headers: dict = {}
    body: Any = None
    query_params: dict = {}
    expected_status: int = 400
    expected_behavior: str = ""
    description: str | None = None
    requires_auth: bool = False


class FuzzFinding(BaseModel):
    """Single anomaly detected during execution — with security classification."""
    test_case_id: str
    test_name: str
    fuzz_type: str
    status_code: int
    response_time_ms: int
    crashed: bool
    anomaly_detected: bool
    anomaly_details: str | None = None
    # Structured classification
    classification: str = "NORMAL"
    severity: str = "INFO"
    expected_status: int = 400


class FuzzSummary(BaseModel):
    """Aggregate summary of a fuzz run."""
    total: int
    passed: int
    failed: int
    crashed: int
    anomalies_detected: int


class SecuritySummaryOut(BaseModel):
    """Structured security summary."""
    total_tests: int = 0
    total_vulnerabilities: int = 0
    severity_breakdown: dict[str, int] = {}
    classification_breakdown: dict[str, int] = {}
    risk_level: str = "SAFE"


class FuzzRunResponse(BaseModel):
    """Full response from the fuzz pipeline."""
    project_id: str
    run_id: str | None = None
    test_cases: List[FuzzTestCaseOut]
    findings: List[FuzzFinding] = []
    summary: FuzzSummary
    security_summary: SecuritySummaryOut | None = None
    executed: bool = False
