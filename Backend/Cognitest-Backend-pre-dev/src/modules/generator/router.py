"""
Generator router — exposes test generation and contract testing endpoints.

Endpoints:
  GET  /generator/types               — list supported test types
  POST /generator/fuzz/{project_id}   — generate + execute fuzz tests
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.middleware.auth_middleware import get_current_user, require_permission, require_project_permission
from .constants import SUPPORTED_TEST_TYPES
from .schema import (
    TestTypesResponse,
)
from .engines.fuzz.schema import (
    FuzzGenerateRequest,
    FuzzTestCaseOut,
    FuzzFinding,
    FuzzSummary,
    FuzzRunResponse,
    SecuritySummaryOut,
)
from .engines.fuzz.service import run_fuzz_pipeline
from .engines.fuzz.result_classifier import classify_batch, generate_security_summary

from .engines.contract.contract_executor import run_contract_engine

router = APIRouter(prefix="/generator", tags=["Generator"])
contract_router = APIRouter()


@router.get("/types", response_model=TestTypesResponse)
async def get_test_types(user: dict = Depends(get_current_user)) -> TestTypesResponse:
    """Return the list of supported AI test generation types."""
    return TestTypesResponse(types=SUPPORTED_TEST_TYPES)


@router.post("/fuzz/{project_id}", response_model=FuzzRunResponse)
async def generate_fuzz_tests(
    project_id: str,
    data: FuzzGenerateRequest,
    user: dict = Depends(require_project_permission("create_test_cases")),
):
    """
    Generate fuzz test cases for a project using AI, optionally execute
    them via Newman, and return results with anomaly detection and
    structured security classification.
    """
    try:
        user_id = user.get("id", user.get("sub", ""))

        result = await run_fuzz_pipeline(
            project_id=project_id,
            spec_id=data.spec_id,
            triggered_by=user_id,
            base_url=data.base_url,
            execute=data.run_tests,
            use_ai=data.use_ai,
        )

        # Map to response models
        test_cases_out = [
            FuzzTestCaseOut(
                id=tc["id"],
                name=tc["name"],
                fuzz_type=tc.get("fuzz_type", "RANDOM_STRING"),
                endpoint_path=tc.get("endpoint_path", "/"),
                method=tc.get("method", "GET"),
                headers=tc.get("headers", {}),
                body=tc.get("body"),
                query_params=tc.get("query_params", {}),
                expected_status=tc.get("expected_status", 400),
                expected_behavior=tc.get("expected_behavior", ""),
                description=tc.get("description"),
            )
            for tc in result["test_cases"]
        ]

        # Classify findings with security intelligence (Phase 3 & 7)
        raw_findings = result.get("findings", [])
        classified_findings = classify_batch(raw_findings)
        security_summary_data = generate_security_summary(classified_findings)

        findings_out = [
            FuzzFinding(
                test_case_id=f.get("test_case_id", ""),
                test_name=f.get("test_name", ""),
                fuzz_type=f.get("fuzz_type", "UNKNOWN"),
                status_code=f.get("status_code", 0),
                response_time_ms=f.get("response_time_ms", 0),
                crashed=f.get("crashed", False),
                anomaly_detected=f.get("anomaly_detected", False),
                anomaly_details=f.get("anomaly_details"),
                classification=f.get("classification", "NORMAL"),
                severity=f.get("severity", "INFO"),
                expected_status=f.get("expected_status", 400),
            )
            for f in classified_findings
        ]

        summary = result.get("summary", {})

        return FuzzRunResponse(
            project_id=project_id,
            run_id=result.get("run_id"),
            test_cases=test_cases_out,
            findings=findings_out,
            summary=FuzzSummary(
                total=summary.get("total", 0),
                passed=summary.get("passed", 0),
                failed=summary.get("failed", 0),
                crashed=summary.get("crashed", 0),
                anomalies_detected=summary.get("anomalies_detected", 0),
            ),
            security_summary=SecuritySummaryOut(**security_summary_data),
            executed=result.get("executed", False),
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fuzz pipeline error: {str(exc)}")


class ContractRunRequest(BaseModel):
    base_url: str
    canonical_spec: dict[str, Any]
    auth_enabled: bool = True
    token: Optional[str] = None
    timeout_seconds: float = 20.0


@contract_router.post("/run/{project_id}")
async def run_contract(
    project_id: str,
    data: ContractRunRequest,
    user: dict = Depends(require_project_permission("run_test_cases")),
) -> dict[str, Any]:
    triggered_by = user.get("userId") or user.get("id") or user.get("sub") or "system"
    try:
        return await run_contract_engine(
            project_id=project_id,
            triggered_by=str(triggered_by),
            canonical_spec=data.canonical_spec,
            base_url=data.base_url,
            auth_enabled=data.auth_enabled,
            token=data.token,
            timeout_seconds=data.timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Contract run failed: {str(exc)}")

