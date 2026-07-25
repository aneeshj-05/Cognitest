from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict, Union
from datetime import datetime

class Spec(BaseModel):
    originalName: Optional[str] = None
    baseUrl: Optional[str] = None

class SpecInfo(BaseModel):
    id: str
    file_type: str
    version: str
    file_url: str
    uploadedBy: Optional[str] = None
    createdAt: datetime
    
class SpecTestResult(BaseModel):
    endpointId: Optional[str] = None
    testCaseId: str
    method: str
    endpoint: str
    name: str
    expected: Union[int, List[int], str]
    actual: Union[int, str]
    message: Optional[str] = None

class SpecTestResultsResponse(BaseModel):
    passed: List[SpecTestResult]
    failed: List[SpecTestResult]

class LastRun(BaseModel):
    executedAt: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    categorySummary: Optional[Dict[str, Any]] = None

class AssignUserRoleRequest(BaseModel):
    roleName: str

class StreamTicketRequest(BaseModel):
    base_url: str
    case_ids: Optional[str] = None
    manual_token: Optional[str] = None
    register_url: Optional[str] = None
    login_url: Optional[str] = None
    auth_email: Optional[str] = None
    auth_password: Optional[str] = None
    admin_token: Optional[str] = None

class StreamTicketResponse(BaseModel):
    ticket: str
    description: Optional[str] = None
    workspaceId: Optional[str] = None

class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None
    workspaceId: str

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    workspaceId: str
    tenantId: Optional[str] = ""
    createdAt: datetime
    updatedAt: datetime

class ProjectMetaResponse(ProjectResponse):
    hasSpec: bool
    spec: Optional[Spec] = None
    lastRun: Optional[LastRun] = None
    # Dynamic stats from DB
    testsRun: Optional[int] = None
    testsPassed: Optional[int] = None
    testsFailed: Optional[int] = None
    categorySummary: Optional[Dict[str, Any]] = None
    endpointsCount: Optional[int] = None
    testSuitesCount: Optional[int] = None
    testRunsCount: Optional[int] = None
    lastRunAt: Optional[str] = None
    baseUrl: Optional[str] = None

class UploadSpecResponse(BaseModel):
    status: str
    message: str
    spec_id: Optional[str] = None
    originalName: Optional[str] = None
    size: Optional[int] = None
    endpoints_count: int = 0

class RunProjectRequest(BaseModel):
    cases: Optional[List[str]] = None
    token: Optional[str] = None
    delay_ms: int = 300
    register_url: Optional[str] = None
    login_url: Optional[str] = None
    auth_email: Optional[str] = None
    auth_password: Optional[str] = None
    admin_token: Optional[str] = None  # Admin JWT for BOLA resource creation

class RunProjectResponse(BaseModel):
    runId: str
    summary: Dict[str, Any]
    executedAt: str

# ── Generator schemas ────────────────────────────────────────────────────────

class GenerateTestsRequest(BaseModel):
    spec_id: str
    test_type: str
    max_tests: Optional[int] = None
    use_ai: bool = False
    # When true, previous active cases for the same project+spec+category are deactivated
    # so regenerating a suite doesn't keep accumulating redundant rows.
    overwrite: bool = True
    # Optional admin credentials — if provided, AI generators will include and annotate
    # admin-route tests with these credentials instead of marking them as manual-only.
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    use_batch: bool = True


class RequestData(BaseModel):
    path_params: Dict[str, Any] = Field(default_factory=dict)
    query_params: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, Any] = Field(default_factory=dict)
    body: Optional[Any] = None


class ExpectedStatusItem(BaseModel):
    status: int
    reason: str


class TestCaseOut(BaseModel):
    id: str
    name: str
    test_type: str
    endpoint_path: str
    method: str
    description: Optional[str] = None
    category: Optional[str] = None
    ai_explanation: Optional[str] = None
    owasp_category: Optional[str] = None
    owasp_id: Optional[str] = None
    owasp_name: Optional[str] = None
    security_intent: Optional[str] = None
    ai_coverage_rationale: Optional[str] = None
    generation_source: Optional[str] = None

    # Request data (what the execution engine sends)
    headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_headers: Optional[Dict[str, str]] = None
    request_query: Optional[Dict[str, Any]] = None
    request_body: Optional[Any] = None
    path_params: Optional[Dict[str, str]] = None
    auth_type: Optional[str] = None
    failure_category: Optional[str] = None
    expected: Optional[List[ExpectedStatusItem]] = None
    metadata: Optional[Dict[str, Any]] = None
    mutation_meta: Optional[Dict[str, Any]] = None
    steps: Optional[List[Any]] = None  # UI convenience

    # Also support nested request_data (from contract branch) and raw payloads
    request_data: Optional[Any] = None

    # Assertions (what to check)
    expected_status: Union[int, List[int]]
    expected_response: Optional[Dict[str, Any]] = None
    assertions: Optional[List[str]] = None
    execution_order: Optional[int] = None


