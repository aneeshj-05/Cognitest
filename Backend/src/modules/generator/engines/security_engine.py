"""
Security Testing Engine – OWASP API Security Top 10 based test generation.

Coverage:
  4.1 Injection (SQL, NoSQL, XPath, Command, XSS, Header)
  4.2 Authentication & Authorization (stateless: missing/invalid/expired/tampered/replay)
  4.3 BOLA / IDOR               ← requires_stateful: True
  4.4 Excessive Data Exposure
  4.5 Rate Limiting & Brute Force
  4.6 HTTP Verb Tampering
  4.7 TLS / Transport Security
  4.8 Security Misconfiguration

Test ordering:
  Stateless tests run first (SQL → Auth → Rate Limit → Exposure → TLS →
  Misconfiguration → Verb Tampering).  Stateful tests (BOLA, wrong-role)
  come last so the runner can do one setup phase and then execute all of
  them together.
"""
import uuid
from typing import Any
from ..spec_parser import extract_endpoints
from .security import (
    generate_injection_tests,
    generate_bola_tests,
    generate_exposure_tests,
    generate_auth_tests,
    generate_rate_limit_tests,
    generate_tls_tests,
    generate_verb_tampering_tests,
    generate_misconfiguration_tests,
    generate_function_level_auth_tests,
)
from ..ai.generators.security_generator import generate_security_tests_ai

import logging
logger = logging.getLogger(__name__)

# OWASP category → sort key (stateful categories pushed to the end)
_OWASP_ORDER = {
    "Injection": 1,
    "Auth": 2,
    "RateLimit": 3,
    "Exposure": 4,
    "TLS": 5,
    "Misconfiguration": 6,
    "VerbTamper": 7,
    # Stateful below this line
    "BOLA": 10,
    "FunctionAuth": 11,
}


def _make_wrong_role_tests(endpoints) -> list[dict]:
    """
    Generate wrong-role / privilege escalation tests.

    These are stateful — the runner needs a real 'viewer' token to send,
    which is only available after the stateful setup phase creates User B
    with a restricted role.
    """
    tests = []
    for ep in endpoints:
        if ep.method not in ("POST", "PUT", "PATCH", "DELETE"):
            continue
        if not ep.requires_auth:
            continue
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Privilege Escalation: viewer role on {ep.method} {ep.path}",
            "test_type": "Security",
            "endpoint_path": ep.path,
            "method": ep.method,
            "expected_status": 403,
            "requires_stateful": True,
            "owasp_category": "WrongRole",
            "description": (
                f"Sends User B's 'viewer' role token to {ep.method} {ep.path}. "
                f"Should return 403 Forbidden.  A 200 response is a privilege escalation vulnerability."
            ),
        })
    return tests


async def generate_security_tests(spec: dict[str, Any], use_ai: bool = False) -> list[dict]:
    """
    Generate comprehensive security tests based on OWASP API Security Top 10.

    Tests are returned in execution order:
      1. Stateless tests (immediate, no setup required)
      2. Stateful tests (BOLA + wrong-role, runner does setup first)

    Args:
        spec: OpenAPI/Swagger specification dictionary

    Returns:
        List of test case dictionaries with ``requires_stateful`` flag where needed.
    """
    if use_ai:
        ai_cases, tokens = await generate_security_tests_ai(spec)
        logger.info("AI-only security engine generated %d cases (%d tokens)", len(ai_cases), tokens)
        return ai_cases

    stateless: list[dict] = []
    stateful: list[dict] = []

    endpoints = extract_endpoints(spec)

    for endpoint in endpoints:
        # 4.1 Injection (stateless)
        for t in generate_injection_tests(endpoint):
            t.setdefault("owasp_category", "Injection")
            stateless.append(t)

        # 4.2 Auth stateless
        for t in generate_auth_tests(endpoint):
            t.setdefault("owasp_category", "Auth")
            stateless.append(t)

        # 4.4 Excessive Data Exposure (stateless)
        for t in generate_exposure_tests(endpoint):
            t.setdefault("owasp_category", "Exposure")
            stateless.append(t)

        # 4.3 BOLA (stateful)
        for t in generate_bola_tests(endpoint):
            t.setdefault("owasp_category", "BOLA")
            stateful.append(t)

    # 4.5 Rate Limiting (stateless, spec-level)
    for t in generate_rate_limit_tests(endpoints):
        t.setdefault("owasp_category", "RateLimit")
        stateless.append(t)

    # 4.6 Verb Tampering (stateless, spec-level)
    for t in generate_verb_tampering_tests(endpoints):
        t.setdefault("owasp_category", "VerbTamper")
        stateless.append(t)

    # 4.7 TLS (stateless, spec-level)
    for t in generate_tls_tests(spec, endpoints):
        t.setdefault("owasp_category", "TLS")
        stateless.append(t)

    # 4.8 Misconfiguration (stateless, spec-level)
    for t in generate_misconfiguration_tests(spec, endpoints):
        t.setdefault("owasp_category", "Misconfiguration")
        stateless.append(t)

    # NOTE: WrongRole tests removed — they duplicate BOLA tests.
    # Both use User B's token against the same endpoints expecting 403.
    # BOLA tests already cover cross-user access on all auth-required endpoints.

    # API5: Broken Function Level Authorization (stateful)
    for t in generate_function_level_auth_tests(endpoints):
        stateful.append(t)

    # Sort stateless tests by OWASP category order
    stateless.sort(key=lambda t: _OWASP_ORDER.get(t.get("owasp_category", ""), 99))

    # Stateless first, then stateful (runner does setup between the two batches)
    all_rules = stateless + stateful

    return all_rules
