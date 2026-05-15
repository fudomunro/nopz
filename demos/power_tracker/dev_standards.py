"""General development standards regulations for Power Tracker."""

import ast
import os
import re
import subprocess

from nopz.regulations import RegulationResult, regulation


@regulation(
    "pep8_compliance",
    description="All Python code must comply with PEP 8 standards.",
)
def pep8_compliance():
    files = _find_python_files()
    # Batch to avoid exceeding arg length limits on large projects
    batch_size = 50
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        result = subprocess.run(
            ["python", "-m", "py_compile", *batch],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return RegulationResult(passed=False, name="pep8_compliance", message=result.stderr)
    return RegulationResult(passed=True, name="pep8_compliance", message="All files compile successfully")


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
    description=(
        "No Python source file (excluding test files matching 'test_*' and "
        "directories __pycache__, runs, .git, node_modules, .venv) may contain "
        "print() calls. All output must use the logging module instead. "
        "The check scans all .py files for un-commented print( occurrences."
    ),
)
def no_print_statements():
    violations = []
    for fpath in _find_python_files():
        if "test_" in os.path.basename(fpath):
            continue
        try:
            with open(fpath) as f:
                for i, line in enumerate(f, 1):
                    stripped = line.strip()
                    if "print(" in stripped and not stripped.startswith("#"):
                        violations.append(f"{fpath}:{i}")
        except (OSError, UnicodeDecodeError):
            continue
    return RegulationResult(
        passed=len(violations) == 0,
        name="no_print_statements",
        message=f"print() found in: {violations}" if violations else "No print statements in library code",
    )


@regulation(
    "has_requirements",
    description="Dependency versions must be pinned (requirements.txt or pyproject.toml).",
)
def has_requirements():
    # Check requirements.txt
    if os.path.exists("requirements.txt"):
        with open("requirements.txt") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            if lines and all("==" in l for l in lines):
                return RegulationResult(passed=True, name="has_requirements", message="requirements.txt with pinned versions")

    # Check pyproject.toml for pinned deps
    if os.path.exists("pyproject.toml"):
        with open("pyproject.toml") as f:
            content = f.read()
        # Look for == version pinning in dependencies
        pinned = re.findall(r'["\'][^"\']*==[^"\']*["\']', content)
        if pinned:
            return RegulationResult(passed=True, name="has_requirements", message="pyproject.toml with pinned versions")

    return RegulationResult(passed=False, name="has_requirements", message="No pinned dependency file found (expected requirements.txt or pyproject.toml)")


@regulation(
    "test_coverage",
    description=(
        "Test suite must achieve at least 95% code coverage measured by pytest --cov. "
        "The check runs pytest with coverage reporting and parses the TOTAL line. "
        "Tests must complete within 120 seconds or the check fails with a timeout."
    ),
)
def test_coverage():
    try:
        cov_env = {**os.environ, "COVERAGE_SOURCE": ".", "COVERAGE_OMIT": ".venv/*,*/__pycache__/*,test_*"}
        result = subprocess.run(
            ["python", "-m", "pytest", "--cov=.", "--cov-report=term", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
            env=cov_env,
        )
    except subprocess.TimeoutExpired:
        return RegulationResult(
            passed=False,
            name="test_coverage",
            message=(
                "Tests timed out after 120 seconds (tests may be hanging). "
                "Common causes: (1) mocking asyncio.sleep with AsyncMock prevents "
                "CancelledError delivery — use a real async sleep helper instead; "
                "(2) SSE/streaming endpoints blocking on asyncio.Event.wait() with no "
                "background task — trigger FastAPI lifespan events in your test fixture "
                "or mock the event."
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
    description=(
        "Project must contain at least one of the following files in the working "
        "directory to serve as an application entry point: run.sh, run.py, Makefile, "
        "justfile, docker-compose.yml, or Dockerfile. The check passes if any of "
        "these files exist."
    ),
)
def has_run_script():
    run_indicators = ["run.sh", "run.py", "Makefile", "justfile", "docker-compose.yml", "Dockerfile"]
    for name in run_indicators:
        if os.path.exists(name):
            return RegulationResult(passed=True, name="has_run_script", message=f"Run method found: {name}")
    return RegulationResult(passed=False, name="has_run_script", message="No run script or Makefile found")


def _find_python_files() -> list[str]:
    """Find all Python files in the project, excluding runs/ and __pycache__/."""
    files = []
    for root, dirs, filenames in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "runs", ".git", "node_modules", ".venv")]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(os.path.join(root, fname))
    return files
