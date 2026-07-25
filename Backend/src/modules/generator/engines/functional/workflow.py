"""
Multi-step workflow and API chaining test generators.

Generates tests that validate multi-step API workflows with real variable
extraction and injection between steps:

- Register → Login → Authenticated request (token chaining)
- Create → Read (verify ID consistency)
- Create → Update → Read (verify mutation)
- Create → Delete → Read (verify deletion / 404)
- Business flow: Add-to-cart → Checkout → Pay → Verify state
  (CART → CHECKOUT → PAYMENT_PENDING → CONFIRMED)

Each step supports:
  extract:      JSONPath rules to pull values from response body
  inject_vars:  {{var}} placeholders in body/path/headers resolved from context
  assertions:   Declarative checks on status + extracted state
"""
from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any

from ...spec_parser import Endpoint, get_expected_status
from src.modules.generator.services.data_provider import data_provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    """One HTTP call inside a multi-step workflow."""
    step_id: str
    name: str
    method: str
    endpoint_path: str
    expected_status: int
    # Request parts — may contain {{variable}} placeholders
    request_headers: dict[str, str] | None = None
    request_body: dict[str, Any] | None = None
    request_query: dict[str, Any] | None = None
    path_params: dict[str, str] | None = None
    # Variable extraction: {"token": "$.data.token", "userId": "$.data.id"}
    extract: dict[str, str] = field(default_factory=dict)
    # Variables that MUST exist in context before this step runs
    depends_on: list[str] = field(default_factory=list)
    assertions: list[str] = field(default_factory=list)
    # Optional expected state label (for state-machine workflows)
    expected_state: str | None = None


@dataclass
class WorkflowTest:
    """A complete multi-step workflow test case."""
    id: str
    name: str
    description: str
    steps: list[WorkflowStep]
    # State machine labels in order (e.g. CART → CHECKOUT → PAYMENT_PENDING → CONFIRMED)
    state_machine: list[str] = field(default_factory=list)
    test_type: str = "Functional"
    category: str = "workflow"
    # Flat compatibility fields (point to step 0) for TestCaseOut schema
    endpoint_path: str = ""
    method: str = ""
    expected_status: int = 200
    request_body: dict | None = None
    assertions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = [asdict(s) for s in self.steps]
        return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


def _group_endpoints_by_resource(endpoints: list[Endpoint]) -> dict[str, dict[str, Endpoint]]:
    """
    Group endpoints by resource path prefix and method.

    /api/users and /api/users/{id} share the prefix '/api/users'.
    Returns: { "/api/users": { "GET": ep, "POST": ep, ... } }
    """
    groups: dict[str, dict[str, Endpoint]] = defaultdict(dict)
    for ep in endpoints:
        parts = ep.path.rstrip("/").split("/")
        base_parts = [p for p in parts if not p.startswith("{")]
        base = "/".join(base_parts) if base_parts else ep.path
        groups[base][ep.method] = ep
    return dict(groups)


def _sample_body(body_schema: dict[str, Any] | None) -> dict | None:
    """Generate a realistic sample body from a JSON schema."""
    if not body_schema:
        return None
    props = body_schema.get("properties", {})
    if not props:
        return None
    sample: dict[str, Any] = {}
    for fname, fschema in props.items():
        ftype = fschema.get("type", "string")
        sample[fname] = data_provider.get_sample_value(fname, ftype, fschema)
    
    # Ensure we never send an empty body if a schema is present
    if not sample and body_schema:
        if isinstance(body_schema, dict) and (body_schema.get("properties") or body_schema.get("type") == "object"):
            return {"_placeholder": "REQUIRED_JSON_PAYLOAD"}
        return {"data": "required"}
    return sample or {"payload": "mandatory"}


def _detect_auth_endpoints(endpoints: list[Endpoint]) -> tuple[Endpoint | None, Endpoint | None]:
    """
    Heuristically find register and login endpoints.
    Looks for POST endpoints whose paths contain 'register' or 'login'/'signin'.
    """
    register_ep = None
    login_ep = None
    for ep in endpoints:
        if ep.method != "POST":
            continue
        path_lower = ep.path.lower()
        # Signup: POST to /signup, /register, etc.
        if any(kw in path_lower for kw in ("register", "signup", "sign-up")):
            register_ep = ep
        # Login: POST to /login, /signin, /auth, /token
        # But EXCLUDE password reset, verification, or forgot password paths
        elif any(kw in path_lower for kw in ("login", "signin", "auth", "authenticate", "token")):
            if not any(noise in path_lower for noise in ("reset", "forgot", "verify", "password", "email", "otp")):
                login_ep = ep
    return register_ep, login_ep


