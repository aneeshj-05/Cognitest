import json
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from src.middleware.auth_middleware import get_current_user
from src.config import prisma
from prisma import Json as PrismaJson
from ..schema import TestCaseOut, UpdateTestCaseRequest, TestExecutionCase, TestRunHistory, CategoryStatsItem
from ..services import project_service
from ..utils import sanitize_json, normalize_test_category

router = APIRouter(prefix="/projects", tags=["Test Cases"])


def _dict_values_to_str(d: Any) -> Any:
    if not isinstance(d, dict):
        return d
    return {str(k): str(v) for k, v in d.items()}


def _dict_keys_to_str(d: Any) -> Any:
    if not isinstance(d, dict):
        return d
    return {str(k): v for k, v in d.items()}


def _default_reason_for_status(status: int) -> str:
    return {
        400: "Malformed request body",
        401: "Unauthorized",
        404: "Resource not found",
        422: "Validation failure",
        429: "Rate limit exceeded",
    }.get(status, f"Expected HTTP {status}")


def _build_expected_entries(raw_expected: Any, fallback_expected_status: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if isinstance(raw_expected, list):
        for item in raw_expected:
            if not isinstance(item, dict):
                continue
            try:
                status = int(item.get("status"))
            except (TypeError, ValueError):
                continue
            reason = str(item.get("reason") or _default_reason_for_status(status)).strip()
            entries.append({"status": status, "reason": reason})
    if entries:
        return entries

    values = fallback_expected_status if isinstance(fallback_expected_status, list) else [fallback_expected_status]
    for value in values:
        try:
            status = int(value)
        except (TypeError, ValueError):
            continue
        entries.append({"status": status, "reason": _default_reason_for_status(status)})
    return entries


def _normalize_case_for_response(tc: Any) -> TestCaseOut:
    tc_id = tc.get("id") if isinstance(tc, dict) else tc.id
    name = tc.get("name") if isinstance(tc, dict) else tc.name
    test_type = (tc.get("test_type") if isinstance(tc, dict) else tc.test_type) or "unknown"
    path = tc.get("endpoint_path") if isinstance(tc, dict) else tc.endpoint_path
    method = tc.get("method") if isinstance(tc, dict) else tc.method
    desc = tc.get("description") if isinstance(tc, dict) else tc.description
    cat = tc.get("category") if isinstance(tc, dict) else tc.category
    exp = tc.get("ai_explanation") if isinstance(tc, dict) else tc.ai_explanation

    headers = tc.get("request_headers") if isinstance(tc, dict) else tc.request_headers
    query = tc.get("request_query") if isinstance(tc, dict) else tc.request_query
    body = tc.get("request_body") if isinstance(tc, dict) else tc.request_body
    path_params = tc.get("path_params") if isinstance(tc, dict) else tc.path_params
    estatus = tc.get("expected_status") if isinstance(tc, dict) else tc.expected_status
    eresponse = tc.get("expected_response") if isinstance(tc, dict) else tc.expected_response
    assertions = tc.get("assertions") if isinstance(tc, dict) else tc.assertions
    metadata = tc.get("metadata") if isinstance(tc, dict) else tc.metadata
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    metadata = metadata if isinstance(metadata, dict) else {}
    expected_entries = _build_expected_entries(metadata.get("expected"), metadata.get("expected_statuses") or estatus)
    failure_category = metadata.get("failure_category")
    auth_type = metadata.get("auth_type")
    owasp_category = (
        (tc.get("owasp_category") if isinstance(tc, dict) else getattr(tc, "owasp_category", None))
        or metadata.get("owasp_category")
    )
    owasp_id = (
        (tc.get("owasp_id") if isinstance(tc, dict) else getattr(tc, "owasp_id", None))
        or metadata.get("owasp_id")
        or owasp_category
    )
    owasp_name = (
        (tc.get("owasp_name") if isinstance(tc, dict) else getattr(tc, "owasp_name", None))
        or metadata.get("owasp_name")
    )
    security_intent = (
        (tc.get("security_intent") if isinstance(tc, dict) else getattr(tc, "security_intent", None))
        or metadata.get("security_intent")
    )
    ai_coverage_rationale = (
        (tc.get("ai_coverage_rationale") if isinstance(tc, dict) else getattr(tc, "ai_coverage_rationale", None))
        or metadata.get("ai_coverage_rationale")
    )
    generation_source = (
        (tc.get("generation_source") if isinstance(tc, dict) else getattr(tc, "generation_source", None))
        or metadata.get("generation_source")
    )
    order = tc.get("execution_order") if isinstance(tc, dict) else getattr(tc, "execution_order", None)

    return TestCaseOut(
        id=tc_id,
        name=name,
        test_type=test_type,
        endpoint_path=path,
        method=method,
        description=desc,
        category=cat,
        ai_explanation=exp,
        owasp_category=owasp_category,
        owasp_id=owasp_id,
        owasp_name=owasp_name,
        security_intent=security_intent,
        ai_coverage_rationale=ai_coverage_rationale,
        generation_source=generation_source,
        request_headers=_dict_values_to_str(_dict_keys_to_str(headers)),
        request_query=_dict_keys_to_str(query),
        headers=_dict_values_to_str(_dict_keys_to_str(headers)),
        query_params=_dict_keys_to_str(query),
        request_body=body,
        path_params=_dict_values_to_str(_dict_keys_to_str(path_params)),
        auth_type=auth_type,
        failure_category=failure_category,
        expected=expected_entries or None,
        metadata=metadata or None,
        expected_status=estatus,
        expected_response=eresponse,
        assertions=assertions,
        execution_order=order,
    )


async def _fetch_test_cases_from_db(
    project_id: str,
    version: Optional[str] = None,
    spec_id: Optional[str] = None,
    test_types: Optional[str] = None,
    methods: Optional[str] = None,
    include_inactive: bool = False,
) -> List[TestCaseOut]:
    """Plain async helper — no FastAPI dependencies. Called internally by multiple route handlers."""
    where_clause: dict[str, Any] = {"projectId": project_id}
    if not include_inactive:
        where_clause["isActive"] = True

    suite_filter = {}
    if version:
        suite_filter["specVersion"] = version
    elif spec_id:
        suite_filter["specId"] = spec_id
    
    if suite_filter:
        where_clause["suite"] = suite_filter

    if test_types:
        raw = [t.strip().split(":", 1)[0] for t in test_types.split(",") if t.strip()]
        valid = [normalize_test_category(r) for r in raw if r.upper() != "ALL"]
        if valid:
            where_clause["category"] = {"in": valid}

    if methods:
        ms = [m.strip().upper() for m in methods.split(",") if m.strip()]
        if ms and "ALL" not in ms:
            where_clause["method"] = {"in": ms}

    test_cases = await prisma.testcase.find_many(
        where=where_clause,
        order={"execution_order": "asc"}
    )
    return [_normalize_case_for_response(tc) for tc in test_cases]


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/test-cases-db", response_model=List[TestCaseOut])
async def list_test_cases_from_db(
    project_id: str,
    version: Optional[str] = None,
    spec_id: Optional[str] = None,
    test_types: Optional[str] = None,
    methods: Optional[str] = None,
    include_inactive: bool = Query(False),
    user: dict = Depends(get_current_user)
):
    await project_service.verify_project_access(project_id, user)
    return await _fetch_test_cases_from_db(
        project_id,
        version=version,
        spec_id=spec_id,
        test_types=test_types,
        methods=methods,
        include_inactive=include_inactive,
    )


@router.get("/{project_id}/test-cases", response_model=List[TestCaseOut])
async def list_test_cases(
    project_id: str,
    case_ids: Optional[str] = None,
    version: Optional[str] = None,
    spec_id: Optional[str] = None,
    test_types: Optional[str] = None,
    methods: Optional[str] = None,
    include_inactive: bool = Query(False),
    user: dict = Depends(get_current_user)
):
    """Fetch test cases. Supports fast-path by comma-separated case_ids (used by Run Suite modal)."""
    await project_service.verify_project_access(project_id, user)

    if case_ids:
        ids = [cid.strip() for cid in case_ids.split(",") if cid.strip()]
        if ids:
            test_cases = await prisma.testcase.find_many(
                where={"id": {"in": ids}, "projectId": project_id},
                order={"execution_order": "asc"},
            )
            return [_normalize_case_for_response(tc) for tc in test_cases]

    return await _fetch_test_cases_from_db(
        project_id,
        version=version,
        spec_id=spec_id,
        test_types=test_types,
        methods=methods,
        include_inactive=include_inactive,
    )


@router.patch("/{project_id}/test-cases/{case_id}", response_model=TestCaseOut)
async def update_test_case(
    project_id: str,
    case_id: str,
    data: UpdateTestCaseRequest,
    user: dict = Depends(get_current_user)
):
    await project_service.verify_project_access(project_id, user)

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        existing = await prisma.testcase.find_unique(where={"id": case_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Test case not found")
        return _normalize_case_for_response(existing)

    db_data = {}
    if "headers" in update_data:
        update_data["request_headers"] = update_data.pop("headers")
    if "query_params" in update_data:
        update_data["request_query"] = update_data.pop("query_params")
    metadata_patch: dict[str, Any] = {}
    expected_entries = update_data.pop("expected", None)
    if expected_entries is not None:
        normalized_expected = _build_expected_entries(expected_entries, update_data.get("expected_status"))
        metadata_patch["expected"] = normalized_expected
        metadata_patch["expected_statuses"] = [item["status"] for item in normalized_expected]
        if normalized_expected and "expected_status" not in update_data:
            update_data["expected_status"] = int(normalized_expected[0]["status"])
    failure_category = update_data.pop("failure_category", None)
    if failure_category is not None:
        metadata_patch["failure_category"] = failure_category
    auth_type = update_data.pop("auth_type", None)
    if auth_type is not None:
        metadata_patch["auth_type"] = auth_type

    if "expected_status" in update_data and isinstance(update_data["expected_status"], list):
        statuses = update_data["expected_status"]
        metadata_patch["expected_statuses"] = statuses
        first_numeric = 200
        for value in statuses:
            try:
                first_numeric = int(value)
                break
            except (TypeError, ValueError):
                continue
        update_data["expected_status"] = first_numeric

    if metadata_patch:
        existing = await prisma.testcase.find_unique(where={"id": case_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Test case not found")
        existing_metadata = existing.metadata
        if isinstance(existing_metadata, str):
            try:
                existing_metadata = json.loads(existing_metadata)
            except Exception:
                existing_metadata = {}
        if not isinstance(existing_metadata, dict):
            existing_metadata = {}
        update_data["metadata"] = {**existing_metadata, **metadata_patch}

    json_fields = {
        "request_body", "request_headers", "request_query",
        "path_params", "expected_response", "assertions", "metadata"
    }
    for k, v in update_data.items():
        db_data[k] = sanitize_json(v) if k in json_fields else v

    updated = await prisma.testcase.update(where={"id": case_id}, data=db_data)
    return _normalize_case_for_response(updated)


@router.delete("/{project_id}/test-cases/{case_id}", status_code=204)
async def delete_test_case_endpoint(
    project_id: str,
    case_id: str,
    user: dict = Depends(get_current_user)
):
    await project_service.verify_project_access(project_id, user)
    await prisma.testcase.update(where={"id": case_id}, data={"isActive": False})
    return None


# ── Dashboard routes ────────────────────────────────────────────────────────────

@router.get("/{project_id}/test-executions", response_model=List[TestExecutionCase])
async def get_test_executions(
    project_id: str,
    category: Optional[str] = None,
    version: Optional[str] = None,
    spec_id: Optional[str] = None,
    include_inactive: bool = Query(False),
    user: dict = Depends(get_current_user)
):
    await project_service.verify_project_access(project_id, user)

    where_clause: dict[str, Any] = {"projectId": project_id}
    if not include_inactive:
        where_clause["isActive"] = True

    suite_filter = {}
    if version:
        suite_filter["specVersion"] = version
    elif spec_id:
        suite_filter["specId"] = spec_id

    if suite_filter:
        where_clause["suite"] = suite_filter

    if category and category.lower() != "all":
        where_clause["category"] = normalize_test_category(category)

    test_cases = await prisma.testcase.find_many(
        where=where_clause,
        order={"execution_order": "asc"},
        take=500,  # safety cap — dashboard shows latest 500 cases max
    )

    tc_ids = [tc.id for tc in test_cases]
    if not tc_ids:
        return []

    # Fetch only the most-recent 5 results per test case to build history.
    # We do a single batched find_many with a take limit instead of loading
    # the entire TestResult table.
    results = await prisma.testresult.find_many(
        where={"testCaseId": {"in": tc_ids}},
        order={"executedAt": "desc"},
        include={"run": True},
        take=len(tc_ids) * 5,  # at most 5 results per test case
    )

    history_map: dict[str, list] = {tid: [] for tid in tc_ids}
    tc_stats: dict[str, dict] = {tid: {"passed": 0, "failed": 0, "total": 0} for tid in tc_ids}

    tc_payload_fallback: dict[str, dict] = {}
    for tc in test_cases:
        fallback: dict[str, Any] = {"method": tc.method, "endpoint_path": tc.endpoint_path}
        if tc.request_headers: fallback["headers"] = tc.request_headers
        if tc.request_body:    fallback["body"] = tc.request_body
        if tc.request_query:   fallback["query_params"] = tc.request_query
        if tc.path_params:     fallback["path_params"] = tc.path_params
        tc_payload_fallback[tc.id] = fallback

    for r in results:
        tid = r.testCaseId
        if tid not in tc_stats:
            continue
        tc_stats[tid]["total"] += 1
        status_name = r.status.name if hasattr(r.status, "name") else str(r.status)
        if status_name == "PASSED":
            tc_stats[tid]["passed"] += 1
        elif status_name == "FAILED":
            tc_stats[tid]["failed"] += 1

        if len(history_map[tid]) >= 5:
            continue

        ex_at = r.executedAt or (r.run.createdAt if r.run else None)
        history_map[tid].append(TestRunHistory(
            id=r.id,
            runDate=ex_at.strftime("%b %d, %Y") if ex_at else "Unknown",
            runTime=ex_at.strftime("%I:%M %p") if ex_at else "Unknown",
            status=status_name,
            statusCode=r.actual_status,
            responseTime=f"{r.response_time_ms}ms" if r.response_time_ms else "0ms",
            duration=f"{(r.response_time_ms or 0) / 1000:.1f}s",
            errorMessage=r.error_message,
            payload=r.request_sent if r.request_sent else tc_payload_fallback.get(tid),
        ))

    output = []
    enum_map = {
        "FUNCTIONAL": "Functional", "NEGATIVE": "Negative",
        "SECURITY": "Security", "CONTRACT": "Contract", "FUZZ": "Fuzz"
    }
    for tc in test_cases:
        tid = tc.id
        hist = history_map[tid]
        stats = tc_stats[tid]
        cat_str = str(tc.category.name if hasattr(tc.category, "name") else tc.category).upper()
        resolved_type = tc.test_type or enum_map.get(cat_str, cat_str.capitalize())

        output.append(TestExecutionCase(
            id=tid,
            name=tc.name,
            endpoint=tc.endpoint_path,
            method=tc.method,
            test_type=resolved_type,
            totalRuns=stats["total"],
            passed=stats["passed"],
            failed=stats["failed"],
            lastStatus=hist[0].status if hist else "PASS",
            history=hist
        ))
    return output


@router.get("/{project_id}/category-stats", response_model=List[CategoryStatsItem])
async def get_category_stats(
    project_id: str,
    version: Optional[str] = None,
    spec_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    await project_service.verify_project_access(project_id, user)

    # ── Step 1: Resolve test case IDs scoped to this project (+ optional spec) ──
    # We avoid a massive cross-table JOIN by first fetching test case IDs,
    # then aggregating results only for those IDs.
    tc_where: dict[str, Any] = {"projectId": project_id, "isActive": True}
    if version:
        tc_where["suite"] = {"specVersion": version}
    elif spec_id:
        tc_where["suite"] = {"specId": spec_id}

    # Only fetch id + category — minimal columns, fast query
    test_cases = await prisma.testcase.find_many(
        where=tc_where,
        # Prisma Python client doesn't support `select` in find_many directly,
        # but limiting take keeps the query fast for dashboards.
        take=2000,
    )

    if not test_cases:
        return []

    # Build a lookup: test_case_id → category string
    id_to_cat: dict[str, str] = {}
    for tc in test_cases:
        cat = str(tc.category.name if hasattr(tc.category, "name") else tc.category).upper()
        id_to_cat[tc.id] = cat

    tc_ids = list(id_to_cat.keys())

    # ── Step 2: Fetch only status + testCaseId for matching results ──────────
    # No `include` — avoids the full JOIN that caused the ReadTimeout.
    # Limit to last 10 000 results so this stays fast even on large projects.
    results = await prisma.testresult.find_many(
        where={
            "testCaseId": {"in": tc_ids},
            "run": {"projectId": project_id, "status": "COMPLETED"},
        },
        order={"executedAt": "desc"},
        take=10_000,
    )

    # ── Step 3: Aggregate in Python ──────────────────────────────────────────
    stats: dict[str, dict] = {}
    for r in results:
        cat = id_to_cat.get(r.testCaseId, "UNKNOWN")
        if cat not in stats:
            stats[cat] = {"passed": 0, "failed": 0, "runs": set()}
        status_name = r.status.name if hasattr(r.status, "name") else str(r.status)
        if status_name == "PASSED":
            stats[cat]["passed"] += 1
        elif status_name == "FAILED":
            stats[cat]["failed"] += 1
        stats[cat]["runs"].add(r.runId)

    return [
        CategoryStatsItem(
            category=c,
            passed=s["passed"],
            failed=s["failed"],
            totalRuns=len(s["runs"])
        )
        for c, s in stats.items()
    ]
