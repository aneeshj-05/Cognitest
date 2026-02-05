"""Test execution logic.

This module contains a lightweight execution harness for running generated
tests against a target environment or mock. Currently it's a synchronous
placeholder that returns a simple summary suitable for the frontend.
"""

from typing import List, Dict, Optional, Any


def run_tests(tests: List[Any], env: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
	"""Run provided tests and return a simple summary.

	Args:
		tests: List of test case dicts or pydantic models with an `id` field.
		env: Optional environment configuration (e.g., baseUrl).

	Returns:
		A summary dict containing `total`, `passed`, and `failed` counts.
	"""
	total = len(tests) if tests is not None else 0

	# Placeholder behavior: mark 75% of selected tests as passed.
	# If tests are pydantic models, they may have `selected` attribute.
	selected = []
	for t in tests:
		try:
			sel = getattr(t, "selected", None)
		except Exception:
			sel = None

		if sel is None:
			# assume selected by default
			selected.append(t)
		elif sel:
			selected.append(t)

	sel_count = len(selected)
	passed = int(sel_count * 0.75)
	failed = sel_count - passed

	return {"total": sel_count, "passed": passed, "failed": failed}

