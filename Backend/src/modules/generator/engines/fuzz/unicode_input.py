"""
Unicode input fuzz test generators.
Generates tests with Unicode special characters, emoji, RTL text, and encoding edge cases.
"""
import uuid
from ...spec_parser import Endpoint, get_expected_status


UNICODE_PAYLOADS = [
    "こんにちは世界",                        # Japanese
    "مرحبا بالعالم",                        # Arabic (RTL)
    "🔥💀🚀✨🎯",                           # Emoji
    "\u202Eabc",                            # RTL override character
    "Ṫ̈̃ḙ̋ẍ̌t̨̛",                          # Combining diacritical marks
    "\ufeff",                               # BOM (byte order mark)
    "\u0000",                               # Unicode null
    "田中太郎",                              # CJK characters
    "Ω≈ç√∫",                               # Math symbols
    "\ud800",                               # Surrogate half (invalid)
    "é à ü ö",                              # Accented characters
    "‮test‬",                               # Bidi override
]


def generate_unicode_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate Unicode fuzz tests for an endpoint.
    Tests how the API handles various Unicode inputs.
    """
    tests = []

    # Fuzz query params with unicode
    expected_err = get_expected_status(endpoint, 400)
    if expected_err:
        for param in endpoint.query_params:
            for payload in UNICODE_PAYLOADS[:4]:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Unicode in query param '{param['name']}' — {repr(payload)[:30]}",
                    "test_type": "Fuzz",
                    "fuzz_type": "UNICODE_INPUT",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "headers": {},
                    "body": None,
                    "query_params": {param["name"]: payload},
                    "expected_status": expected_err,
                    "expected_behavior": f"Should handle Unicode gracefully (Expected {expected_err})",
                    "description": f"Sends Unicode input in query param '{param['name']}'",
                })

    # Fuzz body fields with unicode
    if endpoint.method in ("POST", "PUT", "PATCH") and endpoint.body_schema:
        expected_body_err = get_expected_status(endpoint, 400)
        if expected_body_err:
            properties = endpoint.body_schema.get("properties", {})
            for field_name, field_schema in list(properties.items())[:3]:
                if field_schema.get("type") == "string":
                    for payload in UNICODE_PAYLOADS[:3]:
                        tests.append({
                            "id": str(uuid.uuid4()),
                            "name": f"Unicode in body field '{field_name}'",
                            "test_type": "Fuzz",
                            "fuzz_type": "UNICODE_INPUT",
                            "endpoint_path": endpoint.path,
                            "method": endpoint.method,
                            "headers": {"Content-Type": "application/json"},
                            "body": {field_name: payload},
                            "query_params": {},
                            "expected_status": expected_body_err,
                            "expected_behavior": f"Should not crash on Unicode (Expected {expected_body_err})",
                            "description": f"Sends Unicode '{repr(payload)[:30]}' in body field '{field_name}'",
                        })

    return tests
