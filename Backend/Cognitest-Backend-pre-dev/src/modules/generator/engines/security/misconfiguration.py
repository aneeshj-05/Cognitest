"""
Security Misconfiguration test generators. Covers OWASP API Security 4.8.

Removed: verbose error tests (overlap with injection tests).
Fixed: CORS tests now use a public endpoint to avoid auth timeouts.
"""

import uuid
from typing import Any
from ...spec_parser import Endpoint

_DEBUG_PATHS = [
    "/debug", "/actuator/env", "/actuator/health", "/.env",
    "/swagger-ui.html", "/api-docs", "/metrics", "/console",
]

_DEFAULT_CREDENTIALS = [
    ("admin", "admin"), ("admin", "password"), ("admin", "123456"),
    ("root", "root"), ("test", "test"), ("user", "user"),
    ("administrator", "administrator"),
]

_EVIL_ORIGINS = ["https://evil.example.com", "null", "https://attacker.com"]


def generate_misconfiguration_tests(
    spec: dict[str, Any],
    endpoints: list[Endpoint],
) -> list[dict]:
    tests: list[dict] = []
    tests.extend(_generate_cors_tests(endpoints))
    tests.extend(_generate_debug_endpoint_tests())
    tests.extend(_generate_default_credential_tests(endpoints))
    return tests


def _generate_cors_tests(endpoints: list[Endpoint]) -> list[dict]:
    """
    Probe CORS policy using a PUBLIC endpoint to avoid auth timeouts.
    CORS misconfiguration is in response headers, not status codes.
    """
    tests = []
    # Prefer GET + no auth + no path params — avoids auth timeouts and path param issues
    ideal = [
        e for e in endpoints
        if e.method == "GET" and not e.requires_auth and not e.path_params
    ]
    fallback = [e for e in endpoints if not e.requires_auth]
    sample = (ideal[:1] if ideal else (fallback[:1] if fallback else endpoints[:1]))

    for ep in sample:
        for origin in _EVIL_ORIGINS:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"CORS Misconfiguration: Origin '{origin}' on {ep.path}",
                "test_type": "Security",
                "owasp_category": "Misconfiguration",
                "endpoint_path": ep.path,
                "method": ep.method,
                "expected_status": 200,
                "custom_headers": {"Origin": origin},
                "description": (
                    f"Sends {ep.method} {ep.path} with 'Origin: {origin}'. "
                    f"Check response headers: if 'Access-Control-Allow-Origin: {origin}' "
                    f"appears with 'Access-Control-Allow-Credentials: true', "
                    f"this is a CRITICAL CORS misconfiguration."
                ),
            })

        # Preflight OPTIONS probe
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"CORS Preflight: OPTIONS with evil origin on {ep.path}",
            "test_type": "Security",
            "owasp_category": "Misconfiguration",
            "endpoint_path": ep.path,
            "method": "OPTIONS",
            "expected_status": 200,
            "custom_headers": {"Origin": "https://evil.example.com"},
            "description": (
                f"Sends OPTIONS {ep.path} with attacker Origin. "
                f"Check 'Access-Control-Allow-Origin' in response headers."
            ),
        })

    return tests


def _generate_debug_endpoint_tests() -> list[dict]:
    tests = []
    for path in _DEBUG_PATHS:
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Debug Endpoint Probe: GET {path}",
            "test_type": "Security",
            "owasp_category": "Misconfiguration",
            "endpoint_path": path,
            "method": "GET",
            "expected_status": 404,
            "description": (
                f"Probes {path} — a well-known debug/management endpoint. "
                f"Should return 404 or 401. A 200 with config data is CRITICAL."
            ),
        })
    return tests


def _generate_default_credential_tests(endpoints: list[Endpoint]) -> list[dict]:
    tests = []
    login_endpoints = [
        ep for ep in endpoints
        if ep.method == "POST"
        and any(k in ep.path.lower() for k in ("login", "signin", "auth", "token", "session"))
    ]

    for ep in login_endpoints[:1]:
        for username, password in _DEFAULT_CREDENTIALS:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"Default Credentials: {username}/{password} on {ep.path}",
                "test_type": "Security",
                "owasp_category": "Misconfiguration",
                "endpoint_path": ep.path,
                "method": ep.method,
                "expected_status": 400,
                "request_body": {"email": username, "password": password},
                "description": (
                    f"Attempts login at {ep.path} with default credential pair "
                    f"'{username}'/'{password}'. Expects 400 or 401. "
                    f"A 200 means default credentials are active — CRITICAL."
                ),
            })

    admin_probes = ["/admin", "/admin/login", "/administrator", "/management"]
    for path in admin_probes:
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Default Credentials: Admin path probe {path}",
            "test_type": "Security",
            "owasp_category": "Misconfiguration",
            "endpoint_path": path,
            "method": "GET",
            "expected_status": 404,
            "description": (
                f"Probes {path} for exposed admin panel. "
                f"Should return 404 or 401. A 200 is CRITICAL."
            ),
        })

    return tests
