"""
Rate limiting and brute-force protection test generators.

Covers OWASP API Security 4.5.

Generates ONE test per auth-related endpoint (login, signup, reset/OTP).
The runner's burst loop handles the actual repeated requests.
"""
import uuid
from ...spec_parser import Endpoint

_AUTH_KEYWORDS = {"login", "signin", "authenticate", "auth", "token"}
_SIGNUP_KEYWORDS = {"signup", "register", "sign-up", "sign_up"}
_RESET_KEYWORDS = {"reset", "forgot", "otp", "verify", "recover", "2fa", "mfa"}


def generate_rate_limit_tests(endpoints: list[Endpoint]) -> list[dict]:
    """
    Generate one rate-limit test per distinct auth-related endpoint.

    - Login/signin → brute-force protection (expect 429)
    - Signup/register → registration abuse (expect 429)
    - Reset/OTP → token guessing (expect 429)
    """
    tests = []
    seen_paths: set[str] = set()

    for ep in endpoints:
        if ep.method not in ("POST", "GET"):
            continue
        path_lower = ep.path.lower()

        # Deduplicate: one test per path
        if path_lower in seen_paths:
            continue

        is_login = any(k in path_lower for k in _AUTH_KEYWORDS)
        is_signup = any(k in path_lower for k in _SIGNUP_KEYWORDS)
        is_reset = any(k in path_lower for k in _RESET_KEYWORDS)

        if not (is_login or is_signup or is_reset):
            continue

        seen_paths.add(path_lower)

        if is_login and not is_signup:
            label = "Login brute-force"
            desc = (
                f"Sends rapid repeated requests to {ep.path} to test brute-force protection. "
                f"Server must return 429 after threshold."
            )
        elif is_signup:
            label = "Signup abuse"
            desc = (
                f"Sends rapid repeated signup requests to {ep.path}. "
                f"Server must rate-limit (429) to prevent account enumeration."
            )
        else:
            label = "OTP/Reset abuse"
            desc = (
                f"Sends rapid OTP/reset guesses to {ep.path}. "
                f"Server must enforce rate limit (429) to prevent exhaustive guessing."
            )

        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Rate Limiting: {label} on {ep.path}",
            "test_type": "Security",
            "owasp_category": "RateLimit",
            "endpoint_path": ep.path,
            "method": ep.method,
            "expected_status": 429,
            "description": desc,
        })

    return tests
