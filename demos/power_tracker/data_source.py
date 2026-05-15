"""Data source regulations for Power Tracker."""

import ast
import os

from nopz.regulations import RegulationResult, regulation


def _find_python_files() -> list[str]:
    """Find all Python files in the project, excluding common non-source dirs."""
    files = []
    for root, dirs, filenames in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "runs", ".git", "node_modules", ".venv")]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(os.path.join(root, fname))
    return files


def _parse_all() -> list[ast.Module]:
    """Parse all Python files and return their ASTs."""
    trees = []
    for fpath in _find_python_files():
        try:
            with open(fpath) as f:
                trees.append(ast.parse(f.read()))
        except (SyntaxError, OSError, UnicodeDecodeError):
            pass
    return trees


def _import_names(tree: ast.Module) -> set[str]:
    """Collect all imported names from an AST."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            for alias in node.names:
                names.add(alias.name)
    return names


@regulation(
    "seeds_10_people",
    description=(
        "Data source must seed exactly 10 person profiles. Each profile must "
        "be a dict or constructor call with at least one key matching a person "
        "field name (name, title, id, power_rank, or country). "
        "Scope: non-test Python source files. Missing or unparseable files "
        "are skipped."
    ),
)
def seeds_10_people():
    person_keys = {"name", "title", "id", "power_rank", "country"}
    for tree in _parse_all():
        for node in ast.walk(tree):
            if isinstance(node, ast.List) and len(node.elts) == 10:
                for elt in node.elts:
                    if isinstance(elt, ast.Dict):
                        keys = [k.value for k in elt.keys if isinstance(k, ast.Constant)]
                        if set(keys) & person_keys:
                            return RegulationResult(passed=True, name="seeds_10_people", message="Seeds 10 people found")
                    elif isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name):
                        kw_names = {kw.arg for kw in elt.keywords if kw.arg}
                        if kw_names & person_keys:
                            return RegulationResult(passed=True, name="seeds_10_people", message="Seeds 10 people found")
    return RegulationResult(passed=False, name="seeds_10_people", message="No seed logic for 10 people found")


@regulation(
    "thread_safe_storage",
    description=(
        "Data store must be safe for concurrent access from multiple "
        "threads or async tasks. Scope: non-test Python source files. "
        "Missing or unparseable files are skipped."
    ),
)
def thread_safe_storage():
    safe_imports = {"threading", "asyncio", "Lock", "RLock", "Semaphore", "Queue"}
    for tree in _parse_all():
        names = _import_names(tree)
        if names & safe_imports:
            return RegulationResult(passed=True, name="thread_safe_storage", message="Thread-safe storage found")
    return RegulationResult(passed=False, name="thread_safe_storage", message="No thread-safety mechanism found")


@regulation(
    "activity_generator",
    description=(
        "A background routine must continuously generate activity events "
        "at regular intervals. Scope: non-test Python source files. "
        "Missing or unparseable files are skipped."
    ),
)
def activity_generator():
    for tree in _parse_all():
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                has_sleep = False
                has_while = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func = child.func
                        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
                        if name == "sleep":
                            has_sleep = True
                    if isinstance(child, ast.While):
                        has_while = True
                if has_sleep and has_while:
                    return RegulationResult(passed=True, name="activity_generator", message="Activity generator found")
    return RegulationResult(passed=False, name="activity_generator", message="No activity generator found")


@regulation(
    "activity_references_valid_person",
    description=(
        "Generated activities must reference valid person_ids that exist "
        "in the data store. Scope: non-test Python source files. Missing "
        "or unparseable files are skipped."
    ),
)
def activity_references_valid_person():
    for tree in _parse_all():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "choice":
                    if isinstance(func.value, ast.Attribute) and func.value.attr == "random":
                        return RegulationResult(passed=True, name="activity_references_valid_person", message="Activities reference valid persons")
                    if isinstance(func.value, ast.Name) and func.value.id == "random":
                        return RegulationResult(passed=True, name="activity_references_valid_person", message="Activities reference valid persons")
    return RegulationResult(passed=False, name="activity_references_valid_person", message="Person reference logic not found")


@regulation(
    "activity_capped_at_100",
    description=(
        "Data store must cap activity history at a maximum of 100 entries, "
        "removing oldest entries when the limit is reached. Scope: non-test "
        "Python source files. Missing or unparseable files are skipped."
    ),
)
def activity_capped_at_100():
    for tree in _parse_all():
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for comp_node in [node.left] + node.comparators:
                    if isinstance(comp_node, ast.Constant) and comp_node.value == 100:
                        return RegulationResult(passed=True, name="activity_capped_at_100", message="Activity cap at 100 found")
                    if isinstance(comp_node, ast.Name) and _is_cap_variable(comp_node.id):
                        return RegulationResult(passed=True, name="activity_capped_at_100", message="Activity cap at 100 found")
            if isinstance(node, ast.Slice):
                if isinstance(node.upper, ast.Constant) and node.upper.value == 100:
                    return RegulationResult(passed=True, name="activity_capped_at_100", message="Activity cap at 100 found")
                if isinstance(node.upper, ast.Name) and _is_cap_variable(node.upper.id):
                    return RegulationResult(passed=True, name="activity_capped_at_100", message="Activity cap at 100 found")
    return RegulationResult(passed=False, name="activity_capped_at_100", message="No activity cap logic found")


_CAP_KEYWORDS = {"max", "cap", "limit", "capped", "maxsize", "maxlen"}


def _is_cap_variable(name: str) -> bool:
    """Check if a variable name suggests a capacity/limit constant."""
    lower = name.lower()
    has_activity = "activit" in lower
    has_cap = any(kw in lower for kw in _CAP_KEYWORDS)
    return has_activity and has_cap