def _sample_path_params(ep: Endpoint) -> dict:
    """Generate path parameters with extraction placeholders where possible."""
    params = {}
    from src.modules.generator.services.data_provider import data_provider
    
    # Known variables that we expect to be in context
    KNOWN_VARS = {"auth_token", "created_id", "registered_user_id", "order_id", "cart_id", "payment_id"}
    
    for p in ep.path_params:
        p_lower = p.lower()
        # If it's a known chaining variable, use placeholder
        if p in KNOWN_VARS:
            params[p] = f"{{{{{p}}}}}"
        elif p_lower == "id" or p_lower == "userid":
             # If it's just 'id', try to use {{created_id}} or {{registered_user_id}} as a default chaining guess
             params[p] = "{{created_id}}" if "created_id" in KNOWN_VARS else "{{registered_user_id}}"
        else:
            # Fallback to realistic sample data
            params[p] = data_provider.get_sample_value(p, "string")
            
    return params


def _is_admin_endpoint(ep: Endpoint) -> bool:
    """Check if an endpoint is an admin-only route."""
    return "/admin" in ep.path.lower()


def _endpoint_needs_auth(ep: Endpoint) -> bool:
    """Check if endpoint requires authentication via spec or path heuristics."""
    if ep.requires_auth:
        return True
    # Heuristic: common protected path patterns
    path_lower = ep.path.lower()
    protected_patterns = (
        "/cart", "/orders", "/checkout", "/profile",
        "/account", "/wishlist", "/favorites", "/settings",
        "/admin", "/dashboard", "/payments", "/subscriptions",
    )
    return any(p in path_lower for p in protected_patterns)


def _inject_auth_into_step(step: WorkflowStep) -> WorkflowStep:
    """Add auth dependency and multiple common Authorization headers to a workflow step."""
    if "auth_token" not in step.depends_on:
        step.depends_on.append("auth_token")
    if step.request_headers is None:
        step.request_headers = {}
    
    # Generic injection for broad compatibility
    step.request_headers["Authorization"] = "Bearer {{auth_token}}"
    step.request_headers["x-auth-token"] = "{{auth_token}}"
    step.request_headers["x-api-key"] = "{{auth_token}}"
    return step


def _workflow_needs_auth_token(steps: list[WorkflowStep]) -> bool:
    for s in steps:
        if "auth_token" in (s.depends_on or []):
            return True
        if s.request_headers:
            for v in s.request_headers.values():
                if "{{auth_token}}" in str(v):
                    return True
    return False


def _workflow_extracts_auth_token(steps: list[WorkflowStep]) -> bool:
    return any("auth_token" in (s.extract or {}) for s in steps)


def _renumber_step_names(steps: list[WorkflowStep]) -> None:
    prefix_re = re.compile(r"^Step\s+\d+\s*:\s*(.*)$")
    for i, s in enumerate(steps, start=1):
        m = prefix_re.match(s.name or "")
        if not m:
            continue
        s.name = f"Step {i}: {m.group(1)}"


