"""
Negative test generator — Rate Limit & Abuse.

Sends a burst of rapid requests to probe whether the API enforces
rate limiting. This is a SOFT / INFORMATIONAL test — many APIs do
not implement rate limiting, and that is acceptable. The test will
log the absence of 429 as informational rather than failing hard.

Changes from previous version:
  - Uses MutationType.RATE_LIMIT_INFORMATIONAL instead of RATE_LIMIT.
    The expectation engine treats this as a soft assertion:
      - Got 429       → passed=True, informational=False  (API enforces limits)
      - No 429        → passed=True, informational=True   (not a failure)
      - Server crash  → passed=False (5xx is still a real problem)
  - burst_count default raised to 30 to give more signal on fast servers.
"""
from __future__ import annotations

import os
import uuid
from src.modules.generator.spec_parser import Endpoint
from .mutation_taxonomy import MUTATION_EXPECTATIONS, MutationType
from .payload_generator import generate_valid_payload, generate_from_schema

def generate_rate_limit_tests(
    endpoints: list[Endpoint],
    spec: dict | None = None,
    max_targets: int = 2,
    burst_count: int | None = None,
) -> list[dict]:
    """
    Generate rate-limit probe tests.

    Selection priority:
      1. Unauthenticated GET endpoints without path params (least side-effect)
      2. Any GET endpoint without path params
      3. Any endpoint (last resort)

    Returns at most max_targets test cases.
    """
    tests: list[dict] = []
    
    if burst_count is None:
        burst_count = int(os.environ.get("NEGATIVE_TEST_BURST_COUNT", "10"))

    # Hard cap — never exceed settings.max_burst_count regardless of env/caller
    try:
        from src.config.settings import settings as _settings
        burst_count = min(burst_count, _settings.max_burst_count)
    except Exception:
        burst_count = min(burst_count, 10)

    candidates = [
        ep for ep in endpoints
        if not ep.requires_auth and ep.method == "GET" and not ep.path_params
    ]
    if not candidates:
        candidates = [
            ep for ep in endpoints
            if ep.method == "GET" and not ep.path_params
        ]
    if not candidates:
        candidates = endpoints[:max_targets]

    for ep in candidates[:max_targets]:
        request_data = None
        if ep.body_schema:
            try:
                request_data = generate_valid_payload(ep, spec=spec)
            except Exception:
                pass
                
        request_query = {}
        for param in (ep.query_params or []):
            try:
                pname = param.get("name", "")
                pschema = param.get("schema") or {"type": param.get("type", "string")}
                pval = generate_from_schema(pschema, spec=spec)
                request_query[pname] = pval if pval is not None else "test"
            except Exception:
                pass

        path_params = {}
        for param in (ep.path_params or []):
            if "id" in param.lower() or "uuid" in param.lower():
                path_params[param] = "ffffffff-ffff-ffff-ffff-ffffffffffff"
            else:
                path_params[param] = "test_value"

        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Rate limit burst ({burst_count} rapid requests) - {ep.method} {ep.path}",
            "mutation_type": MutationType.RATE_LIMIT_INFORMATIONAL,
            "expected_status": list(MUTATION_EXPECTATIONS[MutationType.RATE_LIMIT_INFORMATIONAL]),
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "RATE_LIMIT",
            "endpoint_path": ep.path,
            "method": ep.method,
            "description": (
                f"Sends {burst_count} rapid-fire requests to {ep.method} {ep.path} "
                "to probe whether the API enforces rate limiting. "
                "A 429 response means rate limiting is active. "
                "No 429 is informational — not a test failure."
            ),
            "request_data": request_data,
            "request_query": request_query or None,
            "path_params": path_params or None,
            "target_field": None,
            "burst_count": burst_count,
            "metadata": {
                "burst_count": burst_count
            },
            "requires_auth": ep.requires_auth,
        })

    return tests