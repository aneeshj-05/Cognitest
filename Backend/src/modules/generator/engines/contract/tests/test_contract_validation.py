import unittest

from src.modules.generator.engines.contract.contract_validator import validate_exchange


class TestStrictValidation(unittest.TestCase):
    def test_undocumented_status_returns_violation(self) -> None:
        tc = {
            "method": "get",
            "endpoint_path": "/x",
            "expected_statuses": ["200"],
            "kind": "positive",
            "security_required": False,
        }

        op = {
            "method": "get",
            "path": "/x",
            "security_required": False,
            "responses": {
                "200": {"content_type": "application/json", "json_schema": {"type": "object"}},
            },
        }

        exchange = {
            "response": {
                "status_code": 500,
                "content_type": "application/json",
                "json": {},
            }
        }

        violations = validate_exchange(operation=op, test_case=tc, exchange=exchange, auth_provided=False)
        self.assertTrue(any(v["severity"] == "HIGH" and v["actual_status"] == 500 for v in violations))

    def test_content_type_mismatch_reports_violation(self) -> None:
        tc = {
            "method": "get",
            "endpoint_path": "/x",
            "expected_statuses": ["200"],
            "kind": "positive",
            "security_required": False,
        }

        op = {
            "method": "get",
            "path": "/x",
            "security_required": False,
            "responses": {
                "200": {"content_type": "application/json", "json_schema": {"type": "object"}},
            },
        }

        exchange = {
            "response": {
                "status_code": 200,
                "content_type": "text/plain",
                "text": "{}",
                "json": {},
            }
        }

        violations = validate_exchange(operation=op, test_case=tc, exchange=exchange, auth_provided=False)
        self.assertTrue(
            any(
                v["schema_validation_errors"]
                and "Response Content-Type does not match documented media type" in v["schema_validation_errors"][0]
                for v in violations
            )
        )

    def test_schema_validation_error_reports_details(self) -> None:
        tc = {
            "method": "get",
            "endpoint_path": "/x",
            "expected_statuses": ["200"],
            "kind": "positive",
            "security_required": False,
        }

        op = {
            "method": "get",
            "path": "/x",
            "security_required": False,
            "responses": {
                "200": {
                    "content_type": "application/json",
                    "json_schema": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                    },
                }
            },
        }

        exchange = {
            "response": {
                "status_code": 200,
                "content_type": "application/json",
                "json": {"id": 123},
            }
        }

        violations = validate_exchange(operation=op, test_case=tc, exchange=exchange, auth_provided=False)
        self.assertTrue(
            any(
                v["schema_validation_errors"]
                and any("response.json.id" in msg for msg in v["schema_validation_errors"])
                for v in violations
            )
        )

    def test_required_negative_returning_2xx_is_violation(self) -> None:
        tc = {
            "method": "post",
            "endpoint_path": "/x",
            "expected_statuses": ["200"],
            "kind": "negative_required_missing",
            "security_required": False,
        }
        op = {
            "method": "post",
            "path": "/x",
            "security_required": False,
            "responses": {
                "200": {"content_type": "application/json", "json_schema": {"type": "object"}},
            },
        }
        exchange = {
            "response": {
                "status_code": 200,
                "content_type": "application/json",
                "json": {},
            }
        }
        violations = validate_exchange(operation=op, test_case=tc, exchange=exchange, auth_provided=False)
        self.assertTrue(any("Required-field negative returned 2xx" in " ".join(v["schema_validation_errors"]) for v in violations))

    def test_auth_negative_returning_2xx_is_violation(self) -> None:
        tc = {
            "method": "get",
            "endpoint_path": "/x",
            "expected_statuses": ["200"],
            "kind": "negative_auth_missing",
            "security_required": True,
        }
        op = {
            "method": "get",
            "path": "/x",
            "security_required": True,
            "responses": {
                "200": {"content_type": "application/json", "json_schema": {"type": "object"}},
            },
        }
        exchange = {
            "response": {
                "status_code": 200,
                "content_type": "application/json",
                "json": {},
            }
        }
        violations = validate_exchange(operation=op, test_case=tc, exchange=exchange, auth_provided=False)
        self.assertTrue(any("Auth-negative returned 2xx" in " ".join(v["schema_validation_errors"]) for v in violations))

    def test_relaxed_success_allows_2xx_when_spec_is_default_only(self) -> None:
        import os

        os.environ["COGNITEST_RELAX_SUCCESS_STATUS"] = "1"
        try:
            tc = {
                "method": "post",
                "endpoint_path": "/x",
                "expected_statuses": ["default"],
                "kind": "positive",
                "security_required": False,
            }
            op = {
                "method": "post",
                "path": "/x",
                "security_required": False,
                "responses": {
                    "default": {"content_type": "application/json", "json_schema": {"type": "object"}},
                },
            }
            exchange = {
                "response": {
                    "status_code": 200,
                    "content_type": "application/json",
                    "json": {},
                }
            }
            violations = validate_exchange(operation=op, test_case=tc, exchange=exchange, auth_provided=False)
            self.assertFalse(any(v["severity"] == "HIGH" for v in violations))
        finally:
            os.environ.pop("COGNITEST_RELAX_SUCCESS_STATUS", None)


if __name__ == "__main__":
    unittest.main()