def _build_auth_prereq_steps(
    register_ep: Endpoint | None,
    login_ep: Endpoint | None,
) -> list[WorkflowStep]:
    """Minimal auth init: (optional) register -> login -> extract auth_token."""
    if not login_ep:
        return []

    steps: list[WorkflowStep] = []
    reg_body = {}

    if register_ep:
        reg_body = _sample_body(register_ep.body_schema) or {}
        
        # Ensure email/password are present if they appear in the schema properties
        props = register_ep.body_schema.get("properties", {}) if register_ep.body_schema else {}
        
        # If reg_body is still empty but we have properties, populate them
        if not reg_body and props:
            for k, v in props.items():
                reg_body[k] = data_provider.get_sample_value(k, v.get("type", "string"), v)

        # Force injection of placeholders for chaining
        found_email = False
        for k in list(reg_body.keys()):
            k_lower = k.lower()
            if "email" in k_lower:
                reg_body[k] = "{{email}}"
                found_email = True
            elif "password" in k_lower or "passcode" in k_lower:
                reg_body[k] = "Test@123"
        
        # Heuristic fallback: if no email field was found but it's likely a signup, add it
        if not found_email and not reg_body:
            reg_body = {"email": "{{email}}", "password": "Test@123", "name": "Test User"}

        expected_reg_status = get_expected_status(register_ep, 201)
        if expected_reg_status:
            steps.append(WorkflowStep(
                step_id=_new_id(),
                name=f"Step 1: Register new user at {register_ep.path}",
                method="POST",
                endpoint_path=register_ep.path,
                expected_status=expected_reg_status,
                path_params=_sample_path_params(register_ep),
                request_headers={"Content-Type": "application/json"},
                request_body=reg_body,
                extract={
                    "auth_token": "$.token || $.access_token || $.data.token || $.data.access_token || $.accessToken || $.jwt || $.id_token || $.auth_token",
                    "registered_user_id": "$.data.id || $.userId || $.id || $.user.id", 
                    "registered_email": "$.data.email || $.email"
                },
                assertions=[
                    f"Status code is {expected_reg_status} (or 409/422 if Duplicate user handled gracefully)",
                    "Response contains user ID",
                ],
            ))

    login_body = {}
    if login_ep.body_schema:
        # Re-use credential fields from reg_body if available
        login_props = login_ep.body_schema.get("properties", {})
        for k in login_props:
            if k in reg_body:
                login_body[k] = reg_body[k]
        
        # Fallback if no matching fields were found
        if not login_body:
            login_body = _sample_body(login_ep.body_schema) or {}
            for k in list(login_body.keys()):
                k_lower = k.lower()
                if "email" in k_lower:
                    login_body[k] = "{{email}}"
                elif "password" in k_lower or "passcode" in k_lower:
                    login_body[k] = "Test@123"
    
    # Final fallback for login
    if not login_body:
        login_body = {"email": "{{email}}", "password": "Test@123"}

    expected_login_status = get_expected_status(login_ep, 200)
    if expected_login_status:
        steps.append(WorkflowStep(
            step_id=_new_id(),
            name=f"Step {len(steps)+1}: Login at {login_ep.path} (using same credentials)",
            method="POST",
            endpoint_path=login_ep.path,
            expected_status=expected_login_status,
            path_params=_sample_path_params(login_ep),
            request_headers={"Content-Type": "application/json"},
            request_body=login_body,
            extract={
                "auth_token": "$.token || $.access_token || $.data.token || $.data.access_token || $.accessToken || $.jwt || $.id_token || $.auth_token",
                "token_type": "$.data.token_type || $.token_type",
                "logged_user_id": "$.data.user.id || $.user.id",
            },
            assertions=[
                f"Status code is {expected_login_status}",
                "Response contains auth token",
                "Token is non-empty string",
            ],
        ))

    return steps


# ---------------------------------------------------------------------------
# Workflow builders
# ---------------------------------------------------------------------------

