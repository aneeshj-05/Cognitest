"""
Security Outcome Classifier.

Maps (scenario_type, actual_http_status) → (SecurityClassification, Severity).

This module never makes HTTP requests.  All logic is pure / testable in
isolation.
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """Ordered severity levels for security findings."""

    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ScenarioType(str, Enum):
    """Three authorization scenario categories."""

    UNAUTHENTICATED = "A_UNAUTHENTICATED"
    WRONG_OWNER = "B_WRONG_OWNER"
    CORRECT_OWNER = "C_CORRECT_OWNER"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


class SecurityClassification:
    """
    Outcome of classifying a single HTTP response in a security scenario.

    Attributes:
        label:       Human-readable description of the outcome.
        severity:    Severity level (INFO / WARNING / HIGH / CRITICAL).
        passed:      True when the API behaves correctly from a security view.
    """

    __slots__ = ("label", "severity", "passed")

    def __init__(self, label: str, severity: Severity, passed: bool) -> None:
        self.label = label
        self.severity = severity
        self.passed = passed

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "severity": self.severity.value,
            "passed": self.passed,
        }


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------

# Server errors are always critical regardless of scenario
_SERVER_ERROR_RANGE = range(500, 600)

# 2xx statuses that indicate a successful response
_SUCCESS_STATUSES = {200, 201, 202, 204}


def classify_result(scenario_type: ScenarioType, actual_status: int) -> SecurityClassification:
    """
    Classify the HTTP response for a security scenario.

    Args:
        scenario_type: Which of the three authorization scenarios was executed.
        actual_status: The HTTP status code returned by the API.

    Returns:
        A :class:`SecurityClassification` with label, severity, and pass/fail.
    """
    # ------------------------------------------------------------------
    # Universal: server errors are always CRITICAL
    # ------------------------------------------------------------------
    if actual_status in _SERVER_ERROR_RANGE:
        return SecurityClassification(
            label="Server Error – Unhandled Exception",
            severity=Severity.CRITICAL,
            passed=False,
        )

    # ------------------------------------------------------------------
    # Scenario A – Request with NO Authorization header
    # Expected: 401 Unauthorized
    # ------------------------------------------------------------------
    if scenario_type == ScenarioType.UNAUTHENTICATED:
        if actual_status == 401:
            return SecurityClassification(
                label="Correct: Unauthenticated Request Rejected (401)",
                severity=Severity.INFO,
                passed=True,
            )
        if actual_status in _SUCCESS_STATUSES:
            return SecurityClassification(
                label="Missing Authentication Check – Endpoint Accessible Without Token",
                severity=Severity.CRITICAL,
                passed=False,
            )
        if actual_status == 403:
            return SecurityClassification(
                label="Auth Middleware Skipped – 403 Without Token (expected 401)",
                severity=Severity.HIGH,
                passed=False,
            )
        return SecurityClassification(
            label=f"Unexpected Response for Unauthenticated Request (got {actual_status})",
            severity=Severity.WARNING,
            passed=False,
        )

    # ------------------------------------------------------------------
    # Scenario B – Valid token but WRONG resource owner
    # Expected: 403 Forbidden
    # ------------------------------------------------------------------
    if scenario_type == ScenarioType.WRONG_OWNER:
        if actual_status == 403:
            return SecurityClassification(
                label="Correct: Cross-User Access Forbidden (403)",
                severity=Severity.INFO,
                passed=True,
            )
        if actual_status in _SUCCESS_STATUSES:
            return SecurityClassification(
                label="AUTHORIZATION VULNERABILITY – Wrong Owner Can Access Resource",
                severity=Severity.CRITICAL,
                passed=False,
            )
        if actual_status == 401:
            return SecurityClassification(
                label="Auth Middleware Issue – Token Rejected Instead of Ownership Check",
                severity=Severity.HIGH,
                passed=False,
            )
        if actual_status == 404:
            # Ambiguous but acceptable: resource not found before ownership check
            return SecurityClassification(
                label="Resource Not Found (404) – Ownership Check Could Not Be Verified",
                severity=Severity.WARNING,
                passed=False,  # Cannot confirm protection
            )
        return SecurityClassification(
            label=f"Unexpected Response for Wrong-Owner Request (got {actual_status})",
            severity=Severity.WARNING,
            passed=False,
        )

    # ------------------------------------------------------------------
    # Scenario C – Valid token, CORRECT resource owner
    # Expected: 2xx
    # ------------------------------------------------------------------
    if scenario_type == ScenarioType.CORRECT_OWNER:
        if actual_status in _SUCCESS_STATUSES:
            return SecurityClassification(
                label="Correct: Owner Can Access Own Resource",
                severity=Severity.INFO,
                passed=True,
            )
        if actual_status == 403:
            return SecurityClassification(
                label="Over-Restriction – Owner Cannot Access Own Resource (403)",
                severity=Severity.WARNING,
                passed=False,
            )
        if actual_status == 401:
            return SecurityClassification(
                label="Auth Error – Valid Token Rejected for Own Resource",
                severity=Severity.HIGH,
                passed=False,
            )
        return SecurityClassification(
            label=f"Unexpected Response for Owner Request (got {actual_status})",
            severity=Severity.WARNING,
            passed=False,
        )

    # Fallback (should never happen with typed ScenarioType)
    return SecurityClassification(
        label=f"Unknown Scenario – Cannot Classify (got {actual_status})",
        severity=Severity.WARNING,
        passed=False,
    )
