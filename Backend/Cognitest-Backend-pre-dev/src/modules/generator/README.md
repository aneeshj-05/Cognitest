# Security Testing Engine

## Overview

A complete OWASP API Security Top 10 based test generation system that automatically generates comprehensive security test cases from OpenAPI/Swagger specifications.

## Architecture

```
generator/
├── engines/
│   ├── __init__.py
│   ├── security_engine.py          # Main orchestrator
│   ├── functional_engine.py        # Stub for future implementation
│   ├── negative_engine.py          # Stub for future implementation
│   ├── fuzz_engine.py              # Stub for future implementation
│   └── security/
│       ├── __init__.py
│       ├── injection.py            # SQL, XSS, Command injection tests
│       ├── bola.py                 # Broken Object-Level Authorization
│       ├── exposure.py             # Excessive Data Exposure
│       ├── auth.py                 # Authentication & Token tests
│       ├── rate_limit.py           # Rate limiting & brute-force
│       └── tls.py                  # TLS/SSL enforcement
└── spec_parser.py                  # OpenAPI spec parser
```

## Features

### 1. Injection Attack Tests (`injection.py`)

Generates tests for:
- **SQL Injection**: Tests query params, path params, and body fields with payloads like:
  - `' OR '1'='1`
  - `'; DROP TABLE users; --`
  - `' OR 1=1--`
  
- **XSS (Cross-Site Scripting)**: Tests with payloads like:
  - `<script>alert(1)</script>`
  - `<img src=x onerror=alert(1)>`
  - `<svg onload=alert(1)>`
  
- **Command Injection**: Tests with payloads like:
  - `; ls -la`
  - `&& whoami`
  - `| cat /etc/passwd`

### 2. BOLA Tests (`bola.py`)

Tests for Broken Object-Level Authorization:
- Unauthorized access via ID manipulation
- Cross-user resource access attempts
- Admin resource access by non-admin users
- Expected status: `403 Forbidden`

### 3. Excessive Data Exposure (`exposure.py`)

Validates that sensitive fields are not exposed:
- Checks for fields containing: `password`, `token`, `secret`, `hash`, `ssn`, `credit_card`, etc.
- Tests for mass assignment vulnerabilities
- Validates that internal/admin fields cannot be modified by regular users

### 4. Authentication & Authorization Tests (`auth.py`)

Comprehensive auth testing:
- Missing Authorization header → `401`
- Invalid/malformed tokens → `401`
- Expired tokens → `401`
- Tampered token signatures → `401`
- Wrong role/insufficient permissions → `403`
- Token reuse after logout → `401`

### 5. Rate Limiting Tests (`rate_limit.py`)

Tests brute-force protection on sensitive endpoints:
- Login/auth endpoints
- OTP endpoints
- Password reset endpoints
- Expected status: `429 Too Many Requests`

### 6. TLS/SSL Enforcement (`tls.py`)

Validates secure communication:
- HTTPS enforcement
- HTTP to HTTPS redirect
- Minimum TLS version (1.2+)
- Valid certificate validation

## Usage

### Basic Usage

```python
from src.modules.generator.engines import generate_security_tests

# Load your OpenAPI spec
spec = {
    "openapi": "3.0.0",
    "paths": {
        "/api/users/{id}": {
            "get": {
                "security": [{"bearerAuth": []}],
                "parameters": [...]
            }
        }
    }
}

# Generate security tests
test_cases = generate_security_tests(spec)

# Each test case has the structure:
# {
#     "id": "uuid",
#     "name": "Test name",
#     "test_type": "Security",
#     "endpoint_path": "/api/users/123",
#     "method": "GET",
#     "expected_status": 403,
#     "description": "Detailed description"
# }
```

### API Integration

The security engine is integrated into the project generation flow:

```python
# In generate.py
from src.modules.generator.engines import generate_security_tests

def generate_test_payload(spec: dict, test_type: str, api_key: str = ""):
    if test_type == "Security":
        return generate_security_tests(spec)
    # ... other test types
```

### Testing

Run the test script to verify the engine:

```bash
cd backend
source .venv/bin/activate
python test_security_engine.py
```

Expected output:
```
✓ Generated 96 security test cases

Injection Attacks: 58 tests
BOLA: 8 tests
Authentication & Authorization: 22 tests
Rate Limiting: 2 tests
TLS/SSL Enforcement: 4 tests
Excessive Data Exposure: 2 tests

✓ Total: 96 security tests generated successfully
```

## Test Case Output Format

All generated test cases conform to the `TestCaseOut` schema:

```python
{
    "id": str,                    # UUID
    "name": str,                  # Human-readable test name
    "test_type": "Security",      # Always "Security"
    "endpoint_path": str,         # Full endpoint path with params
    "method": str,                # HTTP method (GET, POST, etc.)
    "expected_status": int,       # Expected HTTP status code
    "description": str            # Detailed test description
}
```

## Spec Parser