def _build_auth_workflow(
    register_ep: Endpoint | None,
    login_ep: Endpoint | None,
    all_endpoints: list[Endpoint] | None = None,
) -> WorkflowTest | None:
    """
    Workflow: Register → Login → Extract token → Authenticated GET on a real protected endpoint.

    Step 3 picks the first `requires_auth` GET endpoint from the spec so the test
    actually validates that the extracted token is accepted by a protected route.
    """
    if not login_ep:
        return None

    steps: list[WorkflowStep] = []
    reg_body = {}

    # Step 1: Register (optional)
    if register_ep:
        reg_body = _sample_body(register_ep.body_schema) or {}
        # Dynamically inject credentials only if the fields exist in the schema
        for k in reg_body.keys():
            k_lower = k.lower()
            if "email" in k_lower:
                reg_body[k] = "{{email}}"
            elif "password" in k_lower or "passcode" in k_lower:
                reg_body[k] = "Test@123"

        expected_reg_status = get_expected_status(register_ep, 201)
        if expected_reg_status:
            steps.append(WorkflowStep(
                step_id=_new_id(),
                name=f"Step 1: Register new user at {register_ep.path}",
                method="POST",
                endpoint_path=register_ep.path,
                expected_status=expected_reg_status,
                path_params=_sample_path_params(register_ep),
                request_headers={"Content-Type": "application/json"},
                request_body=reg_body,
                extract={
                    "auth_token": "$.token || $.access_token || $.data.token || $.data.access_token || $.accessToken || $.jwt || $.id_token || $.auth_token",
                    "registered_user_id": "$.data.id || $.userId || $.id || $.user.id", 
                    "registered_email": "$.data.email || $.email"
                },
                assertions=[
                    f"Status code is {expected_reg_status} (or 409/422 if Duplicate user handled gracefully)",
                    "Response contains user ID",
                ],
            ))

    # Step 2: Login → extract token (reusing same payload/credentials from Step 1)
    login_body = {}
    if login_ep.body_schema:
        # Re-use credential fields from reg_body if available (Step 1)
        login_props = login_ep.body_schema.get("properties", {})
        for k in login_props:
            if k in reg_body:
                login_body[k] = reg_body[k]
        
        # Fallback if no matching fields were found
        if not login_body:
            login_body = _sample_body(login_ep.body_schema) or {}
            for k in login_body.keys():
                k_lower = k.lower()
                if "email" in k_lower:
                    login_body[k] = "{{email}}"
                elif "password" in k_lower or "passcode" in k_lower:
                    login_body[k] = "Test@123"

    expected_login_status = get_expected_status(login_ep, 200)
    if expected_login_status:
        steps.append(WorkflowStep(
            step_id=_new_id(),
            name=f"Step {len(steps)+1}: Login at {login_ep.path} (using same credentials)",
            method="POST",
            endpoint_path=login_ep.path,
            expected_status=expected_login_status,
            path_params=_sample_path_params(login_ep),
            request_headers={"Content-Type": "application/json"},
            request_body=login_body,
            extract={
                "auth_token": "$.token || $.access_token || $.data.token || $.data.access_token || $.accessToken || $.jwt || $.id_token || $.auth_token",
                "token_type": "$.data.token_type || $.token_type",
                "logged_user_id": "$.data.user.id || $.user.id || $.userId || $.id",
            },
            assertions=[
                f"Status code is {expected_login_status}",
                "Response contains auth token",
                "Token is non-empty string",
            ],
        ))

    # Step 3: Use token to make an authenticated request on a REAL protected endpoint
    # Pick the first GET endpoint that requires auth (no path params preferred → collection list)
    protected_get: Endpoint | None = None
    if all_endpoints:
        # Prefer a collection (no path params) GET that requires auth
        for ep in all_endpoints:
            if ep.method == "GET" and ep.requires_auth and not ep.path_params:
                # Skip the login/register paths themselves
                if not any(kw in ep.path.lower() for kw in ("login", "register", "signup", "token")):
                    protected_get = ep
                    break
        # Fallback: any GET that requires auth
        if not protected_get:
            for ep in all_endpoints:
                if ep.method == "GET" and ep.requires_auth:
                    if not any(kw in ep.path.lower() for kw in ("login", "register", "signup", "token")):
                        protected_get = ep
                        break

    auth_get_path = protected_get.path if protected_get else "/api/me"
    auth_get_name = protected_get.path if protected_get else "protected resource"
    expected_get_status = get_expected_status(protected_get, 200) if protected_get else 200

    if expected_get_status:
        steps.append(WorkflowStep(
            step_id=_new_id(),
            name=f"Step {len(steps)+1}: Authenticated GET on {auth_get_name} with extracted token",
            method="GET",
            endpoint_path=auth_get_path,
            expected_status=expected_get_status,
            path_params=_sample_path_params(protected_get) if protected_get else {},
            request_headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {{auth_token}}",
            },
            depends_on=["auth_token"],
            assertions=[
                f"Status code is {expected_get_status}",
                "Token is accepted — not 401",
            ],
        ))

    first_step = steps[0]
    return WorkflowTest(
        id=_new_id(),
        name=f"Workflow: Register → Login → Authenticated Request",
        description=(
            "Multi-step auth flow: "
            "1) Register a new user account, "
            "2) Login to receive an auth token, "
            "3) Use extracted token in an authenticated GET request — "
            "validates token issuance and acceptance."
        ),
        steps=steps,
        state_machine=[],
        endpoint_path=first_step.endpoint_path,
        method=first_step.method,
        expected_status=first_step.expected_status,
        request_body=first_step.request_body,
        assertions=["Token extracted and reused across steps"],
    )


