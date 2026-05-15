"""General development standards regulations for Power Tracker."""

import ast
import os
import re
import subprocess

from nopz.regulations import RegulationResult, regulation


@regulation(
    "pep8_compliance",
    description=(
        "All Python source files in the project must have valid syntax. "
        "Scope: all .py files excluding directories __pycache__, runs, .git, "
        "node_modules, and .venv. The check verifies each file compiles "
        "without syntax errors and handles missing or unreadable files gracefully."
    ),
)
def pep8_compliance():
    files = _find_python_files()
    if not files:
        return RegulationResult(passed=True, name="pep8_compliance", message="No Python files found")
    batch_size = 50
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        try:
            result = subprocess.run(
                ["python", "-m", "py_compile", *batch],
                capture_output=True,
                text=True,
            )
        except OSError as e:
            return RegulationResult(passed=False, name="pep8_compliance", message=f"Check error: {e}")
        if result.returncode != 0:
            return RegulationResult(passed=False, name="pep8_compliance", message=result.stderr)
    return RegulationResult(passed=True, name="pep8_compliance", message="All files compile successfully")


@regulation(
    "type_hints",
    description=(
        "All Python functions and classes must have type annotations for "
        "arguments (except self/cls) and return values. Scope: all .py files "
        "excluding directories __pycache__, runs, .git, node_modules, and .venv. "
        "The check parses each file's AST and skips files that are missing, "
        "unreadable, or have syntax errors without raising exceptions."
    ),
)
def type_hints():
    violations = []
    for fpath in _find_python_files():
        try:
            with open(fpath) as f:
                tree = ast.parse(f.read())
        except (SyntaxError, OSError, UnicodeDecodeError):
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
        "No Python source file may contain print() calls; all output must use "
        "the logging module. Scope: all .py files excluding those with 'test_' "
        "prefix and directories __pycache__, runs, .git, node_modules, .venv. "
        "Commented-out print calls are ignored. Missing or unreadable files "
        "are skipped without error."
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
        message=f"print() found in: {violations}" if violations else "No print statements found",
    )


@regulation(
    "has_requirements",
    description=(
        "Project must declare dependencies with pinned versions. The check "
        "looks for requirements.txt or pyproject.toml in the project root "
        "(current working directory). It passes if requirements.txt exists "
        "with all non-comment, non-empty lines containing '==' (e.g. "
        "'flask==2.0.1'), or if pyproject.toml exists with dependency "
        "strings containing '=='. Missing files result in a clear failure."
    ),
)
def has_requirements():
    if os.path.exists("requirements.txt"):
        try:
            with open("requirements.txt") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
                if lines and all("==" in l for l in lines):
                    return RegulationResult(passed=True, name="has_requirements", message="requirements.txt with pinned versions")
        except OSError:
            pass

    if os.path.exists("pyproject.toml"):
        try:
            with open("pyproject.toml") as f:
                content = f.read()
            pinned = re.findall(r'["\'][^"\']*==[^"\']*["\']', content)
            if pinned:
                return RegulationResult(passed=True, name="has_requirements", message="pyproject.toml with pinned versions")
        except OSError:
            pass

    return RegulationResult(passed=False, name="has_requirements", message="No pinned dependency file found")


@regulation(
    "test_coverage",
    description=(
        "Test suite must achieve at least 80% code coverage. The check runs "
        "the test suite with coverage measurement and parses the coverage "
        "percentage from the output. A built-in timeout prevents the check "
        "from hanging indefinitely. Missing test runner or dependencies "
        "result in a clear failure message."
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
            message="Tests timed out after 120 seconds",
        )
    except OSError as e:
        return RegulationResult(passed=False, name="test_coverage", message=f"Could not run tests: {e}")
    coverage_pct = 0
    for line in result.stdout.splitlines():
        if "TOTAL" in line:
            parts = line.split()
            for part in parts:
                if part.endswith("%"):
                    coverage_pct = int(part.rstrip("%"))
                    break
    return RegulationResult(
        passed=coverage_pct >= 80,
        name="test_coverage",
        message=f"Coverage: {coverage_pct}%" if coverage_pct else f"Tests failed: {result.stdout[-300:]}",
        details={"coverage": coverage_pct},
    )


@regulation(
    "has_run_script",
    description=(
        "Project must provide a way to run the application. The check passes "
        "if the working directory contains at least one of: run.sh, run.py, "
        "Makefile, justfile, docker-compose.yml, or Dockerfile. Each is "
        "checked with os.path.exists(). Missing files are treated as absent, "
        "not as errors."
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