class GenerateTestsResponse(BaseModel):
    project_id: str
    test_type: str
    cases: List[TestCaseOut]
    count: int
    suite_id: Optional[str] = None
    generation_method: str = "rule_based"
    base_url: Optional[str] = None


# ── Per-test-case CRUD schemas ───────────────────────────────────────────────

class UpdateTestCaseRequest(BaseModel):
    name: Optional[str] = None
    test_type: Optional[str] = None
    endpoint_path: Optional[str] = None
    method: Optional[str] = None
    description: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    request_headers: Optional[Dict[str, str]] = None
    request_query: Optional[Dict[str, Any]] = None
    request_body: Optional[Any] = None
    path_params: Optional[Dict[str, str]] = None
    auth_type: Optional[str] = None
    failure_category: Optional[str] = None
    expected: Optional[List[ExpectedStatusItem]] = None
    metadata: Optional[Dict[str, Any]] = None

    # Assertions
    expected_status: Optional[Union[int, List[int]]] = None
    expected_response: Optional[Dict] = None
    assertions: Optional[List[str]] = None
    execution_order: Optional[int] = None


# ── AI Analysis schemas ──────────────────────────────────────────────────────

class AnalyzeFailureRequest(BaseModel):
    test_name: str
    test_type: str
    method: str
    endpoint_path: str
    expected_status: int
    actual_status: int
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    request_body: Optional[str] = None
    description: Optional[str] = None


class AIAnalysisResult(BaseModel):
    root_cause: str
    explanation: str
    suggested_fix: str
    severity: str = "medium"


class AIAnalysisResponse(BaseModel):
    analysis: AIAnalysisResult
    ai_powered: bool = True
    tokens_used: Optional[Dict[str, int]] = None


# ── Run Results schemas ──────────────────────────────────────────────────────

class RunResultItem(BaseModel):
    id: str
    name: str
    endpoint_path: str
    method: str
    expected_status: int
    actual_status: int
    passed: bool
    response_time_ms: int = 0
    response_body: str = ""
    response_headers: Dict[str, str] = {}
    error_message: str = ""
    request_headers: Optional[Dict[str, str]] = None
    request_body: Optional[Any] = None
    final_request_sent: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, Any]] = None
    expected: Optional[List[ExpectedStatusItem]] = None
    failure_category: Optional[str] = None
    actual_failure_category: Optional[str] = None
    auth_applied: Optional[bool] = None
    auth_status: Optional[str] = None
    auth_warning: Optional[str] = None
    log: str = ""


class RunResultsSummary(BaseModel):
    total: int
    passed: int
    failed: int


class RunResultsResponse(BaseModel):
    results: List[RunResultItem]
    summary: RunResultsSummary
    base_url: str = ""
    executed_at: str = ""


# ── Generation Meta schema ───────────────────────────────────────────────────

class GenerationMeta(BaseModel):
    generation_method: str = "rule_based"
    ai_tokens_used: int = 0
    test_type: str = ""
    generated_at: str = ""

# ── Test Execution History schemas (Dashboard) ───────────────────────────────

class TestRunHistory(BaseModel):
    id: str
    runDate: str
    runTime: str
    status: str
    statusCode: int
    responseTime: str
    duration: str
    errorMessage: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

class TestExecutionCase(BaseModel):
    id: str
    name: str
    endpoint: str
    method: str
    test_type: Optional[str] = None
    totalRuns: int
    passed: int
    failed: int
    lastStatus: str
    history: List[TestRunHistory]


# ── Category Stats (aggregated from TestRun records) ──────────────────────────

class CategoryStatsItem(BaseModel):
    """Aggregated pass/fail stats for a test category."""
    category: str
    passed: int
    failed: int
    totalRuns: int


# ── Stateful security run schemas ────────────────────────────────────────────

class StatefulTestResult(BaseModel):
    """Single authorization scenario execution result."""
    scenario_id: str
    endpoint_path: str
    method: str
    scenario_type: str          # e.g. "A_UNAUTHENTICATED"
    request_headers: Dict[str, str]
    expected_status: int
    actual_status: int
    passed: bool
    classification: str         # Human-readable outcome label
    severity: str               # INFO / WARNING / HIGH / CRITICAL
    description: str
    error: Optional[str] = None


class SetupPhaseResult(BaseModel):
    """Outcome of the pre-test user/token provisioning phase."""
    success: bool
    steps: List[Dict[str, Any]]
    error: Optional[str] = None


class SeveritySummary(BaseModel):
    CRITICAL: int = 0
    HIGH: int = 0
    WARNING: int = 0
    INFO: int = 0


class StatefulRunReport(BaseModel):
    """Complete stateful security run report."""
    setup: SetupPhaseResult
    total: int
    passed: int
    failed: int
    severity_summary: SeveritySummary
    vulnerabilities: List[StatefulTestResult]
    all_results: List[StatefulTestResult]