def _build_create_read_workflow(post_ep: Endpoint, get_ep: Endpoint, resource_base: str) -> WorkflowTest:
    """Workflow: Create → Read (verify ID and data consistency)."""
    sample_body = _sample_body(post_ep.body_schema) or {}
    needs_auth = _endpoint_needs_auth(post_ep) or _endpoint_needs_auth(get_ep)

    # Determine path param name for GET
    get_path_param = next(iter(get_ep.path_params), "id") if get_ep.path_params else "id"
    get_path = get_ep.path  # e.g. /api/users/{id}

    expected_post_status = get_expected_status(post_ep, 201)
    if not expected_post_status: return None
    
    step1 = WorkflowStep(
        step_id=_new_id(),
        name=f"Step 1: POST {post_ep.path} — create resource",
        method="POST",
        endpoint_path=post_ep.path,
        expected_status=expected_post_status,
        path_params=_sample_path_params(post_ep),
        request_headers={"Content-Type": getattr(post_ep, 'content_type', 'application/json')},
        request_body=sample_body,
        extract={"created_id": "$.data.id", "created_item": "$.data"},
        assertions=[
            f"Status code is {expected_post_status}",
            "Response contains created resource with ID",
        ],
    )

    expected_get_status = get_expected_status(get_ep, 200)
    if not expected_get_status: return None

    step2 = WorkflowStep(
        step_id=_new_id(),
        name=f"Step 2: GET {get_path} — read back created resource",
        method="GET",
        endpoint_path=get_path,
        expected_status=expected_get_status,
        path_params={**_sample_path_params(get_ep), get_path_param: "{{created_id}}"},
        depends_on=["created_id"],
        extract={"read_id": "$.data.id"},
        assertions=[
            f"Status code is {expected_get_status}",
            "Returned resource ID matches created_id",
            "Data fields match submitted values",
        ],
    )

    steps = [step1, step2]
    if needs_auth:
        steps = [_inject_auth_into_step(s) for s in steps]

    return WorkflowTest(
        id=_new_id(),
        name=f"Workflow: Create → Read at {resource_base}",
        description=(
            f"Multi-step consistency check: "
            f"1) POST {post_ep.path} to create a resource, "
            f"2) GET {get_path} using extracted ID — "
            f"verifies the resource persists and data matches."
        ),
        steps=steps,
        endpoint_path=post_ep.path,
        method="POST",
        expected_status=expected_post_status,
        request_body=steps[0].request_body,
        assertions=[
            "Created resource is immediately readable",
            "ID from POST matches ID from GET",
        ],
    )


def _build_create_update_read_workflow(
    post_ep: Endpoint,
    update_ep: Endpoint,
    get_ep: Endpoint,
    resource_base: str,
    update_method: str,
) -> WorkflowTest:
    """Workflow: Create → Update → Read (verify mutation applied)."""
    create_body = _sample_body(post_ep.body_schema) or {}
    update_body = _sample_body(update_ep.body_schema) or {}
    needs_auth = (
        _endpoint_needs_auth(post_ep)
        or _endpoint_needs_auth(update_ep)
        or _endpoint_needs_auth(get_ep)
    )

    # Mark update values distinctly
    for k in update_body:
        if isinstance(update_body[k], str):
            update_body[k] = f"updated_{k}"

    path_param = next(iter(update_ep.path_params), "id") if update_ep.path_params else "id"

    expected_post_status = get_expected_status(post_ep, 201)
    expected_update_status = get_expected_status(update_ep, 200)
    expected_get_status = get_expected_status(get_ep, 200)

    if not all([expected_post_status, expected_update_status, expected_get_status]):
        return None

    steps = [
        WorkflowStep(
            step_id=_new_id(),
            name=f"Step 1: POST {post_ep.path} — create resource",
            method="POST",
            endpoint_path=post_ep.path,
            expected_status=expected_post_status,
            path_params=_sample_path_params(post_ep),
            request_headers={"Content-Type": getattr(post_ep, 'content_type', 'application/json')},
            request_body=create_body,
            extract={"created_id": "$.data.id"},
            assertions=[f"Status code is {expected_post_status}", "Resource created with an ID"],
        ),
        WorkflowStep(
            step_id=_new_id(),
            name=f"Step 2: {update_method} {update_ep.path} — update resource",
            method=update_method,
            endpoint_path=update_ep.path,
            expected_status=expected_update_status,
            request_headers={"Content-Type": getattr(update_ep, 'content_type', 'application/json')},
            path_params={**_sample_path_params(update_ep), path_param: "{{created_id}}"},
            request_body=update_body,
            depends_on=["created_id"],
            extract={"updated_data": "$.data"},
            assertions=[
                f"Status code is {expected_update_status}",
                "Updated fields reflect new values",
            ],
        ),
        WorkflowStep(
            step_id=_new_id(),
            name=f"Step 3: GET {get_ep.path} — verify update was persisted",
            method="GET",
            endpoint_path=get_ep.path,
            expected_status=expected_get_status,
            path_params={**_sample_path_params(get_ep), path_param: "{{created_id}}"},
            depends_on=["created_id"],
            assertions=[
                f"Status code is {expected_get_status}",
                "Response reflects updated field values",
                "Non-updated fields remain unchanged",
            ],
        ),
    ]

    if needs_auth:
        steps = [_inject_auth_into_step(s) for s in steps]

    return WorkflowTest(
        id=_new_id(),
        name=f"Workflow: Create → {update_method} → Read at {resource_base}",
        description=(
            f"Multi-step mutation workflow: "
            f"1) POST {post_ep.path} to create, "
            f"2) {update_method} {update_ep.path} to update, "
            f"3) GET {get_ep.path} to confirm update persisted."
        ),
        steps=steps,
        endpoint_path=post_ep.path,
        method="POST",
        expected_status=expected_post_status,
        request_body=steps[0].request_body,
        assertions=["Update is reflected in subsequent GET"],
    )


