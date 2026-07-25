from pydantic import BaseModel
from typing import List, Optional, Any


class TestTypesResponse(BaseModel):
    types: List[str]


class GenerateTestsRequest(BaseModel):
    spec_id: str
    test_type: str


class TestCaseOut(BaseModel):
    id: str
    name: str
    test_type: str
    endpoint_path: str
    method: str
    description: str | None = None
    requires_auth: bool = False

    # Request data (what the execution engine sends)
    headers: dict[str, str] | None = None
    query_params: dict[str, Any] | None = None
    request_body: dict | None = None
    path_params: dict[str, str] | None = None

    # Assertions (what to check)
    expected_status: int
    expected_response: dict | None = None
    assertions: list[str] | None = None


class TestPlan(BaseModel):
    """Phased test execution plan."""
    auth_bootstrap_steps: List[TestCaseOut] = []
    public_tests: List[TestCaseOut] = []
    protected_tests: List[TestCaseOut] = []


class GenerateTestsResponse(BaseModel):
    project_id: str
    test_type: str
    plan: TestPlan
    count: int


# ──────────────────────────────────────────────
# Fuzz-specific schemas moved to engines/fuzz/schema.py
# ──────────────────────────────────────────────

