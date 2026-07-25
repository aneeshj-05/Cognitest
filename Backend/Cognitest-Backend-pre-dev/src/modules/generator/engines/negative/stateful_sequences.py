from __future__ import annotations

import re
import uuid
from typing import Any

from src.modules.generator.spec_parser import Endpoint

from .payload_generator import generate_valid_payload
from .sequence_lifecycle import LIFECYCLE_RULES, SequenceType




def generate_create_then_get_tests(
    endpoint: Endpoint,
    all_endpoints: list[Endpoint],
    spec: dict[str, Any] | None = None,
) -> list[dict]:
    if endpoint.method != "POST" or not endpoint.body_schema:
        return []

    payload = generate_valid_payload(endpoint, spec=spec)
    if payload is None:
        return []

    get_ep = _find_matching_endpoint(endpoint, all_endpoints, "GET")
    if not get_ep:
        return []

    sequence_type = SequenceType.CREATE_THEN_GET.value
    validations = LIFECYCLE_RULES[sequence_type]["step_validations"]
    
    return [
        _make_sequence_case(
            endpoint=endpoint,
            sequence_type=sequence_type,
            mutation_type="STATEFUL_SEQUENCE",
            name=f"Create then get - {endpoint.path}",
            steps=[
                _make_step(
                    name="create",
                    method="POST",
                    endpoint_path=endpoint.path,
                    payload=payload,
                    expected_status=validations[0],
                    auth_token_source="real_session_token" if endpoint.requires_auth else "none",
                    capture_resource=True,
                    body_schema=endpoint.body_schema,
                ),
                _make_step(
                    name="get",
                    method="GET",
                    endpoint_path=get_ep.path,
                    expected_status=validations[1],
                    path_param_from="previous_id",
                    auth_token_source="real_session_token" if get_ep.requires_auth else "none",
                ),
            ],
        )
    ]


def generate_create_then_delete_then_get_tests(
    endpoint: Endpoint,
    all_endpoints: list[Endpoint],
    spec: dict[str, Any] | None = None,
) -> list[dict]:
    if endpoint.method != "POST" or not endpoint.body_schema:
        return []

    payload = generate_valid_payload(endpoint, spec=spec)
    if payload is None:
        return []

    delete_ep = _find_matching_endpoint(endpoint, all_endpoints, "DELETE")
    get_ep = _find_matching_endpoint(endpoint, all_endpoints, "GET")
    if not delete_ep or not get_ep:
        return []

    sequence_type = SequenceType.CREATE_THEN_DELETE_THEN_GET.value
    validations = LIFECYCLE_RULES[sequence_type]["step_validations"]
    
    return [
        _make_sequence_case(
            endpoint=endpoint,
            sequence_type=sequence_type,
            mutation_type="STATEFUL_SEQUENCE",
            name=f"Create, delete, then get - {endpoint.path}",
            steps=[
                _make_step(
                    name="create",
                    method="POST",
                    endpoint_path=endpoint.path,
                    payload=payload,
                    expected_status=validations[0],
                    auth_token_source="real_session_token" if endpoint.requires_auth else "none",
                    capture_resource=True,
                    body_schema=endpoint.body_schema,
                ),
                _make_step(
                    name="delete",
                    method="DELETE",
                    endpoint_path=delete_ep.path,
                    expected_status=validations[1],
                    path_param_from="previous_id",
                    auth_token_source="real_session_token" if delete_ep.requires_auth else "none",
                ),
                _make_step(
                    name="get_after_delete",
                    method="GET",
                    endpoint_path=get_ep.path,
                    expected_status=validations[2],
                    path_param_from="previous_id",
                    auth_token_source="real_session_token" if get_ep.requires_auth else "none",
                ),
            ],
        )
    ]