def _build_create_delete_read_workflow(
    post_ep: Endpoint,
    delete_ep: Endpoint,
    get_ep: Endpoint,
    resource_base: str,
) -> WorkflowTest:
    """Workflow: Create → Delete → Read (expect 404 → confirms hard delete)."""
    create_body = _sample_body(post_ep.body_schema) or {}
    path_param = next(iter(delete_ep.path_params), "id") if delete_ep.path_params else "id"
    needs_auth = (
        _endpoint_needs_auth(post_ep)
        or _endpoint_needs_auth(delete_ep)
        or _endpoint_needs_auth(get_ep)
    )

    expected_post_status = get_expected_status(post_ep, 201)
    expected_delete_status = get_expected_status(delete_ep, 204)
    expected_get_err_status = get_expected_status(get_ep, 404)

    if not all([expected_post_status, expected_delete_status, expected_get_err_status]):
        return None

    steps = [
        WorkflowStep(
            step_id=_new_id(),
            name=f"Step 1: POST {post_ep.path} — create resource",
            method="POST",
            endpoint_path=post_ep.path,
            expected_status=expected_post_status,
            path_params=_sample_path_params(post_ep),
            request_headers={"Content-Type": getattr(post_ep, 'content_type', 'application/json')},
            request_body=create_body,
            extract={"created_id": "$.data.id"},
            assertions=[f"Status code is {expected_post_status}", "Resource created"],
        ),
        WorkflowStep(
            step_id=_new_id(),
            name=f"Step 2: DELETE {delete_ep.path} — remove resource",
            method="DELETE",
            endpoint_path=delete_ep.path,
            expected_status=expected_delete_status,
            path_params={**_sample_path_params(delete_ep), path_param: "{{created_id}}"},
            depends_on=["created_id"],
            assertions=[f"Status code is {expected_delete_status}", "Deletion acknowledged"],
        ),
        WorkflowStep(
            step_id=_new_id(),
            name=f"Step 3: GET {get_ep.path} — confirm resource is gone ({expected_get_err_status})",
            method="GET",
            endpoint_path=get_ep.path,
            expected_status=expected_get_err_status,
            path_params={**_sample_path_params(get_ep), path_param: "{{created_id}}"},
            depends_on=["created_id"],
            assertions=[
                f"Status code is {expected_get_err_status}",
                "Deleted resource is no longer accessible",
            ],
        ),
    ]

    if needs_auth:
        steps = [_inject_auth_into_step(s) for s in steps]

    return WorkflowTest(
        id=_new_id(),
        name=f"Workflow: Create → Delete → Read (404) at {resource_base}",
        description=(
            f"Hard-delete verification: "
            f"1) POST {post_ep.path} to create, "
            f"2) DELETE {delete_ep.path} to remove, "
            f"3) GET {get_ep.path} — must return 404 confirming deletion."
        ),
        steps=steps,
        endpoint_path=post_ep.path,
        method="POST",
        expected_status=201,
        request_body=steps[0].request_body,
        assertions=["Deleted resource returns 404 on GET"],
    )


