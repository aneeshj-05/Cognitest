"""
Fuzz test sub-generators package.
Same pattern as security/ — granular sub-modules per fuzz type.
"""
from .random_strings import generate_random_string_tests
from .unicode_input import generate_unicode_tests
from .long_input import generate_long_input_tests
from .xss_fuzz import generate_xss_fuzz_tests
from .path_traversal import generate_path_traversal_tests
from .payload_injection import generate_payload_injection_tests
from .boundary_tests import (
    generate_boundary_value_tests,
    generate_missing_required_tests,
    generate_type_mismatch_tests,
    generate_enum_violation_tests,
    generate_extra_fields_test,
    generate_malformed_json_tests,
)

__all__ = [
    "generate_random_string_tests",
    "generate_unicode_tests",
    "generate_long_input_tests",
    "generate_xss_fuzz_tests",
    "generate_path_traversal_tests",
    "generate_payload_injection_tests",
    "generate_boundary_value_tests",
    "generate_missing_required_tests",
    "generate_type_mismatch_tests",
    "generate_enum_violation_tests",
    "generate_extra_fields_test",
    "generate_malformed_json_tests",
]

