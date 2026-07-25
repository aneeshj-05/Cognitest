"""
Result classification engine — evaluates test results and classifies
vulnerabilities based on expected vs actual responses.

Transforms raw pass/fail status into structured security classifications
with severity levels.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Classification Rules ──
# Maps (fuzz_type, expected_status) → classification logic
CLASSIFICATION_RULES = {
    # Auth-related
    "MISSING_AUTH": {
        "expected": 401,
        "on_unexpected_200": ("AUTH_BYPASS", "CRITICAL"),
        "description": "Missing authentication should return 401",
    },
    "INVALID_AUTH": {
        "expected": 401,
        "on_unexpected_200": ("AUTH_ENFORCEMENT_FAILURE", "CRITICAL"),
        "description": "Invalid authentication should return 401/403",
    },
    "EXPIRED_TOKEN": {
        "expected": 401,
        "on_unexpected_200": ("TOKEN_EXPIRY_NOT_ENFORCED", "HIGH"),
        "description": "Expired token should return 401",
    },
    # Input validation
    "INVALID_ENUM": {
        "expected": 400,
        "on_unexpected_200": ("ENUM_VALIDATION_WEAKNESS", "MEDIUM"),
        "description": "Invalid enum value should return 400",
    },
    "MISSING_PARAMS": {
        "expected": 400,
        "on_unexpected_200": ("REQUIRED_FIELD_NOT_ENFORCED", "MEDIUM"),
        "description": "Missing required field should return 400",
    },
    "INVALID_PARAMS": {
        "expected": 400,
        "on_unexpected_200": ("INPUT_VALIDATION_WEAKNESS", "MEDIUM"),
        "description": "Invalid parameters should return 400",
    },
    # Fuzz types
    "RANDOM_STRING": {
        "expected": 400,
        "on_unexpected_200": ("INPUT_VALIDATION_WEAKNESS", "MEDIUM"),
        "description": "Random string fuzz should be rejected",
    },
    "UNICODE_INPUT": {
        "expected": 400,
        "on_unexpected_200": ("UNICODE_HANDLING_WEAKNESS", "LOW"),
        "description": "Unicode fuzz should be handled safely",
    },
    "LONG_INPUT": {
        "expected": 400,
        "on_unexpected_200": ("LENGTH_VALIDATION_WEAKNESS", "MEDIUM"),
        "description": "Oversized input should be rejected",
    },
    "XSS_FUZZ": {
        "expected": 400,
        "on_unexpected_200": ("XSS_VULNERABILITY", "HIGH"),
        "description": "XSS payload should be rejected",
    },
    "PATH_TRAVERSAL": {
        "expected": 400,
        "on_unexpected_200": ("PATH_TRAVERSAL_VULNERABILITY", "HIGH"),
        "description": "Path traversal should be rejected",
    },
    "PAYLOAD_INJECTION": {
        "expected": 400,
        "on_unexpected_200": ("INJECTION_VULNERABILITY", "CRITICAL"),
        "description": "Injection payload should be rejected",
    },
    # Security
    "SQL_INJECTION": {
        "expected": 400,
        "on_unexpected_200": ("SQL_INJECTION_VULNERABILITY", "CRITICAL"),
        "description": "SQL injection should be blocked",
    },
    "NOSQL_INJECTION": {
        "expected": 400,
        "on_unexpected_200": ("NOSQL_INJECTION_VULNERABILITY", "CRITICAL"),
        "description": "NoSQL injection should be blocked",
    },
    "XSS_INJECTION": {
        "expected": 400,
        "on_unexpected_200": ("XSS_VULNERABILITY", "HIGH"),
        "description": "XSS injection should be blocked",
    },
    "COMMAND_INJECTION": {
        "expected": 400,
        "on_unexpected_200": ("COMMAND_INJECTION_VULNERABILITY", "CRITICAL"),
        "description": "Command injection should be blocked",
    },
}

# Severity ordering for comparisons
SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}


def classify_result(
    fuzz_type: str,
    expected_status: int,
    actual_status: int,
    endpoint_path: str = "",
    method: str = "",
    requires_auth: bool = False,
) -> dict[str, Any]:
    """
    Classify a single test result into a structured security finding.

    Returns:
        Dict with: classification, severity, is_vulnerability, description
    """
    result = {
        "classification": "NORMAL",
        "severity": "INFO",
        "is_vulnerability": False,
        "description": "",
    }

    # 1. Exact Match — Perfect behavior according to contract
    if actual_status == expected_status:
        result["classification"] = "EXPECTED_RESPONSE"
        result["severity"] = "INFO"
        result["description"] = f"Server correctly returned {actual_status} as defined in contract"
        return result

    # 2. Unexpected Success (Security Bypass / Validation Failure)
    if actual_status == 200 or actual_status == 201 or actual_status == 204:
        # If we expected an error but got success
        if expected_status >= 400:
            rule = CLASSIFICATION_RULES.get(fuzz_type)
            if rule:
                classification, _ = rule["on_unexpected_200"]
                result["classification"] = classification
            else:
                result["classification"] = "VALIDATION_FAILURE"
            
            result["severity"] = "CRITICAL"
            result["is_vulnerability"] = True
            result["description"] = (
                f"Security Bypass: Expected error {expected_status}, but server returned {actual_status} OK. "
                "This indicates the input was not properly validated or security was bypassed."
            )
            return result

    # 3. Server Crash (5xx)
    if actual_status >= 500:
        result["classification"] = "SERVER_CRASH"
        result["severity"] = "HIGH"
        result["is_vulnerability"] = True
        result["description"] = f"Server Error {actual_status} — potential unhandled exception or crash."
        return result

    # 4. Safe Error but Contract Mismatch (e.g., got 400 when spec defined 422)
    SAFE_ERROR_CODES = {400, 401, 403, 404, 405, 413, 415, 422}
    if actual_status in SAFE_ERROR_CODES:
        result["classification"] = "CONTRACT_MISMATCH"
        result["severity"] = "LOW"
        result["is_vulnerability"] = False
        result["description"] = (
            f"Contract Mismatch: Expected {expected_status} but got {actual_status}. "
            "Server blocked the request safely, but did not use the status code defined in the OpenAPI spec."
        )
        return result

    # 5. Connection/timeout errors
    if actual_status == 0:
        result["classification"] = "CONNECTION_ERROR"
        result["severity"] = "HIGH"
        result["is_vulnerability"] = True
        result["description"] = "Request failed — connection error or timeout"
        return result

    # 6. Other unexpected status
    result["classification"] = "UNEXPECTED_RESPONSE"
    result["severity"] = "LOW"
    result["description"] = f"Expected {expected_status}, got {actual_status} (Undefined behavior)"
    return result

    # ── Auth-related responses ──
    if actual_status == 401 and not requires_auth:
        result["classification"] = "UNEXPECTED_AUTH_REQUIRED"
        result["severity"] = "INFO"
        result["description"] = "Endpoint requires auth but spec says it doesn't"
        return result

    # ── Expected response ──
    if actual_status == expected_status:
        result["classification"] = "EXPECTED_RESPONSE"
        result["severity"] = "INFO"
        result["description"] = f"Server correctly returned {actual_status}"
        return result

    # ── Connection/timeout errors ──
    if actual_status == 0:
        result["classification"] = "CONNECTION_ERROR"
        result["severity"] = "HIGH"
        result["is_vulnerability"] = True
        result["description"] = "Request failed — connection error or timeout"
        return result

    # ── Other unexpected status ──
    result["classification"] = "UNEXPECTED_RESPONSE"
    result["severity"] = "LOW"
    result["description"] = f"Expected {expected_status}, got {actual_status}"
    return result


def classify_batch(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Classify a batch of findings and enrich each with classification data.

    Args:
        findings: List of finding dicts (from anomaly detector or execution).

    Returns:
        Same list with added classification, severity, is_vulnerability fields.
    """
    for finding in findings:
        classification = classify_result(
            fuzz_type=finding.get("fuzz_type", "RANDOM_STRING"),
            expected_status=finding.get("expected_status", 400),
            actual_status=finding.get("status_code", finding.get("actual_status", 0)),
            endpoint_path=finding.get("endpoint_path", ""),
            method=finding.get("method", ""),
            requires_auth=finding.get("requires_auth", False),
        )
        finding["classification"] = classification["classification"]
        finding["severity"] = classification["severity"]
        finding["is_vulnerability"] = classification["is_vulnerability"]
        finding["classification_description"] = classification["description"]

    return findings


def generate_security_summary(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Generate a structured security summary from classified findings.
    """
    total = len(findings)
    vulnerabilities = [f for f in findings if f.get("is_vulnerability")]
    
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in vulnerabilities:
        sev = f.get("severity", "INFO")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    classification_counts: dict[str, int] = {}
    for f in findings:
        cls = f.get("classification", "UNKNOWN")
        classification_counts[cls] = classification_counts.get(cls, 0) + 1

    return {
        "total_tests": total,
        "total_vulnerabilities": len(vulnerabilities),
        "severity_breakdown": severity_counts,
        "classification_breakdown": classification_counts,
        "risk_level": (
            "CRITICAL" if severity_counts["CRITICAL"] > 0
            else "HIGH" if severity_counts["HIGH"] > 0
            else "MEDIUM" if severity_counts["MEDIUM"] > 0
            else "LOW" if severity_counts["LOW"] > 0
            else "SAFE"
        ),
    }
