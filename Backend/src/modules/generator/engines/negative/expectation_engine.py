"""
expectation_engine.py — Validates actual HTTP response status against
the expected status codes derived from the Swagger spec.

All expected statuses are now spec-driven. The validation engine no longer
looks up hardcoded defaults from MUTATION_EXPECTATIONS. Instead, it receives
the expected statuses directly from the test case (which were resolved
from the spec during generation).

Changes from previous version:
  - Added validate_response_from_spec() which validates against spec-derived codes
  - Retained validate_response() for backward compatibility (rate limit etc.)
  - Cleaner docstrings
"""
from __future__ import annotations

from dataclasses import dataclass

from .mutation_taxonomy import FailureReason, MUTATION_EXPECTATIONS, MutationType


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    failure_reason: FailureReason | None
    allowed_statuses: list[int]
    actual_status: int
    note: str
    informational: bool = False   # True → result is advisory, not a hard pass/fail


def get_allowed_statuses(mutation_type: MutationType) -> list[int]:
    return list(MUTATION_EXPECTATIONS[mutation_type])


def is_server_error(actual_status: int) -> bool:
    return actual_status >= 500


def is_infra_error(actual_status: int) -> bool:
    return actual_status == 0


def validate_response_from_spec(
    expected_statuses: list[int],
    actual_status: int,
    *,
    mutation_type: MutationType | None = None,
) -> ValidationResult:
    """
    Classify the test outcome using spec-derived expected status codes.

    This is the primary validation path for negative tests. Expected statuses
    are derived from the Swagger spec during test generation — no hardcoded
    defaults are used.

    Args:
        expected_statuses: List of acceptable status codes (from the spec)
        actual_status: The actual HTTP status code received
        mutation_type: Optional mutation type for informational classification

    Returns a ValidationResult with:
      passed           — True if the API behaved correctly
      failure_reason   — Why it failed (None if passed)
      informational    — True if the result is advisory
      note             — Human-readable explanation

    Classification priority (in order):
      1. Infra error (status == 0)         → always FAIL, INFRA_ERROR
      2. Server crash (5xx)                → always FAIL, SERVER_ERROR
      3. Soft rate-limit (informational)   → PASS with informational=True if 429 absent
      4. Status in allowed list            → PASS
      5. Status is 200/201                 → FAIL, ACCEPTED_INVALID_INPUT (most dangerous)
      6. Any other status                  → FAIL, WRONG_REJECTION_CODE
    """
    allowed = list(expected_statuses) if expected_statuses else []

    # ── 1. Infrastructure failure ────────────────────────────────────────
    if is_infra_error(actual_status):
        return ValidationResult(
            passed=False,
            failure_reason=FailureReason.INFRA_ERROR,
            allowed_statuses=allowed,
            actual_status=actual_status,
            note="Request never reached server — network or infrastructure failure",
        )

    # ── 2. Server crash ──────────────────────────────────────────────────
    if is_server_error(actual_status):
        return ValidationResult(
            passed=False,
            failure_reason=FailureReason.SERVER_ERROR,
            allowed_statuses=allowed,
            actual_status=actual_status,
            note="Server crashed on this input — unhandled exception likely",
        )

    # ── 3. Soft rate-limit: no 429 observed → informational, not a failure
    if mutation_type == MutationType.RATE_LIMIT_INFORMATIONAL and actual_status != 429:
        return ValidationResult(
            passed=True,       # does NOT count as a test failure
            failure_reason=FailureReason.RATE_LIMIT_NOT_ENFORCED,
            allowed_statuses=allowed,
            actual_status=actual_status,
            note=(
                f"Rate limiting is not enforced — no 429 observed (got {actual_status}). "
                "This is informational: the API may intentionally allow high request rates."
            ),
            informational=True,
        )

    # ── 4. Status matches allowed list ──────────────────────────────────
    if actual_status in allowed:
        return ValidationResult(
            passed=True,
            failure_reason=None,
            allowed_statuses=allowed,
            actual_status=actual_status,
            note=f"Matched allowed status {actual_status}",
        )

    # ── 5. API accepted input it must reject ────────────────────────────
    if actual_status in (200, 201):
        return ValidationResult(
            passed=False,
            failure_reason=FailureReason.ACCEPTED_INVALID_INPUT,
            allowed_statuses=allowed,
            actual_status=actual_status,
            note="API accepted input it must reject — most dangerous failure type",
        )

    # ── 6. Rejected but with wrong code ─────────────────────────────────
    return ValidationResult(
        passed=False,
        failure_reason=FailureReason.WRONG_REJECTION_CODE,
        allowed_statuses=allowed,
        actual_status=actual_status,
        note=f"Got {actual_status}, expected one of {allowed}",
    )


def validate_response(mutation_type: MutationType, actual_status: int) -> ValidationResult:
    """
    Legacy validation path — validates using hardcoded MUTATION_EXPECTATIONS.

    Retained for backward compatibility (e.g., rate limit tests).
    For all other negative tests, use validate_response_from_spec() instead.
    """
    allowed = get_allowed_statuses(mutation_type)
    return validate_response_from_spec(
        allowed,
        actual_status,
        mutation_type=mutation_type,
    )