def generate_create_duplicate_tests(endpoint: Endpoint, spec: dict[str, Any] | None = None) -> list[dict]:
    if endpoint.method != "POST" or not endpoint.body_schema:
        return []

    payload = generate_valid_payload(endpoint, spec=spec)
    if payload is None:
        return []

    sequence_type = SequenceType.CREATE_DUPLICATE.value
    validations = LIFECYCLE_RULES[sequence_type]["step_validations"]
    
    return [
        _make_sequence_case(
            endpoint=endpoint,
            sequence_type=sequence_type,
            mutation_type="STATEFUL_SEQUENCE",
            name=f"Duplicate create - {endpoint.method} {endpoint.path}",
            steps=[
                _make_step(
                    name="create",
                    method="POST",
                    endpoint_path=endpoint.path,
                    payload=payload,
                    expected_status=validations[0],
                    auth_token_source="real_session_token" if endpoint.requires_auth else "none",
                    capture_resource=True,
                    body_schema=endpoint.body_schema,
                ),
                _make_step(
                    name="duplicate_create",
                    method="POST",
                    endpoint_path=endpoint.path,
                    payload=payload,
                    expected_status=validations[1],
                    auth_token_source="real_session_token" if endpoint.requires_auth else "none",
                    body_schema=endpoint.body_schema,
                ),
            ],
        )
    ]


def generate_stateful_sequence_tests(
    endpoint: Endpoint,
    all_endpoints: list[Endpoint],
    spec: dict[str, Any] | None = None,
) -> list[dict]:
    return generate_create_then_get_tests(endpoint, all_endpoints, spec=spec) + generate_create_then_delete_then_get_tests(endpoint, all_endpoints, spec=spec)


def generate_duplicate_tests(endpoint: Endpoint, spec: dict[str, Any] | None = None) -> list[dict]:
    return generate_create_duplicate_tests(endpoint, spec=spec)


def _make_sequence_case(
    *,
    endpoint: Endpoint,
    sequence_type: str,
    mutation_type: str,
    name: str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    step_validations = list(LIFECYCLE_RULES[sequence_type]["step_validations"])
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "type": "SEQUENCE",
        "sequence_type": sequence_type,
        "mutation_type": mutation_type,
        "sub_category": "STATEFUL_SEQUENCE",
        "expected_status": step_validations,
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "payload": steps[0].get("payload"),
        "request_body": steps[0].get("payload"),
        "request_data": steps[0].get("payload"),
        "target_field": None,
        "description": "Strict lifecycle sequence test",
        "test_type": "Negative",
        "category": "NEGATIVE",
        "steps": steps,
        "requires_auth": endpoint.requires_auth,
    }


def _make_step(
    *,
    name: str,
    method: str,
    endpoint_path: str,
    expected_status: Any,
    auth_token_source: str,
    payload: dict | list | str | None = None,
    path_param_from: str | None = None,
    capture_resource: bool = False,
    capture_field: list[str] | str = ("id", "_id", "uuid", "resourceId"),
    body_schema: dict | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "name": name,
        "method": method,
        "endpoint_path": endpoint_path,
        "expected_status": expected_status,
        "auth": "primary",
        "auth_token_source": auth_token_source,
        "payload": payload,
        "request_body": payload,
        "request_data": payload,
        "capture_resource": capture_resource,
    }
    
    if capture_resource:
        if isinstance(capture_field, str):
            capture_field = [capture_field]
        step["capture_field"] = list(capture_field)

    if path_param_from is not None:
        step["path_param_from"] = path_param_from

    # Store body schema for deferred payload regeneration at execution time.
    # This allows _execute_sequence_case to generate fresh unique payloads
    # on every run (avoiding stale email/unique-constraint collisions).
    if body_schema is not None:
        step["_body_schema"] = body_schema

    return step


def _find_matching_endpoint(source: Endpoint, endpoints: list[Endpoint], method: str) -> Endpoint | None:
    base = source.path.rstrip("/")
    matches = []
    for ep in endpoints:
        if ep.method != method:
            continue
        if not (ep.path.startswith(base + "/") or ep.path == base):
            continue
        if "{" not in ep.path:
            continue
        matches.append(ep)
        
    if not matches:
        return None
        
    matches.sort(key=lambda ep: len(ep.path))
    return matches[0]
