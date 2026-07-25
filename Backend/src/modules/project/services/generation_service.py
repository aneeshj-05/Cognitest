import json
import logging
import uuid
from typing import Any, List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException
from src.config import prisma
from prisma import Json as PrismaJson
from ..schema import (
    GenerateTestsRequest,
    GenerateTestsResponse,
    TestCaseOut,
    UpdateTestCaseRequest,
)
from ..generate import generate_test_payload, generate_test_payload_async
from ..utils import sanitize_json, _strip_null_bytes, substitute_path_params, normalize_test_category, normalize_test_sub_category
from src.modules.generator.ai.token_logger import TokenUsageLogger, calculate_cost

logger = logging.getLogger(__name__)


def classify_status(code: int) -> str:
    if code == 401:
        return "auth"
    if code == 422:
        return "validation"
    if code == 400:
        return "schema"
    if code == 404:
        return "not_found"
    if code == 429:
        return "rate_limit"
    return "unknown"


def _default_reason_for_status(status: int) -> str:
    return {
        400: "Malformed request body",
        401: "Unauthorized",
        404: "Resource not found",
        422: "Validation failure",
        429: "Rate limit exceeded",
    }.get(status, f"Expected HTTP {status}")


def _derive_failure_category(statuses: list[int], explicit: Any = None) -> str:
    valid = {"validation", "auth", "schema", "rate_limit", "not_found"}
    explicit_val = str(explicit or "").strip().lower()
    if explicit_val in valid:
        return explicit_val
    if not statuses:
        return ""
    if 422 in statuses:
        return "validation"
    if 401 in statuses:
        return "auth"
    if 404 in statuses:
        return "not_found"
    if 429 in statuses:
        return "rate_limit"
    if 400 in statuses:
        return "schema"
    if any(code >= 400 for code in statuses):
        return "schema"
    return ""