def _build_order_flow_workflow(endpoints: list[Endpoint]) -> WorkflowTest | None:
    """
    Business Workflow: Add to Cart → Checkout → Payment → Verify Order Status
    State machine: CART → CHECKOUT → PAYMENT_PENDING → CONFIRMED
    Includes rollback scenario: Payment fails → order stays PAYMENT_PENDING.
    """
    # Detect cart/checkout/payment/order endpoints heuristically
    cart_ep = checkout_ep = payment_ep = order_ep = None
    for ep in endpoints:
        path_lower = ep.path.lower()
        if ep.method == "POST" and "cart" in path_lower:
            cart_ep = ep
        elif ep.method == "POST" and ("checkout" in path_lower or "order" in path_lower
                                       and cart_ep and order_ep is None):
            checkout_ep = ep
        elif ep.method == "POST" and "pay" in path_lower:
            payment_ep = ep
        elif ep.method == "GET" and "order" in path_lower:
            order_ep = ep

    # Only build this workflow if at least 2 relevant endpoints are found
    if sum(ep is not None for ep in [cart_ep, checkout_ep, payment_ep, order_ep]) < 2:
        return None

    steps: list[WorkflowStep] = []
    state = []

    if cart_ep:
        cart_body = _sample_body(cart_ep.body_schema) or {"productId": "test_product_001", "quantity": 1}
        expected_cart_status = get_expected_status(cart_ep, 201)
        if expected_cart_status:
            step = WorkflowStep(
                step_id=_new_id(),
                name=f"Step 1: Add to cart at {cart_ep.path}",
                method="POST",
                endpoint_path=cart_ep.path,
                expected_status=expected_cart_status,
                path_params=_sample_path_params(cart_ep),
                request_headers={"Content-Type": "application/json"},
                request_body=cart_body,
                extract={"cart_id": "$.data.cartId", "cart_status": "$.data.status"},
                expected_state="CART",
                assertions=[f"Status code is {expected_cart_status}", "Cart status is CART"],
            )
            if _endpoint_needs_auth(cart_ep):
                _inject_auth_into_step(step)
            steps.append(step)
            state.append("CART")

    if checkout_ep:
        checkout_body = _sample_body(checkout_ep.body_schema) or {}
        if steps:
            checkout_body.setdefault("cartId", "{{cart_id}}")
        expected_checkout_status = get_expected_status(checkout_ep, 201)
        if expected_checkout_status:
            step = WorkflowStep(
                step_id=_new_id(),
                name=f"Step {len(steps)+1}: Checkout at {checkout_ep.path}",
                method="POST",
                endpoint_path=checkout_ep.path,
                expected_status=expected_checkout_status,
                path_params=_sample_path_params(checkout_ep),
                request_headers={"Content-Type": "application/json"},
                request_body=checkout_body,
                depends_on=["cart_id"] if cart_ep else [],
                extract={"order_id": "$.data.orderId", "order_status": "$.data.status"},
                expected_state="CHECKOUT",
                assertions=[f"Status code is {expected_checkout_status}", "Order created from cart", "Order status is CHECKOUT or PENDING"],
            )
            if _endpoint_needs_auth(checkout_ep):
                _inject_auth_into_step(step)
            steps.append(step)
            state.append("CHECKOUT")

    if payment_ep:
        pay_body = _sample_body(payment_ep.body_schema) or {}
        pay_body.setdefault("orderId", "{{order_id}}")
        pay_body.setdefault("amount", 99.99)
        pay_body.setdefault("method", "card")
        expected_pay_status = get_expected_status(payment_ep, 200)
        if expected_pay_status:
            step = WorkflowStep(
                step_id=_new_id(),
                name=f"Step {len(steps)+1}: Make payment at {payment_ep.path}",
                method="POST",
                endpoint_path=payment_ep.path,
                expected_status=expected_pay_status,
                path_params=_sample_path_params(payment_ep),
                request_headers={"Content-Type": "application/json"},
                request_body=pay_body,
                depends_on=["order_id"] if checkout_ep else [],
                extract={"payment_status": "$.data.status", "payment_id": "$.data.paymentId"},
                expected_state="PAYMENT_PENDING",
                assertions=[
                    f"Status code is {expected_pay_status}",
                    "Payment acknowledged",
                    "payment_status is PROCESSING or CONFIRMED",
                ],
            )
            if _endpoint_needs_auth(payment_ep):
                _inject_auth_into_step(step)
            steps.append(step)
            state.append("PAYMENT_PENDING")

    if order_ep:
        order_path_param = next(iter(order_ep.path_params), "id") if order_ep.path_params else "id"
        expected_order_status = get_expected_status(order_ep, 200)
        step = WorkflowStep(
            step_id=_new_id(),
            name=f"Step {len(steps)+1}: Verify order status at {order_ep.path}",
            method="GET",
            endpoint_path=order_ep.path,
            expected_status=expected_order_status,
            path_params={**_sample_path_params(order_ep), order_path_param: "{{order_id}}"} if checkout_ep else _sample_path_params(order_ep),
            depends_on=["order_id"] if checkout_ep else [],
            extract={"final_order_status": "$.data.status"},
            expected_state="CONFIRMED",
            assertions=[
                f"Status code is {expected_order_status}",
                "Order status is CONFIRMED",
                "Rollback check: if payment failed, status is PAYMENT_PENDING (not CONFIRMED)",
            ],
        )
        if _endpoint_needs_auth(order_ep):
            _inject_auth_into_step(step)
        steps.append(step)
        state.append("CONFIRMED")

    if not steps:
        return None

    return WorkflowTest(
        id=_new_id(),
        name="Workflow: Order Placement Flow (Cart → Checkout → Payment → Verified)",
        description=(
            "End-to-end business workflow: "
            "1) Add product to cart, "
            "2) Checkout to create an order, "
            "3) Make payment (triggers PAYMENT_PENDING), "
            "4) Verify final order status (CONFIRMED on success, PAYMENT_PENDING on failure). "
            "Validates state machine transitions and rollback consistency."
        ),
        steps=steps,
        state_machine=state if state else ["CART", "CHECKOUT", "PAYMENT_PENDING", "CONFIRMED"],
        endpoint_path=steps[0].endpoint_path,
        method=steps[0].method,
        expected_status=steps[0].expected_status,
        request_body=steps[0].request_body,
        assertions=[
            "State progresses: CART → CHECKOUT → PAYMENT_PENDING → CONFIRMED",
            "Payment failure keeps order in PAYMENT_PENDING (not CONFIRMED)",
            "Each step's variables flow to the next step",
        ],
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def generate_workflow_tests(endpoints: list[Endpoint]) -> list[dict]:
    """
    Generate multi-step workflow tests from a list of API endpoints.

    Returns a list of serialised WorkflowTest dicts.  Each dict has a top-level
    'steps' key (list of WorkflowStep dicts) plus flat compatibility fields
    (endpoint_path, method, expected_status) so it can be used as-is with the
    existing TestCaseOut schema.
    """
    tests: list[WorkflowTest] = []
    resource_groups = _group_endpoints_by_resource(endpoints)

    # --- Auth workflow (register + login) ------------------------------------
    register_ep, login_ep = _detect_auth_endpoints(endpoints)
    if login_ep:
        wf = _build_auth_workflow(register_ep, login_ep, all_endpoints=endpoints)
        if wf:
            tests.append(wf)

    # --- CRUD-based workflows ------------------------------------------------
    for resource_base, methods in resource_groups.items():
        # Skip admin-only resources entirely
        if any(_is_admin_endpoint(ep) for ep in methods.values()):
            logger.info(
                "[Workflow] Skipping admin resource '%s' — "
                "admin role credentials not available",
                resource_base,
            )
            continue

        post_ep = methods.get("POST")
        get_ep = methods.get("GET")
        put_ep = methods.get("PUT")
        patch_ep = methods.get("PATCH")
        delete_ep = methods.get("DELETE")
        update_ep = put_ep or patch_ep
        update_method = "PUT" if put_ep else ("PATCH" if patch_ep else None)

        # Skip base-path-only resources (no path params on GET/DELETE)
        has_id_get = get_ep and get_ep.path_params
        has_id_delete = delete_ep and delete_ep.path_params
        has_id_update = update_ep and update_ep.path_params

        if post_ep and has_id_get:
            tests.append(_build_create_read_workflow(post_ep, get_ep, resource_base))

        if post_ep and has_id_update and has_id_get:
            tests.append(_build_create_update_read_workflow(
                post_ep, update_ep, get_ep, resource_base, update_method
            ))

        if post_ep and has_id_delete and has_id_get:
            tests.append(_build_create_delete_read_workflow(
                post_ep, delete_ep, get_ep, resource_base
            ))

    # --- Business / order flow workflow -------------------------------------
    order_wf = _build_order_flow_workflow(endpoints)
    if order_wf:
        tests.append(order_wf)

    # --- Ensure auth pre-req steps exist -------------------------------------
    # If a workflow injects Authorization / depends_on auth_token but doesn't
    # extract auth_token in any prior step, prepend register/login steps.
    if login_ep:
        for wf in tests:
            if "Register → Login" in (wf.name or ""):
                continue
            if not _workflow_needs_auth_token(wf.steps):
                continue
            if _workflow_extracts_auth_token(wf.steps):
                continue
            prereq_steps = _build_auth_prereq_steps(register_ep, login_ep)
            if not prereq_steps:
                continue
            wf.steps = prereq_steps + wf.steps
            _renumber_step_names(wf.steps)
            wf.endpoint_path = wf.steps[0].endpoint_path
            wf.method = wf.steps[0].method
            wf.expected_status = wf.steps[0].expected_status
            wf.request_body = wf.steps[0].request_body

    return [wf.to_dict() for wf in tests]
