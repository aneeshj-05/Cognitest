"""
Security test generators package.
"""
from .injection import generate_injection_tests
from .bola import generate_bola_tests
from .exposure import generate_exposure_tests
from .auth import generate_auth_tests
from .rate_limit import generate_rate_limit_tests
from .tls import generate_tls_tests
from .verb_tampering import generate_verb_tampering_tests
from .misconfiguration import generate_misconfiguration_tests
from .function_auth import generate_function_level_auth_tests

__all__ = [
    "generate_injection_tests",
    "generate_bola_tests",
    "generate_exposure_tests",
    "generate_auth_tests",
    "generate_rate_limit_tests",
    "generate_tls_tests",
    "generate_verb_tampering_tests",
    "generate_misconfiguration_tests",
    "generate_function_level_auth_tests",
]
