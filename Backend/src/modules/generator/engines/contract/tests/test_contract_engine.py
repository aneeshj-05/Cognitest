import unittest

from src.modules.generator.engines.contract.contract_generator import generate_contract_test_cases


class TestStrictContractGeneration(unittest.TestCase):
    def test_generates_only_spec_pure_cases_deterministically(self) -> None:
        canonical = {
            "doc_id": "d1",
            "operations": [
                {
                    "operation_key": "post:/x",
                    "method": "post",
                    "path": "/x",
                    "security_required": True,
                    "parameters": [],
                    "request_body": {
                        "required": True,
                        "content_type": "application/json",
                        "json_schema": {
                            "type": "object",
                            "required": ["email"],
                            "properties": {
                                "email": {"type": "string", "format": "email"},
                                "id": {"type": "string", "format": "uuid"},
                            },
                        },
                    },
                    "responses": {
                        "200": {"content_type": "application/json", "json_schema": {"type": "object"}},
                        "400": {"content_type": "application/json", "json_schema": {"type": "object"}},
                        "default": {"content_type": "application/json", "json_schema": {"type": "object"}},
                    },
                }
            ],
        }

        t1 = generate_contract_test_cases(canonical)
        t2 = generate_contract_test_cases(canonical)

        self.assertEqual(
            [(x["id"], x["test_id"], x["kind"], x.get("missing_field"), x.get("format_field")) for x in t1],
            [(x["id"], x["test_id"], x["kind"], x.get("missing_field"), x.get("format_field")) for x in t2],
        )

        kinds = [t["kind"] for t in t1]
        # Strict policy: exactly 1 positive + up to 3 allowed negatives.
        self.assertEqual(4, len(t1))
        self.assertIn("positive", kinds)
        self.assertIn("negative_required_missing", kinds)
        self.assertIn("negative_format_invalid", kinds)
        self.assertIn("negative_auth_missing", kinds)

        # Strict: expected_statuses must be exactly the response keys from spec.
        positive = next(t for t in t1 if t["kind"] == "positive")
        self.assertEqual(["200", "400", "default"], positive["expected_statuses"])


if __name__ == "__main__":
    unittest.main()
