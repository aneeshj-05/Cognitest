"""
Negative test generator — Unsupported HTTP Methods.

For each path in the spec, determines which methods are NOT defined
and generates a test expecting 405 Method Not Allowed.

Expected status codes are derived from the Swagger spec's responses section.
For undefined methods, we check if ANY defined endpoint on the same path
declares a 405 response. If not, the test is skipped.
"""
import os
import uuid
from typing import Any
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType

ALL_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}


def generate_invalid_method_tests(
    spec: dict[str, Any],
    endpoints: list[Endpoint],
) -> list[dict]:
    """
    Generate tests that send unsupported HTTP methods.

    This is a spec-level generator (not per-endpoint) because it needs
    to compare defined methods against the full set.

    Expected status codes are derived from the Swagger spec's responses section.
    For each path, we check if any defined endpoint declares a 405 response.
    If the spec does not define 405 for any endpoint on that path, tests are skipped.
    """
    tests: list[dict] = []

    defined: dict[str, set[str]] = {}
    path_endpoints: dict[str, list[Endpoint]] = {}
    for ep in endpoints:
        defined.setdefault(ep.path, set()).add(ep.method)
        path_endpoints.setdefault(ep.path, []).append(ep)

    for path, methods in defined.items():
        unsupported = {"GET", "POST", "PUT", "PATCH", "DELETE"} - methods
        limit = int(os.environ.get("NEGATIVE_TEST_MAX_METHODS_PER_PATH", "2"))

        # Derive expected status from the spec using any defined endpoint on this path
        resolved_status = None
        for ep in path_endpoints[path]:
            resolved_status = get_expected_status(ep, 405)
            if resolved_status is not None:
                break

        # If no defined endpoint on this path declares 405, skip
        if resolved_status is None:
            continue

        for method in sorted(unsupported)[:limit]:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"Unsupported method {method} - {path}",
                "mutation_type": MutationType.METHOD_NOT_ALLOWED,
                "expected_status": [resolved_status],
                "test_type": "Negative",
                "category": "NEGATIVE",
                "sub_category": "UNSUPPORTED_METHOD",
                "endpoint_path": path,
                "method": method,
                "description": (
                    f"Sends a {method} request to {path} which does not define "
                    f"that method. The API should return {resolved_status}."
                ),
                "request_data": None,
                "target_field": None,
                "requires_auth": any(ep.requires_auth for ep in endpoints if ep.path == path),
            })

    return tests
