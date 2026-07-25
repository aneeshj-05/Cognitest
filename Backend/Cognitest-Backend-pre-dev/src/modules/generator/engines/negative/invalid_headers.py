"""
Negative test generator — Invalid Headers & Content-Type.

For POST/PUT/PATCH endpoints that expect JSON, generates tests with:
  - Missing Content-Type header        (force_content_type = "__OMIT__")
  - Wrong Content-Type: text/xml       (force_content_type = "text/xml")
  - Wrong Content-Type: multipart      (force_content_type = "multipart/form-data")

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.

Changes from previous version:
  - REMOVED the `if endpoint.requires_auth: return tests` gate.
    Header tests must run on ALL endpoints, including protected ones.
    The runner already injects the real session JWT for authenticated
    endpoints — there is no reason to skip header mutation tests here.
"""
from __future__ import annotations

from typing import Any
import uuid

from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType
from .payload_generator import generate_valid_payload

import logging
logger = logging.getLogger(__name__)


def generate_invalid_header_tests(
    endpoint: Endpoint,
    spec: dict[str, Any] | None = None,
) -> list[dict]:
    """
    Generate tests with incorrect or missing HTTP headers.

    Applies to POST / PUT / PATCH endpoints that declare a body schema.
    Runs on both public AND authenticated endpoints (auth is injected
    by the runner, not here).

    Expected status codes are derived from the Swagger spec's responses section.
    If the spec does not define a relevant error status code, the test is skipped.
    """
    tests: list[dict] = []

    # Only body-mutation methods need Content-Type validation
    if endpoint.method not in ("POST", "PUT", "PATCH"):
        return tests

    if not endpoint.body_schema:
        return tests

    # Derive expected status from the spec — do not assume or hardcode
    resolved_status = get_expected_status(endpoint, 400)
    if resolved_status is None:
        return tests

    # Build a fully valid body — we want to isolate the header as the only mutation
    sample_body = generate_valid_payload(endpoint, spec=spec)
    if sample_body is None:
        logger.warning(
            "[InvalidHeaders] Skipping %s %s — generate_valid_payload returned None",
            endpoint.method, endpoint.path,
        )
        return tests

    # ── 1. Missing Content-Type header ────────────────────────────────────
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"Missing Content-Type header - {endpoint.method} {endpoint.path}",
        "mutation_type": MutationType.SCHEMA_TYPE_MISMATCH,
        "expected_status": [resolved_status],
        "test_type": "Negative",
        "category": "NEGATIVE",
        "sub_category": "INVALID_HEADERS",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "description": (
            f"Sends a {endpoint.method} request to {endpoint.path} with a "
            "valid JSON body but no Content-Type header. "
            f"The API should reject the request ({resolved_status})."
        ),
        "request_data": sample_body,
        "target_field": None,
        "force_content_type": "__OMIT__",
        "requires_auth": endpoint.requires_auth,
    })

    # ── 2. Wrong Content-Type: text/xml ───────────────────────────────────
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"Wrong Content-Type (text/xml) - {endpoint.method} {endpoint.path}",
        "mutation_type": MutationType.WRONG_CONTENT_TYPE,
        "expected_status": [resolved_status],
        "test_type": "Negative",
        "category": "NEGATIVE",
        "sub_category": "INVALID_HEADERS",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "description": (
            f"Sends a {endpoint.method} request to {endpoint.path} with "
            "Content-Type: text/xml instead of application/json. "
            f"The API should return {resolved_status}."
        ),
        "request_data": sample_body,
        "target_field": None,
        "force_content_type": "text/xml",
        "requires_auth": endpoint.requires_auth,
    })

    # ── 3. Wrong Content-Type: multipart/form-data ────────────────────────
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"Wrong Content-Type (multipart/form-data) - {endpoint.method} {endpoint.path}",
        "mutation_type": MutationType.WRONG_CONTENT_TYPE,
        "expected_status": [resolved_status],
        "test_type": "Negative",
        "category": "NEGATIVE",
        "sub_category": "INVALID_HEADERS",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "description": (
            f"Sends a {endpoint.method} request to {endpoint.path} with "
            "Content-Type: multipart/form-data instead of application/json. "
            f"The API should return {resolved_status}."
        ),
        "request_data": sample_body,
        "target_field": None,
        "force_content_type": "multipart/form-data",
        "requires_auth": endpoint.requires_auth,
    })

    return tests