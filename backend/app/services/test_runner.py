"""Test execution logic.

This module contains a lightweight execution harness for running generated
tests against a target environment or mock. Executes actual HTTP requests
and compares results against expected status codes.
"""

import requests
from typing import List, Dict, Optional, Any


def run_tests(tests: List[Any], env: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
	"""Run provided tests and return a detailed summary with failures.

	Args:
		tests: List of test case dicts or pydantic models with test details.
		env: Environment configuration dict with 'baseUrl' key.

	Returns:
		A summary dict containing `total`, `passed`, `failed`, and `failedEndpoints` list.
	"""
	base_url = env.get("baseUrl", "") if env else ""
	results = {"total": 0, "passed": 0, "failed": 0, "failedEndpoints": []}

	for test in tests:
		# Only run if selected
		if not getattr(test, "selected", True):
			continue

		results["total"] += 1
		url = f"{base_url}{test.endpoint}"

		try:
			# Actual HTTP Call
			resp = requests.request(
				method=test.method,
				url=url,
				json=test.body if hasattr(test, "body") and test.body else None,
				timeout=5
			)
			if resp.status_code == test.expectedStatus:
				results["passed"] += 1
			else:
				results["failed"] += 1
				results["failedEndpoints"].append(f"{test.method} {test.endpoint}")
		except Exception as e:
			results["failed"] += 1
			results["failedEndpoints"].append(f"TIMEOUT: {test.endpoint}")

	return results

