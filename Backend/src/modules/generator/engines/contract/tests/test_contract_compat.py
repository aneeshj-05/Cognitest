import unittest

from src.modules.generator.engines.contract.contract_generator import (
    coerce_canonical_spec,
    generate_contract_test_cases,
)


class TestOpenApiCoercion(unittest.TestCase):
    def test_openapi_is_coerced_to_minimal_canonical(self) -> None:
        spec = {
            "openapi": "3.0.0",
            "security": [{"bearerAuth": []}],
            "paths": {
                "/x": {
                    "get": {
                        "responses": {
                            "200": {
                                "description": "ok",
                                "content": {"application/json": {"schema": {"type": "object"}}},
                            },
                            "401": {"description": "no"},
                            "default": {"description": "other"},
                        }
                    }
                }
            },
        }

        canonical = coerce_canonical_spec(spec)
        self.assertIn("operations", canonical)
        self.assertEqual(1, len(canonical["operations"]))

        op = canonical["operations"][0]
        self.assertEqual("get:/x", op["operation_key"])
        self.assertTrue(op["security_required"])  # derived from global security

        tests = generate_contract_test_cases(canonical)
        self.assertTrue(tests)
        self.assertEqual(["200", "401", "default"], tests[0]["expected_statuses"])


if __name__ == "__main__":
    unittest.main()
