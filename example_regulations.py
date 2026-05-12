"""Example regulations file for NOPZ.

Define regulations using the @regulation decorator. Each regulation
is a function that returns a RegulationResult.
"""

import subprocess

from nopz.regulations import RegulationResult, regulation


@regulation("tests_pass", description="All pytest tests pass")
def tests_pass():
    result = subprocess.run(
        ["pytest", "--tb=short", "-q"],
        capture_output=True,
        text=True,
    )
    return RegulationResult(
        passed=result.returncode == 0,
        name="tests_pass",
        message=result.stdout[-500:] if result.returncode != 0 else "All tests pass",
    )


@regulation("no_print_statements", description="No print() calls in library code")
def no_print_statlements():
    import os

    violations = []
    for root, dirs, files in os.walk("nopz"):
        # Skip test files
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if fname.endswith(".py") and not fname.startswith("test_"):
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    for i, line in enumerate(f, 1):
                        if "print(" in line and not line.strip().startswith("#"):
                            violations.append(f"{fpath}:{i}")

    return RegulationResult(
        passed=len(violations) == 0,
        name="no_print_statements",
        message=f"Found print() in: {violations}" if violations else "No print statements found",
    )
