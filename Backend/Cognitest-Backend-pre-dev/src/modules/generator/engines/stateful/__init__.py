"""
Stateful Security Test Engine.

Orchestrates multi-step authentication and authorization scenario testing
derived from an OpenAPI specification. Unlike the stateless engine this
package:

  1. Creates test users against the real target API.
  2. Logs in and stores JWT tokens in a shared TestContext.
  3. Creates API resources owned by one user.
  4. Runs cross-user authorization scenarios (401 / 403 checks).
  5. Classifies each response with a security severity label.
"""

from .executor import run_stateful_security_scenarios

__all__ = ["run_stateful_security_scenarios"]
