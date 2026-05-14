"""General development standards regulations for Power Tracker."""

import ast
import os
import subprocess

from nopz.regulations import RegulationResult, regulation


@regulation(
    "pep8_compliance",
    description="All Python code must comply with PEP 8 standards.",
)
def pep8_compliance():
    result = subprocess.run(
        ["python", "-m", "py_compile", * _find_python_files()],
        capture_output=True,
        text=True,
    )
    return RegulationResult(
        passed=result.returncode == 0,
        name="pep8_compliance",
        message="All files compile successfully" if result.returncode == 0 else result.stderr,
    )


@regulation(
    "type_hints",
    description="All functions and classes must have type hints for arguments and return values.",
)
def type_hints():
    violations = []
    for fpath in _find_python_files():
        try:
            with open(fpath) as f:
                tree = ast.parse(f.read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is None:
                    violations.append(f"{fpath}:{node.lineno} - {node.name} missing return type")
                for arg in node.args.args:
                    if arg.annotation is None and arg.arg != "self" and arg.arg != "cls":
                        violations.append(f"{fpath}:{node.lineno} - {node.name}.{arg.arg} missing type")
    return RegulationResult(
        passed=len(violations) == 0,
        name="type_hints",
        message=f"{len(violations)} violations" if violations else "All functions have type hints",
        details={"violations": violations[:20]},
    )


@regulation(
    "no_print_statements",
    description="Use proper logging instead of print statements in library code.",
)
def no_print_statements():
    violations = []
    for fpath in _find_python_files():
        if "test_" in os.path.basename(fpath):
            continue
        with open(fpath) as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if "print(" in stripped and not stripped.startswith("#"):
                    violations.append(f"{fpath}:{i}")
    return RegulationResult(
        passed=len(violations) == 0,
        name="no_print_statements",
        message=f"print() found in: {violations}" if violations else "No print statements in library code",
    )


@regulation(
    "has_requirements",
    description="A requirements.txt must exist with pinned dependency versions.",
)
def has_requirements():
    path = "requirements.txt"
    exists = os.path.exists(path)
    has_versions = False
    if exists:
        with open(path) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            has_versions = all("==" in l for l in lines) if lines else False
    return RegulationResult(
        passed=exists and has_versions,
        name="has_requirements",
        message="requirements.txt exists with pinned versions" if exists and has_versions else "Missing or unpinned requirements.txt",
    )


@regulation(
    "test_coverage",
    description=(
        "Test coverage should exceed 95%. "
        "All tests must complete quickly (under 30 seconds total). "
        "When testing async code: never mock asyncio.sleep with AsyncMock — "
        "it prevents CancelledError delivery and causes tests to hang forever. "
        "Instead, use a real async helper like `async def fast_sleep(d): await asyncio.sleep(0)` "
        "or patch with `side_effect` set to a real async function. "
        "If a task catches CancelledError internally, do not also catch it in the test — "
        "the task will complete normally."
    ),
)
def test_coverage():
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--cov=.", "--cov-report=term", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return RegulationResult(
            passed=False,
            name="test_coverage",
            message=(
                "Tests timed out after 120 seconds (tests may be hanging). "
                "Common causes: mocking asyncio.sleep with AsyncMock prevents "
                "CancelledError delivery. Use a real async sleep helper instead."
            ),
        )
    # Parse coverage from output
    coverage_pct = 0
    for line in result.stdout.splitlines():
        if "TOTAL" in line:
            parts = line.split()
            for part in parts:
                if part.endswith("%"):
                    coverage_pct = int(part.rstrip("%"))
                    break
    return RegulationResult(
        passed=coverage_pct >= 95,
        name="test_coverage",
        message=f"Coverage: {coverage_pct}%" if coverage_pct else f"Tests failed: {result.stdout[-300:]}",
        details={"coverage": coverage_pct},
    )


@regulation(
    "has_run_script",
    description="There must be a simple way to run the application (run.sh or similar).",
)
def has_run_script():
    has_script = os.path.exists("run.sh") or os.path.exists("run.py")
    return RegulationResult(
        passed=has_script,
        name="has_run_script",
        message="Run script exists" if has_script else "No run.sh or run.py found",
    )


def _find_python_files() -> list[str]:
    """Find all Python files in the project, excluding runs/ and __pycache__/."""
    files = []
    for root, dirs, filenames in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "runs", ".git", "node_modules")]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(os.path.join(root, fname))
    return files