def _build_expected_entries(case: dict[str, Any], metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    metadata = metadata if isinstance(metadata, dict) else {}
    raw_expected = case.get("expected") or metadata.get("expected")
    entries: list[dict[str, Any]] = []

    if isinstance(raw_expected, list):
        for item in raw_expected:
            if not isinstance(item, dict):
                continue
            status_raw = item.get("status")
            try:
                status = int(status_raw)
            except (TypeError, ValueError):
                continue
            reason = str(item.get("reason") or _default_reason_for_status(status)).strip()
            entries.append({"status": status, "reason": reason})
    if entries:
        return entries

    raw_statuses = metadata.get("expected_statuses")
    if not isinstance(raw_statuses, list):
        raw_statuses = case.get("expected_status")
    if not isinstance(raw_statuses, list):
        raw_statuses = [raw_statuses]

    for item in raw_statuses:
        try:
            status = int(item)
        except (TypeError, ValueError):
            continue
        entries.append({"status": status, "reason": _default_reason_for_status(status)})

    return entries







def _inject_security_meta(
    assertions: list,
    *,
    owasp_category: str | None = None,
    requires_stateful: bool | None = None,
    requires_auth: bool | None = None,
    auth_negative: bool | None = None,
) -> list:
    """Encode security-specific metadata into the assertions list.

    The execution runner reads ``__security_meta__=<json>`` entries from the
    assertions column to recover owasp_category / requires_stateful after a DB
    round-trip (those fields have no dedicated column in the schema).
    """
    if not any([owasp_category, requires_stateful, requires_auth is not None, auth_negative]):
        return assertions or []
    meta: dict[str, Any] = {}
    if owasp_category:
        meta["owasp_category"] = owasp_category
    if requires_stateful:
        meta["requires_stateful"] = True
    if requires_auth is not None:
        meta["requires_auth"] = bool(requires_auth)
    if auth_negative:
        meta["auth_negative"] = True
    tag = f"__security_meta__={json.dumps(meta, separators=(',', ':'))}"
    # Remove any existing security meta tag before adding the fresh one
    filtered = [a for a in (assertions or []) if not (isinstance(a, str) and a.startswith("__security_meta__="))]
    return filtered + [tag]

def _normalize_case_for_response(tc: Any) -> dict:
    """Normalize DB record or engine dict to TestCaseOut schema fields."""
    def _dict_values_to_str(d: Any) -> Any:
        if not isinstance(d, dict): return d
        return {str(k): str(v) for k, v in d.items()}

    def _dict_keys_to_str(d: Any) -> Any:
        if not isinstance(d, dict): return d
        return {str(k): v for k, v in d.items()}

    is_dict = isinstance(tc, dict)
    
    # Extract fields based on source type
    get_field = lambda f: tc.get(f) if is_dict else getattr(tc, f, None)
    metadata = get_field("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    metadata = metadata if isinstance(metadata, dict) else {}
    auth_type = metadata.get("auth_type") if isinstance(metadata, dict) else None
    source_case = tc if isinstance(tc, dict) else {}
    expected_entries = _build_expected_entries(source_case, metadata if isinstance(metadata, dict) else {})
    if not expected_entries:
        try:
            fallback_status = int(get_field("expected_status"))
            expected_entries = [{"status": fallback_status, "reason": _default_reason_for_status(fallback_status)}]
        except (TypeError, ValueError):
            expected_entries = []
    failure_category = _derive_failure_category(
        [int(item["status"]) for item in expected_entries],
        (source_case.get("failure_category") if isinstance(source_case, dict) else None)
        or (metadata.get("failure_category") if isinstance(metadata, dict) else None),
    )

    return {
        "id": get_field("id") or str(uuid.uuid4()),
        "name": get_field("name") or "Unnamed Test",
        "test_type": get_field("test_type") or "unknown",
        "endpoint_path": get_field("endpoint_path") or "/",
        "method": get_field("method") or "GET",
        "description": get_field("description") or "",
        "category": get_field("category") or "FUNCTIONAL",
        "ai_explanation": get_field("ai_explanation"),
        "owasp_category": get_field("owasp_category") or metadata.get("owasp_category"),
        "owasp_id": get_field("owasp_id") or metadata.get("owasp_id") or metadata.get("owasp_category"),
        "owasp_name": get_field("owasp_name") or metadata.get("owasp_name"),
        "security_intent": get_field("security_intent") or metadata.get("security_intent"),
        "ai_coverage_rationale": get_field("ai_coverage_rationale") or metadata.get("ai_coverage_rationale"),
        "generation_source": get_field("generation_source") or metadata.get("generation_source"),
        "request_headers": _dict_values_to_str(_dict_keys_to_str(get_field("request_headers"))),
        "request_query": _dict_keys_to_str(get_field("request_query")),
        "query_params": _dict_keys_to_str(get_field("request_query")),
        "request_body": get_field("request_body") if get_field("request_body") is not None else get_field("request_data"),
        "path_params": _dict_values_to_str(_dict_keys_to_str(get_field("path_params"))),
        "auth_type": auth_type,
        "failure_category": failure_category,
        "expected": expected_entries or None,
        "expected_status": get_field("expected_status") or 200,
        "expected_response": get_field("expected_response"),
        "assertions": get_field("assertions") or [],
        "execution_order": get_field("execution_order"),
        "metadata": metadata or {},
        "mutation_meta": metadata.get("mutation_meta") or {},
    }


def _db_expected_status(value: Any) -> int:
    if isinstance(value, dict):
        value = value.get("status")
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                item = item.get("status")
            if isinstance(item, list):
                continue
            try:
                return int(item)
            except (TypeError, ValueError):
                continue
        return 200
    try:
        return int(value)
    except (TypeError, ValueError):
        return 200

async def list_test_cases_from_db(
    project_id: str,
    version: Optional[str] = None,
    spec_id: Optional[str] = None,
    test_types: Optional[str] = None,
    methods: Optional[str] = None,
    include_inactive: bool = False,
) -> List[TestCaseOut]:
    """Return the test cases for a project from database, with optional filters."""
    where_clause: dict[str, Any] = {"projectId": project_id}
    if not include_inactive:
        where_clause["isActive"] = True

    suite_filter: dict[str, Any] = {}
    if spec_id:
        suite_filter["specId"] = spec_id
    elif version:
        suite_filter["specVersion"] = version
    if suite_filter:
        where_clause["suite"] = suite_filter

    if test_types:
        raw = [t.strip().split(":", 1)[0] for t in test_types.split(",") if t.strip()]
        normalized = [normalize_test_category(t, default="") for t in raw]
        normalized = [t for t in normalized if t]
        if normalized and "ALL" not in normalized:
            where_clause["category"] = {"in": normalized}

    if methods:
        ms = [m.strip().upper() for m in methods.split(",") if m.strip()]
        if ms and "ALL" not in ms:
            where_clause["method"] = {"in": ms}

    test_cases = await prisma.testcase.find_many(
        where=where_clause,
        order={"createdAt": "asc"}
    )
    out = [TestCaseOut(**_normalize_case_for_response(tc)) for tc in test_cases]
    out.sort(key=lambda x: x.execution_order if x.execution_order is not None else 999999)
    return out

async def generate_project_tests(
    project_id: str, 
    data: GenerateTestsRequest, 
    spec_store: dict, 
    base_url_store: dict,
    draft_store: dict,
    gen_meta_store: dict,
    user_id: str = "system",
    use_batch: Optional[bool] = None,
    on_status_update: Any = None,
) -> GenerateTestsResponse:
    from src.modules.generator.engines.contract.contract_generator import generate_contract_test_cases

    if use_batch is None:
        use_batch = getattr(data, "use_batch", True)

    # 1. Get spec
    api_spec = None
    if getattr(data, "spec_id", None):
        api_spec = await prisma.apispec.find_unique(where={"id": data.spec_id})
        if api_spec and api_spec.projectId != project_id:
            api_spec = None
    if not api_spec:
        api_spec = await prisma.apispec.find_first(
            where={"projectId": project_id},
            order={"createdAt": "desc"},
        )
    
    spec_content = None
    if api_spec and api_spec.parsed_spec:
        spec_content = api_spec.parsed_spec if isinstance(api_spec.parsed_spec, dict) else json.loads(api_spec.parsed_spec)

    if not spec_content:
        spec_content = spec_store.get(project_id)

    if not spec_content:
        raise HTTPException(status_code=400, detail="No spec uploaded for this project. Please upload a spec first.")

    # 2. Resolve base URL
    base_url = base_url_store.get(project_id)
    if not base_url:
        if "servers" in spec_content and spec_content["servers"]:
            base_url = spec_content["servers"][0].get("url")
        elif "host" in spec_content:
            scheme = spec_content.get("schemes", ["https"])[0]
            base_path = spec_content.get("basePath", "")
            base_url = f"{scheme}://{spec_content['host']}{base_path}"

    # 3. Generate test cases
    # NOTE: max_tests=data.max_tests (None = no cap) so AI-generated suites are
    # never silently truncated.  The frontend can pass an explicit limit if needed.

    # Resolve tenant_id for budget enforcement — look up via project
    _tenant_id = ""
    try:
        _proj_for_tenant = await prisma.project.find_unique(where={"id": project_id})
        _tenant_id = (_proj_for_tenant.tenantId or "") if _proj_for_tenant else ""
    except Exception:
        pass

    # Pre-flight budget check for AI generation
    if data.use_ai and _tenant_id:
        from src.modules.generator.ai.token_manager import token_manager, BudgetExceededError
        if not await token_manager.has_budget(_tenant_id):
            remaining = await token_manager.get_remaining_budget(_tenant_id)
            raise HTTPException(
                status_code=402,
                detail=f"Monthly AI token budget exhausted for this account. "
                       f"Remaining: {remaining} tokens. Please upgrade your plan or wait for next billing cycle.",
            )

    try:
        result = await generate_test_payload_async(
            spec=spec_content,
            test_type=data.test_type,
            max_tests=data.max_tests,
            use_ai=data.use_ai,
            admin_config={
                "email":    data.admin_email,
                "password": data.admin_password,
            } if (data.admin_email or data.admin_password) else None,
            tenant_id=_tenant_id,
            use_batch=use_batch,
            on_status_update=on_status_update,
        )
        # Unpack — function now returns (cases, method, tokens, token_batches)
        if len(result) == 4:
            cases_raw, gen_method, tokens_used, token_batches = result
        else:
            cases_raw, gen_method, tokens_used = result
            token_batches = []
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Test generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Test generation failed: {str(exc)}")
    logger.info(
        "[GEN] project=%s type=%s source=%s cases=%d tokens=%d",
        project_id, data.test_type, gen_method, len(cases_raw), tokens_used,
    )

    # 4. Persistence logic — uses a collect-then-deactivate pattern to avoid
    # data loss: old cases are only deactivated AFTER new ones are saved.
    suite_id = None
    persisted_cases = []
    try:
        suite_cat = normalize_test_category(data.test_type)

        # ── Build per-test-case token map from AI batches ──────────────────────
        # token_batches is a list of {cases, input_tokens, output_tokens}
        # Each batch corresponds to one AI call. We distribute tokens evenly
        # across the test cases that call produced.
        _tc_token_map: dict[str, tuple[int, int, int, int]] = {}  # case_id → (in, out, cc, cr)
        for batch in token_batches:
            batch_cases  = batch.get("cases") or []
            batch_in     = int(batch.get("input_tokens") or 0)
            batch_out    = int(batch.get("output_tokens") or 0)
            batch_cc     = int(batch.get("cache_creation_tokens") or 0)
            batch_cr     = int(batch.get("cache_read_tokens") or 0)
            n = len(batch_cases)
            if n == 0:
                continue
            per_in  = batch_in  // n
            per_out = batch_out // n
            per_cc  = batch_cc  // n
            per_cr  = batch_cr  // n
            rem_in  = batch_in  - per_in  * n
            rem_out = batch_out - per_out * n
            rem_cc  = batch_cc  - per_cc  * n
            rem_cr  = batch_cr  - per_cr  * n
            for i, tc in enumerate(batch_cases):
                cid = tc.get("id") if isinstance(tc, dict) else None
                if cid:
                    extra_in  = rem_in  if i == n - 1 else 0
                    extra_out = rem_out if i == n - 1 else 0
                    extra_cc  = rem_cc  if i == n - 1 else 0
                    extra_cr  = rem_cr  if i == n - 1 else 0
                    _tc_token_map[cid] = (per_in + extra_in, per_out + extra_out, per_cc + extra_cc, per_cr + extra_cr)

        # ── Compute total cost for suite ───────────────────────────────────────
        total_input_tokens  = sum(b.get("input_tokens",  0) for b in token_batches)
        total_output_tokens = sum(b.get("output_tokens", 0) for b in token_batches)
        total_cc_tokens     = sum(b.get("cache_creation_tokens", 0) for b in token_batches)
        total_cr_tokens     = sum(b.get("cache_read_tokens", 0) for b in token_batches)
        suite_cost_usd = calculate_cost(
            total_input_tokens, total_output_tokens, total_cc_tokens, total_cr_tokens, is_batch=use_batch
        )

        # ── Fetch project name for logging ─────────────────────────────────────
        try:
            _proj = await prisma.project.find_unique(where={"id": project_id})
            project_name = _proj.name if _proj else project_id
        except Exception:
            project_name = project_id

        # ── Create suite first; propagate any failure immediately ──────────────
        suite_data = {
            "project":           {"connect": {"id": project_id}},
            "name":              f"{data.test_type} Suite - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "test_type":         data.test_type,
            "category":          suite_cat,
            "specVersion":       api_spec.version if api_spec else "1.0.0",
            "generation_method": gen_method,
            "ai_tokens_used":    tokens_used,
            "ai_cost_usd":       suite_cost_usd,
        }
        if api_spec:
            suite_data["spec"] = {"connect": {"id": api_spec.id}}

        suite = await prisma.testsuite.create(data=suite_data)
        suite_id = suite.id
        logger.info(
            "Created TestSuite %s (category=%s tokens=%d cost=$%.6f batch=%s)",
            suite_id, suite_cat, tokens_used, suite_cost_usd, use_batch
        )

        # ── Init token logger (only logs when use_ai=True and tokens > 0) ──────
        token_logger = TokenUsageLogger(
            project_id=project_id,
            project_name=project_name,
            test_type=data.test_type,
            suite_id=suite_id,
            generation_method=gen_method,
            is_batch=use_batch,
        ) if (data.use_ai and tokens_used > 0) else None

        # ── Insert each test case ──────────────────────────────────────────────
        for c in cases_raw:
            case_cat = normalize_test_category(c.get("category") or data.test_type)
            sub_cat = normalize_test_sub_category(
                c.get("sub_category") or c.get("fuzz_type") or ""
            )
            case_metadata = c.get("metadata") if isinstance(c.get("metadata"), dict) else {}
            expected_entries = _build_expected_entries(c, case_metadata)
            expected_statuses = [entry["status"] for entry in expected_entries]
            failure_category = _derive_failure_category(
                [int(entry["status"]) for entry in expected_entries],
                c.get("failure_category") or case_metadata.get("failure_category"),
            )
            if expected_entries:
                c["expected"] = expected_entries
            if failure_category:
                c["failure_category"] = failure_category

            # Per-test-case token counts
            case_id = c.get("id") or ""
            tc_in, tc_out, tc_cc, tc_cr = _tc_token_map.get(case_id, (0, 0, 0, 0))
            tc_tokens = tc_in + tc_out + tc_cc + tc_cr
            tc_cost   = calculate_cost(tc_in, tc_out, tc_cc, tc_cr, is_batch=use_batch)

            # Log to token_logger (records to JSONL file on finalize)
            if token_logger and tc_tokens > 0:
                token_logger.record_test_case(
                    test_case_name        = str(c.get("name") or "Unnamed Test"),
                    endpoint_path         = str(c.get("endpoint_path") or c.get("endpoint") or "/"),
                    method                = str(c.get("method") or "GET"),
                    input_tokens          = tc_in,
                    output_tokens         = tc_out,
                    cache_creation_tokens = tc_cc,
                    cache_read_tokens     = tc_cr,
                )

            res = await prisma.testcase.create(
                data={
                    "projectId": project_id,
                    "suiteId": suite_id,
                    "name": _strip_null_bytes(c.get("name") or "Unnamed Test"),
                    "test_type": _strip_null_bytes(c.get("test_type") or "unknown"),
                    "endpoint_path": _strip_null_bytes(c.get("endpoint_path") or c.get("endpoint") or "/"),
                    "method": _strip_null_bytes(c.get("method") or "GET"),
                    "description": _strip_null_bytes(c.get("description") or ""),
                    "category": case_cat,
                    "subCategory": sub_cat,
                    "ai_tokens_used": tc_tokens,
                    "ai_cost_usd":    tc_cost,

                    # Json fields must never be bare None — use {} / [] as fallbacks
                    "request_headers": sanitize_json(
                        c.get("headers") or c.get("request_headers"), default={}
                    ),
                    "request_query": sanitize_json(
                        c.get("query_params") or c.get("request_query"), default={}
                    ),
                    "request_body": sanitize_json(c.get("request_body") if c.get("request_body") is not None else c.get("request_data"), default={}),
                    "path_params": sanitize_json(c.get("path_params"), default={}),
                    "execution_order": int(c.get("execution_order") or 0),
                    "expected_status": _db_expected_status(c.get("expected_status") or 200),
                    "assertions": sanitize_json(
                        _inject_security_meta(
                            c.get("assertions") or [],
                            owasp_category=c.get("owasp_category"),
                            requires_stateful=c.get("requires_stateful"),
                            requires_auth=c.get("requires_auth"),
                            auth_negative=c.get("auth_negative"),
                        ),
                        default=[]
                    ),
                    "metadata": sanitize_json({
                        **(c.get("metadata") or {}),
                        **({"steps": c.get("steps"), "state_machine": c.get("state_machine", [])} if c.get("steps") else {}),
                        **({"expected_statuses": c.get("expected_statuses") or expected_statuses} if (c.get("expected_statuses") or expected_statuses) else {}),
                        **({"expected": expected_entries} if expected_entries else {}),
                        **({"failure_category": failure_category} if failure_category else {}),
                        **({"auth_type": c.get("auth_type")} if c.get("auth_type") else {}),
                        **({"auth_negative": c.get("auth_negative")} if "auth_negative" in c else {}),
                        **({"kind": c.get("kind")} if c.get("kind") else {}),
                        **({"owasp_category": c.get("owasp_category")} if c.get("owasp_category") else {}),
                        **({"mutation_type": c.get("mutation_type")} if c.get("mutation_type") else {}),
                        **({"mutation_meta": c.get("mutation_meta") or case_metadata.get("mutation_meta")} if (c.get("mutation_meta") or case_metadata.get("mutation_meta")) else {}),
                        # ── Contract-executor fields (needed by execute_contract_test_cases) ──
                        # operation_key is derived deterministically so we always store it.
                        "operation_key": f"{str(c.get('method') or 'GET').lower()}:{str(c.get('endpoint_path') or '/')}",
                        **({"dependency_map": c.get("dependency_map")} if c.get("dependency_map") else {}),
                        **({"depends_on": c.get("depends_on")} if c.get("depends_on") else {}),
                        **({"resource_key": c.get("resource_key")} if c.get("resource_key") else {}),
                        **({"produces_entity": c.get("produces_entity")} if "produces_entity" in c else {}),
                        **({"produced_id_paths": c.get("produced_id_paths")} if c.get("produced_id_paths") else {}),
                        **({"is_producer_endpoint": c.get("is_producer_endpoint")} if "is_producer_endpoint" in c else {}),
                        **({"security_required": c.get("security_required")} if "security_required" in c else {}),
                        **({"missing_field": c.get("missing_field")} if c.get("missing_field") else {}),
                        **({"format_field": c.get("format_field")} if c.get("format_field") else {}),
                        **({"format": c.get("format")} if c.get("format") else {}),
                        # Source tag — AI or RULE, for UI/DB visibility
                        **({"generation_source": c.get("generation_source")} if c.get("generation_source") else {}),
                    }, default={}),
                    "isActive": True,
                }
            )
            persisted_cases.append(res)

        ai_count  = sum(1 for c in cases_raw if c.get("generation_source") == "AI")
        rule_count = sum(1 for c in cases_raw if c.get("generation_source") != "AI")
        logger.info(
            "[PERSIST] project=%s suite=%s total=%d (AI=%d RULE=%d)",
            project_id, suite_id, len(persisted_cases), ai_count, rule_count,
        )

        # ── Finalize token logger → write JSONL log file ───────────────────────
        if token_logger:
            token_summary = token_logger.finalize()
            logger.info(
                "[TOKEN] suite=%s total_tokens=%d cost=$%.6f USD",
                suite_id,
                token_summary["total_tokens"],
                token_summary["total_cost_usd"],
            )

        # ── Only deactivate old cases AFTER new ones are saved successfully ────
        # This prevents data loss if insertion fails midway.
        if data.overwrite and persisted_cases:
            await prisma.testcase.update_many(
                where={
                    "projectId": project_id,
                    "category": suite_cat,
                    "isActive": True,
                    "suiteId": {"not": suite_id},  # keep the newly created suite
                },
                data={"isActive": False}
            )
            logger.info("Deactivated old %s test cases for project %s", suite_cat, project_id)

    except Exception as e:
        logger.exception("DB persistence failed: %s", e)
        # Re-raise so the user knows it failed
        raise HTTPException(status_code=500, detail=f"Database persistence failed: {str(e)}")


    # In-memory update
    draft_store[project_id] = cases_raw
    gen_meta_store[project_id] = {
        "method": gen_method,
        "tokens_used": tokens_used,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_type": data.test_type,
    }

    cases_out = [TestCaseOut(**_normalize_case_for_response(c)) for c in cases_raw]

    return GenerateTestsResponse(
        project_id=project_id,
        test_type=data.test_type or "Functional",
        cases=cases_out,
        count=len(cases_out),
        suite_id=suite_id,
        generation_method=gen_method,
        base_url=base_url or base_url_store.get(project_id),
    )