The `spec_parser.py` module extracts structured endpoint information:

```python
class Endpoint:
    path: str                           # e.g., "/api/users/{id}"
    method: str                         # e.g., "GET"
    query_params: list[dict]            # Query parameters
    path_params: list[str]              # Path parameters like {id}
    body_schema: dict | None            # Request body schema
    response_schema: dict | None        # Response schema
    requires_auth: bool                 # Has security requirements
```

## OWASP API Security Top 10 Coverage

| OWASP Category | Implementation | Status |
|----------------|----------------|--------|
| API1:2023 Broken Object Level Authorization | `bola.py` | ✅ Complete |
| API2:2023 Broken Authentication | `auth.py` | ✅ Complete |
| API3:2023 Broken Object Property Level Authorization | `exposure.py` | ✅ Complete |
| API4:2023 Unrestricted Resource Consumption | `rate_limit.py` | ✅ Complete |
| API5:2023 Broken Function Level Authorization | `auth.py` | ✅ Complete |
| API6:2023 Unrestricted Access to Sensitive Business Flows | `rate_limit.py` | ✅ Complete |
| API7:2023 Server Side Request Forgery | Planned | 🔄 Future |
| API8:2023 Security Misconfiguration | `tls.py` | ✅ Complete |
| API9:2023 Improper Inventory Management | Planned | 🔄 Future |
| API10:2023 Unsafe Consumption of APIs | Planned | 🔄 Future |

## Extension Points

### Adding New Test Categories

1. Create a new module in `engines/security/`:
```python
# engines/security/new_category.py
import uuid
from ...spec_parser import Endpoint

def generate_new_tests(endpoint: Endpoint) -> list[dict]:
    tests = []
    # Your test generation logic
    return tests
```

2. Export in `engines/security/__init__.py`:
```python
from .new_category import generate_new_tests
```

3. Add to `security_engine.py`:
```python
def generate_security_tests(spec: dict) -> list[dict]:
    # ... existing code
    for endpoint in endpoints:
        all_tests.extend(generate_new_tests(endpoint))
```

### Customizing Payloads

Edit the payload lists in each module:

```python
# In injection.py
SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    # Add your custom payloads here
]
```

## Performance

- **Pure Python**: No external security scanners required
- **Fast**: Generates 100+ tests in <1 second
- **Scalable**: Handles large OpenAPI specs efficiently
- **Memory efficient**: Streaming generation, no large data structures

## Limitations

1. **Static Analysis Only**: Tests are generated from spec, not by executing requests
2. **No Dynamic Scanning**: Does not actually test the running API

---

# Contract Testing Runtime

The contract-testing API and storage now live under `src/modules/generator`.

## Run locally

```powershell
cd Cognitest-Backend
python -m uvicorn src.modules.generator.engines.contract.contract_app:app --reload --port 8001
```

## Endpoints

- `GET /health` — basic health check
- `POST /swagger/upload` — upload OpenAPI/Swagger file (YAML/JSON)
- `GET /swagger/{doc_id}/endpoints` — retrieve extracted endpoints
- `POST /contracts/{doc_id}/canonicalize` — build + store canonical contract model
- `GET /contracts/{doc_id}` — retrieve canonical model
- `POST /tests/generate` — generate deterministic contract test plan (positive + negative)
- `GET /tests/plan/{plan_id}` — retrieve stored test plan
- `POST /tests/run` — execute plan against a real API, validate, and store report
- `GET /reports/{run_id}` — retrieve structured JSON report

## Storage

Artifacts are stored under `src/modules/generator/engines/contract/storage/` (unless `CONTRACT_STORAGE_DIR` is set).

## CLI (optional)

```powershell
python -m src.modules.generator.engines.contract.cli generate --doc-id <doc_id> --include-negative --enable-discovery --config .\config.json
python -m src.modules.generator.engines.contract.cli run --plan-id <plan_id> --base-url https://example/api --config .\config.json --auth .\auth.json
```
3. **Spec Dependent**: Quality depends on OpenAPI spec completeness
4. **No False Positive Detection**: All potential issues are flagged

## Future Enhancements

- [ ] LLM-based test case enhancement using ANTHROPIC_API_KEY
- [ ] Dynamic payload generation based on field types
- [ ] Integration with actual security scanners (OWASP ZAP, Burp Suite)
- [ ] Test execution engine with real HTTP requests
- [ ] False positive filtering
- [ ] Custom rule engine for organization-specific security policies
- [ ] GraphQL API support
- [ ] gRPC API support

## Contributing

To add new security test categories:

1. Study the existing modules in `engines/security/`
2. Follow the same pattern: accept `Endpoint` or `spec`, return `list[dict]`
3. Ensure all test cases have required fields: `id`, `name`, `test_type`, `endpoint_path`, `method`, `expected_status`, `description`
4. Add comprehensive docstrings
5. Update this README

## License

Part of the Enmaz-Cognitest project.
