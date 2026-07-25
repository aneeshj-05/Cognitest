"""
Pagination, filtering, and sorting test generators.

Generates functional tests for pagination-related behavior:
- Detects pagination params (page, limit, offset, sort, order, etc.)
- Tests with valid pagination values
- Tests boundary values (page=0, limit=0, negative values)
- Tests sorting parameter behavior
"""
import uuid

from ...spec_parser import Endpoint, get_expected_status


# Common pagination-related parameter names
PAGINATION_PARAMS = {"page", "limit", "offset", "per_page", "perPage", "pageSize", "page_size", "skip", "take"}
SORT_PARAMS = {"sort", "sortBy", "sort_by", "order", "orderBy", "order_by", "direction"}
FILTER_PARAMS = {"filter", "search", "q", "query", "status", "type", "category"}


def generate_pagination_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate pagination, filtering, and sorting tests for an endpoint.

    Only generates tests for GET endpoints that accept pagination-related
    query parameters.
    """
    tests = []
    expected_ok = get_expected_status(endpoint, 200)
    if not expected_ok:
        return tests

    # Only test GET endpoints (list endpoints)
    if endpoint.method != "GET":
        return tests

    param_names = {p.get("name", "").lower(): p.get("name", "") for p in endpoint.query_params}

    # Detect pagination params
    detected_pagination = {
        original: param_names[lower]
        for lower, original in param_names.items()
        if lower in {p.lower() for p in PAGINATION_PARAMS}
    }

    # Detect sort params
    detected_sort = {
        original: param_names[lower]
        for lower, original in param_names.items()
        if lower in {p.lower() for p in SORT_PARAMS}
    }

    # Detect filter params
    detected_filter = {
        original: param_names[lower]
        for lower, original in param_names.items()
        if lower in {p.lower() for p in FILTER_PARAMS}
    }

    # --- Pagination tests ---
    if detected_pagination:
        pagination_param_names = list(detected_pagination.values())

        # Valid pagination
        valid_query: dict[str, str] = {}
        for pname in pagination_param_names:
            pname_lower = pname.lower()
            if pname_lower in ("page", "page_size", "per_page", "perpage", "pagesize"):
                valid_query[pname] = "1"
            elif pname_lower in ("limit", "take"):
                valid_query[pname] = "10"
            elif pname_lower in ("offset", "skip"):
                valid_query[pname] = "0"

        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"GET {endpoint.path} — valid pagination params → {expected_ok}",
            "test_type": "Functional",
            "endpoint_path": endpoint.path,
            "method": "GET",
            "expected_status": expected_ok,
            "description": (
                f"Tests pagination with valid values: {valid_query}. "
                f"Should return paginated results."
            ),
            "request_query": valid_query,
            "assertions": [
                f"Status code is {expected_ok}",
                "Response contains paginated results",
                "Result count respects the limit/page_size",
            ],
        })

        # Boundary: page=0 or offset=-1
        expected_err = get_expected_status(endpoint, 400)
        if expected_err:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"GET {endpoint.path} — boundary pagination (page=0) → {expected_err}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": "GET",
                "expected_status": expected_err,
                "description": (
                    f"Tests pagination with boundary value page=0. "
                    f"Should return {expected_err} or handle gracefully."
                ),
                "request_query": {pagination_param_names[0]: "0"},
                "assertions": [
                    f"Status code is {expected_err} or results are handled gracefully",
                    "No server error (500) occurs",
                ],
            })

        # Boundary: very large limit
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"GET {endpoint.path} — very large limit → {expected_ok}",
            "test_type": "Functional",
            "endpoint_path": endpoint.path,
            "method": "GET",
            "expected_status": expected_ok,
            "description": (
                f"Tests with an excessively large limit (999999). "
                f"Server should cap or handle gracefully."
            ),
            "request_query": {pagination_param_names[0]: "999999"},
            "assertions": [
                f"Status code is {expected_ok} or 400",
                "Server does not return unbounded results",
                "Response time remains acceptable",
            ],
        })

        # Boundary: negative values
        expected_err = get_expected_status(endpoint, 400)
        if expected_err:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"GET {endpoint.path} — negative pagination value → {expected_err}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": "GET",
                "expected_status": expected_err,
                "description": (
                    f"Tests pagination with negative value (-1). "
                    f"Should return {expected_err}."
                ),
                "request_query": {pagination_param_names[0]: "-1"},
                "assertions": [
                    f"Status code is {expected_err}",
                    "Error message indicates invalid pagination value",
                ],
            })

    # --- Sorting tests ---
    if detected_sort:
        sort_param = list(detected_sort.values())[0]

        # Valid ascending sort
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"GET {endpoint.path} — sort ascending → {expected_ok}",
            "test_type": "Functional",
            "endpoint_path": endpoint.path,
            "method": "GET",
            "expected_status": expected_ok,
            "description": (
                f"Tests sorting with ascending order via '{sort_param}' parameter."
            ),
            "request_query": {sort_param: "asc"},
            "assertions": [
                f"Status code is {expected_ok}",
                "Results are returned in ascending order",
            ],
        })

        # Valid descending sort
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"GET {endpoint.path} — sort descending → {expected_ok}",
            "test_type": "Functional",
            "endpoint_path": endpoint.path,
            "method": "GET",
            "expected_status": expected_ok,
            "description": (
                f"Tests sorting with descending order via '{sort_param}' parameter."
            ),
            "request_query": {sort_param: "desc"},
            "assertions": [
                f"Status code is {expected_ok}",
                "Results are returned in descending order",
            ],
        })

        # Invalid sort value
        expected_err = get_expected_status(endpoint, 400)
        if expected_err:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"GET {endpoint.path} — invalid sort value → {expected_err}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": "GET",
                "expected_status": expected_err,
                "description": (
                    f"Tests sorting with an invalid value 'invalid_sort'. "
                    f"Should return {expected_err} or ignore gracefully."
                ),
                "request_query": {sort_param: "invalid_sort"},
                "assertions": [
                    f"Status code is {expected_err} or invalid sort is silently ignored",
                    "No server error (500) occurs",
                ],
            })

    # --- Filter tests ---
    if detected_filter:
        filter_param = list(detected_filter.values())[0]

        # Valid filter
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"GET {endpoint.path} — valid filter param '{filter_param}' → {expected_ok}",
            "test_type": "Functional",
            "endpoint_path": endpoint.path,
            "method": "GET",
            "expected_status": expected_ok,
            "description": (
                f"Tests filtering with a valid value for '{filter_param}'. "
                f"Should return filtered results."
            ),
            "request_query": {filter_param: "test_filter"},
            "assertions": [
                f"Status code is {expected_ok}",
                f"Results are filtered by '{filter_param}'",
                "Non-matching results are excluded",
            ],
        })

        # Empty filter
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"GET {endpoint.path} — empty filter param '{filter_param}' → {expected_ok}",
            "test_type": "Functional",
            "endpoint_path": endpoint.path,
            "method": "GET",
            "expected_status": expected_ok,
            "description": (
                f"Tests filtering with an empty value for '{filter_param}'. "
                f"Should return all results or handle gracefully."
            ),
            "request_query": {filter_param: ""},
            "assertions": [
                f"Status code is {expected_ok}",
                "Empty filter returns all results or is handled gracefully",
            ],
        })

    return tests
    return tests
