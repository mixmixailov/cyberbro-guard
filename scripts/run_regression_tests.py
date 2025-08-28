#!/usr/bin/env python3
"""Script to run regression tests with different options.

Usage:
    python scripts/run_regression_tests.py smoke    # Fast smoke tests
    python scripts/run_regression_tests.py all      # All regression tests  
    python scripts/run_regression_tests.py payment  # Payment regression tests only
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> int:
    """Run command and return exit code."""
    print(f"🔄 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_regression_tests.py <smoke|all|payment>")
        sys.exit(1)
    
    test_type = sys.argv[1].lower()
    
    if test_type == "smoke":
        # Fast smoke tests
        exit_code = run_command([
            "python", "-m", "pytest", 
            "tests/regression/", 
            "-m", "regression", 
            "-k", "smoke",
            "-v"
        ])
    elif test_type == "all":
        # All regression tests
        exit_code = run_command([
            "python", "-m", "pytest",
            "tests/regression/",
            "-m", "regression", 
            "-v"
        ])
    elif test_type == "payment":
        # Payment regression tests only
        exit_code = run_command([
            "python", "-m", "pytest",
            "tests/regression/test_payment_regression_smoke.py",
            "-m", "regression",
            "-v"
        ])
    else:
        print(f"❌ Unknown test type: {test_type}")
        print("Available types: smoke, all, payment")
        sys.exit(1)
    
    if exit_code == 0:
        print("✅ All regression tests passed!")
    else:
        print("❌ Some regression tests failed!")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
