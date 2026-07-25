"""
Reporter – builds a structured run report from execution results.

Provides a summary across all stateful test results without duplicating
logic that belongs in the executor or classifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .classifier import Severity
from .executor import StatefulTestResult
from .setup_orchestrator import SetupResult


# ---------------------------------------------------------------------------
# Report dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SeveritySummary:
    """Count of results per severity level."""

    critical: int = 0
    high: int = 0
    warning: int = 0
    info: int = 0

    def to_dict(self) -> dict:
        return {
            "CRITICAL": self.critical,
            "HIGH": self.high,
            "WARNING": self.warning,
            "INFO": self.info,
        }


@dataclass
class StatefulRunReport:
    """
    Complete report for one stateful security run.

    Attributes:
        setup:          Setup phase summary.
        total:          Total scenarios executed.
        passed:         Scenarios classified as correct security behavior.
        failed:         Scenarios that indicate a security issue.
        severity:       Counts per severity level.
        vulnerabilities: Only the results classified as security issues.
        all_results:    Every result in execution order.
    """

    setup: dict[str, Any]
    total: int
    passed: int
    failed: int
    severity: SeveritySummary
    vulnerabilities: list[dict[str, Any]] = field(default_factory=list)
    all_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "setup": self.setup,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "severity_summary": self.severity.to_dict(),
            "vulnerabilities": self.vulnerabilities,
            "all_results": self.all_results,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_report(
    setup_result: SetupResult,
    results: list[StatefulTestResult],
) -> StatefulRunReport:
    """
    Aggregate execution results into a :class:`StatefulRunReport`.

    Args:
        setup_result: Outcome of the pre-test setup phase.
        results:      All executed scenario results.

    Returns:
        A fully populated :class:`StatefulRunReport`.
    """
    severity = SeveritySummary()
    passed = 0
    vulnerabilities: list[dict] = []
    all_dicts: list[dict] = []

    for r in results:
        d = r.to_dict()
        all_dicts.append(d)

        if r.classification.passed:
            passed += 1

        sev = r.classification.severity
        if sev == Severity.CRITICAL:
            severity.critical += 1
        elif sev == Severity.HIGH:
            severity.high += 1
        elif sev == Severity.WARNING:
            severity.warning += 1
        else:
            severity.info += 1

        if not r.classification.passed:
            vulnerabilities.append(d)

    return StatefulRunReport(
        setup=setup_result.to_dict(),
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        severity=severity,
        vulnerabilities=vulnerabilities,
        all_results=all_dicts,
    )
