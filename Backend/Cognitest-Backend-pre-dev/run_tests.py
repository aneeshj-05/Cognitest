#!/usr/bin/env python
"""Simple test runner to check if pytest can run."""
import subprocess
import sys

print("=" * 70)
print("RUNNING BASELINE PYTEST SUITE")
print("=" * 70)

result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q"],
    cwd=r"C:\Users\cezza\OneDrive\Desktop\EnmazCognitest\Cognitest-Backend"
)

sys.exit(result.returncode)
