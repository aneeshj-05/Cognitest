import json
import asyncio
import logging
import random
import string
import httpx
import re

logger = logging.getLogger(__name__)

async def _stateful_setup(
    client: httpx.AsyncClient,
    base_url: str,
    spec: dict | None = None,
    admin_token: str | None = None,
):
    """
    Streaming generator: creates two test users (User A = owner, User B = attacker),
    logs them in, and creates a resource with User A so BOLA tests have a real ID.

    Yields JSON-encoded event strings (same format as _stream_security_suite).
    Call with ``async for event in _stateful_setup(...): yield event``.

    After exhausting the generator, the caller reads the populated ``context`` dict
    which contains: token_a, token_b, user_id_a, user_id_b, resource_id.
    """
    import random, string

    def rand_suffix() -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

    burl = base_url.rstrip("/")

    # Shared context dict that callers read after the generator finishes
    ctx: dict[str, str | None] = {
        "token_a": None,
        "token_b": None,
        "user_id_a": None,
        "user_id_b": None,
        "resource_id": None,
        "email_a": None,
        "email_b": None,
    }

    # Warm-up: Ping the target once to wake it up (Render cold-start)
    # Done silently without yielding to the frontend per user request
    try:
        await client.get(burl, timeout=10.0)
    except Exception:
        pass
    await asyncio.sleep(1.0)

    # Extract real paths AND payload schemas from the spec
    # Parse the uploaded OpenAPI spec to find actual register/login/resource
    # endpoints and their required fields, instead of blindly guessing.
    spec_signup: list[str] = []
    spec_login: list[str] = []
    spec_resource: list[str] = []
    # Map path -> request body details from the spec.
    spec_required_fields: dict[str, list[str]] = {}
    spec_body_schemas: dict[str, dict] = {}

    if spec and isinstance(spec, dict):
        _signup_keywords = {"register", "signup", "sign-up", "sign_up", "create-account", "create_account"}
        _login_keywords = {"login", "signin", "sign-in", "sign_in", "token", "authenticate", "auth/token"}
        _resource_keywords = {"item", "product", "post", "order", "cart", "article", "listing", "note", "task", "todo"}
        _skip_keywords = {"logout", "refresh", "verify", "confirm", "password", "reset", "otp", "admin"}

        def _extract_body_schema(path_item: dict, method: str = "post") -> dict:
            """Extract and resolve the request body schema."""
            op = path_item.get(method, {})
            rb = op.get("requestBody", {})
            content = rb.get("content", {})
            schema = (
                content.get("application/json", {}).get("schema")
                or next(iter(content.values()), {}).get("schema")
                or {}
            )
            if "$ref" in schema:
                ref_parts = schema["$ref"].lstrip("#/").split("/")
                resolved = spec
                for part in ref_parts:
                    resolved = resolved.get(part, {}) if isinstance(resolved, dict) else {}
                schema = resolved
            return schema if isinstance(schema, dict) else {}

        def _extract_required_fields(path_item: dict, method: str = "post") -> list[str]:
            """Extract required field names from the request body schema."""
            schema = _extract_body_schema(path_item, method)
            props = schema.get("properties", {})
            required = schema.get("required", list(props.keys()))
            return required

        for raw_path, path_item in (spec.get("paths") or {}).items():
            clean = raw_path.split("#")[0].lower()
            has_post = "post" in (path_item or {})
            if not has_post:
                continue
            if any(k in clean for k in _skip_keywords):
                continue

            actual_path = raw_path.split("#")[0]
            schema = _extract_body_schema(path_item)
            fields = _extract_required_fields(path_item)

            if any(k in clean for k in _signup_keywords) and "{" not in clean:
                spec_signup.append(actual_path)
                spec_required_fields[actual_path] = fields
                spec_body_schemas[actual_path] = schema
            elif any(k in clean for k in _login_keywords) and "{" not in clean:
                spec_login.append(actual_path)
                spec_required_fields[actual_path] = fields
                spec_body_schemas[actual_path] = schema
            elif any(k in clean for k in _resource_keywords) and "{" not in clean:
                spec_resource.append(actual_path)
                spec_required_fields[actual_path] = fields
                spec_body_schemas[actual_path] = schema

    signup_candidates = spec_signup + [
        "/api/auth/signup", "/api/auth/register", "/api/register",
        "/api/users", "/auth/signup", "/auth/register", "/users", "/register",
        "/signup",
    ]
    login_candidates = spec_login + [
        "/api/auth/login", "/api/login", "/auth/login", "/login",
    ]
    # If the uploaded spec names resource endpoints, trust it. Fallback probing is
    # only for specs that do not expose any usable POST resource paths.
    resource_candidates = spec_resource or [
        "/api/items", "/api/products", "/api/posts", "/api/cart",
        "/api/orders", "/items", "/products", "/posts",
    ]

    # Deduplicate while preserving order (spec paths first)
    def _dedup(lst: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in lst:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    signup_candidates = _dedup(signup_candidates)
    login_candidates = _dedup(login_candidates)
    resource_candidates = _dedup(resource_candidates)

    # Debug: log discovered paths
    logger.info(f"[Setup] Discovered {len(spec_signup)} signup paths from spec: {spec_signup}")
    logger.info(f"[Setup] Discovered {len(spec_login)} login paths from spec: {spec_login}")
    logger.info(f"[Setup] Total signup candidates: {signup_candidates[:5]}...")
    logger.info(f"[Setup] Total login candidates: {login_candidates[:5]}...")

    # Generate test credentials
    password = "CogniTest123!"
    email_a = f"cogni{rand_suffix()}@test.com"
    email_b = f"cogni{rand_suffix()}@test.com"
    ctx["email_a"] = email_a
    ctx["email_b"] = email_b

    def _build_signup_payloads(email: str, label: str, path: str) -> list[dict]:
        """Build signup payloads. Always includes confirmPassword variant since
        many APIs require it. Spec-derived fields are tried first."""
        required = spec_required_fields.get(path, [])

        spec_payload: dict | None = None
        if required:
            spec_payload = {}
            for field in required:
                fl = field.lower()
                if "confirm" in fl and "pass" in fl:
                    spec_payload[field] = password
                elif "email" in fl:
                    spec_payload[field] = email
                elif "pass" in fl or "pwd" in fl or "secret" in fl:
                    spec_payload[field] = password
                elif "first" in fl:
                    spec_payload[field] = "Cogni"
                elif "last" in fl:
                    spec_payload[field] = label
                elif "name" in fl and "user" in fl:
                    spec_payload[field] = f"cogni{label.lower()}"
                elif "name" in fl:
                    spec_payload[field] = f"Cogni {label}"
                elif "user" in fl:
                    spec_payload[field] = f"cogni{label.lower()}"
                elif "phone" in fl or "mobile" in fl:
                    spec_payload[field] = "+10000000001"
                elif "role" in fl:
                    spec_payload[field] = "user"
                else:
                    spec_payload[field] = f"cogni_{label.lower()}"

        base_payloads = [
            # confirmPassword variants (most common cause of 422)
            {"email": email, "password": password, "confirmPassword": password, "name": f"Cogni {label}"},
            {"email": email, "password": password, "confirmPassword": password},
            {"email": email, "password": password, "confirm_password": password, "name": f"Cogni {label}"},
            {"email": email, "password": password, "passwordConfirm": password, "name": f"Cogni {label}"},
            {"email": email, "password": password, "password2": password, "name": f"Cogni {label}"},
            # Without confirmPassword
            {"email": email, "password": password, "name": f"Cogni {label}"},
            {"email": email, "password": password, "username": f"cogni{label.lower()}", "name": f"Cogni {label}"},
            {"email": email, "password": password},
            {"email": email, "password": password, "firstName": "Cogni", "lastName": label},
            {"email": email, "password": password, "first_name": "Cogni", "last_name": label},
            {"email": email, "passcode": password, "name": f"Cogni {label}"},
            {"username": email, "password": password, "email": email},
        ]
        return ([spec_payload] if spec_payload else []) + base_payloads

    def _build_login_payloads(email: str, path: str) -> list[dict]:
        """Build login payloads using spec field names first."""
        required = spec_required_fields.get(path, [])

        spec_payload: dict | None = None
        if required:
            spec_payload = {}
            for field in required:
                fl = field.lower()
                if "email" in fl:
                    spec_payload[field] = email
                elif "pass" in fl or "pwd" in fl or "secret" in fl:
                    spec_payload[field] = password
                elif "user" in fl:
                    spec_payload[field] = email
                else:
                    spec_payload[field] = email

        base_payloads = [
            {"email": email, "password": password},
            {"email": email, "passcode": password},
            {"username": email, "password": password},
            {"email": email, "password": password, "rememberMe": False},
        ]
        return ([spec_payload] if spec_payload else []) + base_payloads

    def _field_value(field: str, field_schema: dict | None = None):
        """Best-effort placeholder value for a spec-declared request field."""
        fl = field.lower()
        field_schema = field_schema or {}
        field_type = field_schema.get("type", "string")

        if field_type in ("integer", "number"):
            return 1
        if field_type == "boolean":
            return True
        if field_type == "array":
            if "item" in fl or "product" in fl or "cart" in fl:
                return [{"productId": "00000000-0000-0000-0000-000000000001", "quantity": 1}]
            return []
        if "quantity" in fl or "qty" in fl or "count" in fl or "amount" in fl:
            return 1
        if fl in {"id", "_id"} or fl.endswith("id") or fl.endswith("_id"):
            return "00000000-0000-0000-0000-000000000001"
        if "email" in fl:
            return f"resource-{rand_suffix()}@test.com"
        if "price" in fl:
            return 1
        if "url" in fl or "image" in fl:
            return "https://example.com/cognitest.png"
        if "title" in fl:
            return "Cognitest Resource"
        if "description" in fl or "body" in fl or "content" in fl or "text" in fl:
            return "Cognitest generated resource for authorization testing"
        if "name" in fl:
            return f"cognitest-resource-{rand_suffix()}"
        return f"cognitest-{field}-{rand_suffix()}"

    def _build_resource_payloads(path: str) -> list[dict]:
        """Build resource payloads from the spec before trying generic shapes."""
        schema = spec_body_schemas.get(path, {})
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = spec_required_fields.get(path, [])

        spec_payload = None
        if props:
            fields = required or list(props.keys())[:5]
            spec_payload = {
                field: _field_value(field, props.get(field))
                for field in fields
            }

        generic_payloads = [
            {"name": f"cognitest-resource-{rand_suffix()}", "title": "Test Resource A"},
            {"title": "Test Resource A", "description": "Cognitest generated resource"},
            {"productId": "00000000-0000-0000-0000-000000000001", "quantity": 1},
        ]
        return ([spec_payload] if spec_payload else []) + generic_payloads

    # -- Helper: attempt login on multiple paths ------------------------------

    async def _try_login(email: str):
        """Try login endpoints using spec-derived payload shapes first.

        - 404 on a path -> skip to next path immediately
        - 422 on a path -> wrong payload shape, try next payload variant
        """
        for path in login_candidates:
            payloads = _build_login_payloads(email, path)
            for payload in payloads:
                try:
                    r = await client.post(
                        f"{burl}{path}", json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=10.0
                    )
                    if r.status_code == 404:
                        break  # Wrong path, skip remaining payloads
                    if r.status_code in (200, 201):
                        body = {}
                        try:
                            body = r.json()
                        except Exception:
                            pass
                        token = (
                            body.get("token") or body.get("access_token")
                            or body.get("accessToken")
                            or (body.get("data") or {}).get("token")
                            or (body.get("data") or {}).get("access_token")
                            or (body.get("user") or {}).get("token")
                        )
                        uid = str(
                            body.get("_id") or body.get("id") or body.get("userId") or body.get("user_id")
                            or (body.get("data") or {}).get("_id") or (body.get("data") or {}).get("id")
                            or (body.get("user") or {}).get("_id") or (body.get("user") or {}).get("id") or ""
                        ) or None
                        if token:
                            return token, uid
                    # 422 = wrong payload shape, try next payload variant
                except Exception:
                    continue
        return None, None

    # Helper: attempt signup on multiple paths

    async def _try_signup(email: str, label: str):
        """Try signup endpoints using spec-derived payload shapes first.

        - 404 on a path -> skip to next path immediately
        - 422 on a path -> wrong payload shape, try next payload variant
        - 200/201 with no token -> OTP/email-verify flow, attempt login
        - 409 -> already exists, attempt login
        """
        for path in signup_candidates:
            payloads = _build_signup_payloads(email, label, path)
            for payload in payloads:
                try:
                    r = await client.post(
                        f"{burl}{path}", json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=10.0
                    )
                    if r.status_code == 404:
                        break  # Wrong path, skip remaining payloads
                    if r.status_code in (200, 201):
                        body = {}
                        try:
                            body = r.json()
                        except Exception:
                            pass
                        token = (
                            body.get("token") or body.get("access_token")
                            or body.get("accessToken")
                            or (body.get("data") or {}).get("token")
                            or (body.get("data") or {}).get("access_token")
                            or (body.get("user") or {}).get("token")
                        )
                        uid = str(
                            body.get("_id") or body.get("id") or body.get("userId") or body.get("user_id")
                            or (body.get("data") or {}).get("_id") or (body.get("data") or {}).get("id")
                            or (body.get("user") or {}).get("user_id")
                            or (body.get("user") or {}).get("_id") or (body.get("user") or {}).get("id") or ""
                        ) or None
                        if token:
                            return token, uid, path
                        # No token (OTP/email-verify flow) - try login (silently)
                        tok, u = await _try_login(email)
                        if tok:
                            return tok, u or uid, path
                        return None, uid, path

                    if r.status_code == 409:
                        # 409 Conflict = User definitely exists, attempt login
                        tok, u = await _try_login(email)
                        if tok:
                            return tok, u, path

                    if r.status_code == 422:
                        # 422 Unprocessable - Could be "Exists" or "Cold Start Database Lag"
                        # If first payload, try one more time with a long backoff
                        if payload == payloads[0]:
                            await asyncio.sleep(3.0) # Longer backoff for cold-start
                            r2 = await client.post(
                                f"{burl}{path}", json=payload,
                                headers={"Content-Type": "application/json"},
                                timeout=10.0
                            )
                            if r2.status_code in (200, 201):
                                # Token extraction same as above (simplified for brevity)
                                pass
                            elif r2.status_code == 409 or r2.status_code == 422:
                                # Still failing - now attempt login as fallback
                                tok, u = await _try_login(email)
                                if tok:
                                    return tok, u, path
                except Exception:
                    continue
        return None, None, None

    # User A: signup
    yield json.dumps({
        "event": "setup_step", "step": "User A Signup", "status": "pending",
        "log": f"  → Creating User A ({email_a})...",
    }) + "\n"
    await asyncio.sleep(0.05)

    token_a, uid_a, _signup_path = await _try_signup(email_a, "UserA")
    ctx["user_id_a"] = uid_a

    if not token_a:
        # Try login in case user already exists or signup skips token
        yield json.dumps({
            "event": "setup_step", "step": "User A Login", "status": "pending",
            "log": "  → Creating User A session via login...",
        }) + "\n"
        token_a, uid_a = await _try_login(email_a)
        ctx["user_id_a"] = uid_a

    ctx["token_a"] = token_a

    if token_a:
        yield json.dumps({
            "event": "setup_step", "step": "User A Ready", "status": "ok",
            "log": f"  ✓ User A created — token acquired (id={uid_a or 'unknown'})",
        }) + "\n"
    else:
        yield json.dumps({
            "event": "setup_step", "step": "User A Ready", "status": "fail",
            "log": "  ✗ Could not register or log in User A",
        }) + "\n"

    await asyncio.sleep(0.05)

    # User A: create a resource (or use admin token if provided)
    creation_token = admin_token or token_a
    if creation_token:
        auth_headers_a = {
            "Authorization": f"Bearer {creation_token}",
            "Content-Type": "application/json",
        }
        for rpath in resource_candidates:
            try:
                for body in _build_resource_payloads(rpath):
                    r = await client.post(
                        f"{burl}{rpath}",
                        json=body,
                        headers=auth_headers_a,
                        timeout=10.0,
                    )
                    if r.status_code == 404:
                        break
                    if r.status_code in (200, 201):
                        rbody = {}
                        try:
                            rbody = r.json()
                        except Exception:
                            pass
                        rid = str(
                            rbody.get("id") or rbody.get("_id")
                            or (rbody.get("data") or {}).get("id") or ""
                        ) or None
                        if rid:
                            ctx["resource_id"] = rid
                            yield json.dumps({
                                "event": "setup_step", "step": "Create Resource", "status": "ok",
                                "log": f"  ✓ Resource acquired at {rpath} (id={rid}) — BOLA tests will target this ID",
                            }) + "\n"
                            break
                    if r.status_code not in (400, 401, 403, 422):
                        break
                if ctx["resource_id"]:
                    break
            except Exception:
                continue
        if not ctx["resource_id"]:
            yield json.dumps({
                "event": "setup_step", "step": "Create Resource", "status": "warn",
                "log": "  ℹ No resource created for User A — BOLA tests will use fallback IDs",
            }) + "\n"

    await asyncio.sleep(0.05)

    # User B: signup
    yield json.dumps({
        "event": "setup_step", "step": "User B Signup", "status": "pending",
        "log": f"  → Creating User B ({email_b})...",
    }) + "\n"
    await asyncio.sleep(0.05)

    token_b, uid_b, _ = await _try_signup(email_b, "UserB")
    ctx["user_id_b"] = uid_b

    if not token_b:
        yield json.dumps({
            "event": "setup_step", "step": "User B Login", "status": "pending",
            "log": "  → Creating User B session via login...",
        }) + "\n"
        token_b, uid_b = await _try_login(email_b)
        ctx["user_id_b"] = uid_b

    ctx["token_b"] = token_b

    if token_b:
        yield json.dumps({
            "event": "setup_step", "step": "User B Ready", "status": "ok",
            "log": f"  ✓ User B created — token acquired (id={uid_b or 'unknown'}) — attacker role ready",
        }) + "\n"
    else:
        yield json.dumps({
            "event": "setup_step", "step": "User B Ready", "status": "fail",
            "log": "  ✗ Could not register or log in User B",
        }) + "\n"

    await asyncio.sleep(0.05)
    yield json.dumps({"event": "_setup_ctx", "ctx": ctx}) + "\n"


# Auth session helpers

async def _auth_session_setup(
    client: httpx.AsyncClient,
    base_url: str,
    register_url: str | None,
    login_url: str,
    email: str,
    password: str,
    spec: dict | None = None,
    admin_token: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Optionally registers a fresh test user, then logs in to acquire a JWT.

    When `spec` is provided, reads the requestBody schema for the auth
    endpoints and builds payloads that match exactly what the API expects.
    Falls back to common guesses when no schema is available.

    Returns (token, user_id).  Either may be None on failure.
    """
    burl = base_url.rstrip("/")
    token: str | None = None
    user_id: str | None = None

    def _extract_token(body: dict) -> str | None:
        """Deep-search for a JWT/token in common response shapes."""
        if not isinstance(body, dict):
            return None
        # Top-level
        for key in ("token", "access_token", "accessToken", "jwt", "auth_token", "authToken"):
            val = body.get(key)
            if val and isinstance(val, str) and len(val) > 10:
                return val
        # Nested under common wrappers
        for wrapper in ("data", "user", "result", "payload", "response", "auth"):
            nested = body.get(wrapper)
            if isinstance(nested, dict):
                for key in ("token", "access_token", "accessToken", "jwt", "auth_token"):
                    val = nested.get(key)
                    if val and isinstance(val, str) and len(val) > 10:
                        return val
        return None

    def _extract_user_id(body: dict) -> str | None:
        """Deep-search for a user ID."""
        if not isinstance(body, dict):
            return None
        for key in ("id", "userId", "user_id", "_id"):
            val = body.get(key)
            if val:
                return str(val)
        for wrapper in ("data", "user", "result", "payload"):
            nested = body.get(wrapper)
            if isinstance(nested, dict):
                for key in ("id", "userId", "user_id", "_id"):
                    val = nested.get(key)
                    if val:
                        return str(val)
        return None

    def _resolve_ref(ref_str: str) -> dict:
        """Resolve a $ref path like '#/components/schemas/Foo' or '#/definitions/Foo'."""
        if not ref_str or not isinstance(ref_str, str) or not spec:
            return {}
        parts = ref_str.lstrip("#/").split("/")
        resolved = spec
        for part in parts:
            resolved = resolved.get(part, {}) if isinstance(resolved, dict) else {}
        return resolved if isinstance(resolved, dict) else {}

    def _resolve_schema(schema: dict) -> dict:
        """Resolve a schema, following $ref if present (up to 3 levels deep)."""
        if not isinstance(schema, dict):
            return {}
        for _ in range(3):  # max 3 levels of $ref chasing
            if "$ref" in schema:
                schema = _resolve_ref(schema["$ref"])
            else:
                break
        return schema

    def _spec_path_for(endpoint_path: str) -> str:
        """Return the matching OpenAPI path key for a concrete or templated URL."""
        if not spec or not isinstance(spec.get("paths"), dict):
            return endpoint_path

        normalized = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        if normalized in spec["paths"]:
            return normalized

        normalized_parts = [p for p in normalized.strip("/").split("/") if p]
        for candidate in spec["paths"].keys():
            candidate_parts = [p for p in str(candidate).strip("/").split("/") if p]
            if len(candidate_parts) != len(normalized_parts):
                continue
            matches = True
            for c_part, n_part in zip(candidate_parts, normalized_parts):
                if re.fullmatch(r"\{[^/{}]+\}", c_part):
                    continue
                if c_part != n_part:
                    matches = False
                    break
            if matches:
                return str(candidate)

        return normalized

    def _build_payloads_from_schema(
        endpoint_path: str, email: str, password: str, is_register: bool,
    ) -> list[dict]:
        """
        Read the requestBody schema for an endpoint from the OpenAPI spec
        and build payloads that match the required/expected fields.
        Handles both OpenAPI 3.0 and Swagger 2.0 spec formats.
        """
        schema_payloads: list[dict] = []

        if spec and isinstance(spec.get("paths"), dict):
            spec_path = _spec_path_for(endpoint_path)
            path_def = spec["paths"].get(spec_path, {})
            post_def = path_def.get("post", {})
            json_schema: dict = {}

            # ── OpenAPI 3.0: requestBody.content.application/json.schema ──
            req_body = post_def.get("requestBody", {})
            if isinstance(req_body, dict) and req_body:
                # Resolve $ref on requestBody itself
                req_body = _resolve_schema(req_body)
                content = req_body.get("content", {})
                for content_type in ("application/json", "*/*"):
                    if content_type in content:
                        json_schema = _resolve_schema(
                            content[content_type].get("schema", {})
                        )
                        break

            # ── Swagger 2.0: parameters[].in=body → schema ──
            if not json_schema.get("properties"):
                params = post_def.get("parameters", [])
                if isinstance(params, list):
                    for param in params:
                        if isinstance(param, dict) and param.get("in") == "body":
                            json_schema = _resolve_schema(param.get("schema", {}))
                            break

            # Resolve property-level $refs
            properties = json_schema.get("properties", {})
            resolved_props: dict = {}
            for pname, pdef in properties.items():
                resolved_props[pname] = _resolve_schema(pdef) if isinstance(pdef, dict) else pdef
            properties = resolved_props
            required_fields = set(json_schema.get("required", []))

            if properties:
                # Build a payload from the spec schema
                payload: dict = {}
                username = email.split("@")[0]

                for field_name, field_def in properties.items():
                    fl = field_name.lower()
                    field_def = _resolve_schema(field_def) if isinstance(field_def, dict) else {}
                    field_type = field_def.get("type", "string")
                    field_format = field_def.get("format", "")
                    enum_values = field_def.get("enum") if isinstance(field_def.get("enum"), list) else []

                    # Map known field semantics
                    if enum_values:
                        if fl in ("user_type", "role", "roles"):
                            preferred_roles = (
                                "DATA_COLLECTOR", "ANALYST", "SITE_IN_CHARGE",
                                "CUSTOMER_SITE_IN_CHARGE", "CUSTOMER_MANAGEMENT",
                            )
                            payload[field_name] = next(
                                (role for role in preferred_roles if role in enum_values),
                                enum_values[0],
                            )
                        else:
                            payload[field_name] = enum_values[0]
                    elif fl in ("email", "mail", "emailaddress", "email_address"):
                        payload[field_name] = email
                    elif fl in ("password", "passwd", "pass", "passcode", "secret"):
                        payload[field_name] = password
                    elif fl in ("username", "user_name", "login", "user"):
                        payload[field_name] = username
                    elif fl in ("name", "fullname", "full_name", "displayname", "display_name"):
                        payload[field_name] = "Cognitest Runner"
                    elif fl in ("firstname", "first_name", "fname"):
                        payload[field_name] = "Cognitest"
                    elif fl in ("lastname", "last_name", "lname"):
                        payload[field_name] = "Runner"
                    elif fl in ("phone", "phonenumber", "phone_number", "mobile"):
                        payload[field_name] = "+1234567890"
                    elif fl in ("age",):
                        payload[field_name] = 25
                    elif fl in ("role",):
                        payload[field_name] = "user"
                    elif fl in ("confirmpassword", "confirm_password", "password_confirmation",
                                "passwordconfirm", "password_confirm"):
                        payload[field_name] = password
                    elif fl in ("terms", "agree", "accept", "tos"):
                        payload[field_name] = True
                    elif field_type == "string":
                        if field_format == "email":
                            payload[field_name] = email
                        elif "password" in field_format:
                            payload[field_name] = password
                        else:
                            # Only fill required string fields
                            if field_name in required_fields:
                                payload[field_name] = f"test_{field_name}"
                    elif field_type == "integer" or field_type == "number":
                        if field_name in required_fields:
                            payload[field_name] = 1
                    elif field_type == "boolean":
                        if field_name in required_fields:
                            payload[field_name] = True

                if payload:
                    logger.info(
                        "[AutoAuth] Schema for %s: fields=%s, required=%s → payload_keys=%s",
                        endpoint_path, list(properties.keys()), list(required_fields), list(payload.keys()),
                    )
                    schema_payloads.append(payload)
                else:
                    logger.warning("[AutoAuth] Schema for %s: properties found=%s but no payload built", endpoint_path, list(properties.keys()))
            else:
                logger.info("[AutoAuth] No schema properties found for %s (spec format issue?)", endpoint_path)

        return schema_payloads

    # Build spec-driven payloads first, then fall back to hardcoded guesses
    def _get_register_payloads(reg_path: str) -> list[dict]:
        spec_payloads = _build_payloads_from_schema(reg_path, email, password, is_register=True)
        username = email.split("@")[0]
        guesses = [
            {"email": email, "password": password, "name": "Cognitest Runner", "username": username, "user_type": "DATA_COLLECTOR"},
            {"email": email, "password": password, "name": "Cognitest Runner",
             "username": username, "firstName": "Cognitest", "lastName": "Runner", "user_type": "DATA_COLLECTOR"},
            {"email": email, "password": password, "name": "Cognitest Runner", "user_type": "DATA_COLLECTOR"},
            {"email": email, "passcode": password, "name": "Cognitest Runner"},
        ]
        # Spec payloads go first (highest confidence)
        return spec_payloads + guesses

    def _get_login_payloads(login_path: str) -> list[dict]:
        spec_payloads = _build_payloads_from_schema(login_path, email, password, is_register=False)
        guesses = [
            {"email": email, "password": password},
            {"email": email, "passcode": password},
            {"username": email, "password": password},
            {"username": email.split("@")[0], "password": password},
        ]
        return spec_payloads + guesses

    # Step 1: Register (optional)
    if register_url:
        reg_path = register_url if register_url.startswith("/") else f"/{register_url}"
        register_headers = {"Content-Type": "application/json"}
        if admin_token:
            register_headers["Authorization"] = f"Bearer {admin_token.strip().removeprefix('Bearer ').strip()}"
        for payload in _get_register_payloads(register_url):
            try:
                r = await client.post(
                    f"{burl}{reg_path}", json=payload,
                    headers=register_headers,
                    timeout=10.0,
                )
                logger.info("[AutoAuth] Register %s%s -> %s (payload_keys=%s)", burl, reg_path, r.status_code, list(payload.keys()))
                if r.status_code in (200, 201, 409):  # 409 = already exists, still ok
                    try:
                        body = r.json() if r.text else {}
                    except Exception:
                        body = {}
                    token = _extract_token(body)
                    user_id = _extract_user_id(body)
                    if token or r.status_code == 409:
                        break  # 409 means user exists, proceed to login
            except Exception as exc:
                logger.warning("[AutoAuth] Register attempt failed: %s", exc)

    # Step 2: Login
    if not token:
        login_path = login_url if login_url.startswith("/") else f"/{login_url}"
        for payload in _get_login_payloads(login_url):
            try:
                r = await client.post(
                    f"{burl}{login_path}", json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10.0,
                )
                logger.info(
                    "[AutoAuth] Login %s%s -> %s (payload_keys=%s, body=%s)",
                    burl, login_path, r.status_code,
                    list(payload.keys()),
                    r.text[:200] if r.text else "(empty)",
                )
                if r.status_code in (200, 201):
                    try:
                        body = r.json() if r.text else {}
                    except Exception:
                        body = {}
                    token = _extract_token(body)
                    if not user_id:
                        user_id = _extract_user_id(body)
                    if token:
                        break
            except Exception as exc:
                logger.warning("[AutoAuth] Login attempt failed: %s", exc)

    return token, user_id


async def _auth_session_cleanup(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    user_id: str | None,
) -> bool:
    """
    Attempt to delete the test user created during session setup.
    Returns True if cleanup succeeded.
    """
    if not user_id:
        return False

    burl = base_url.rstrip("/")
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    candidates = [
        f"/api/users/{user_id}",
        f"/api/user/{user_id}",
        f"/users/{user_id}",
        f"/user/{user_id}",
    ]
    for path in candidates:
        try:
            r = await client.delete(f"{burl}{path}", headers=auth_headers)
            if r.status_code in (200, 204):
                return True
        except Exception:
            pass
    return False
