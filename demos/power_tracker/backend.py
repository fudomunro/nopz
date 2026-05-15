"""Backend regulations for Power Tracker."""

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
        except SyntaxError:
            pass
    return trees


def _import_names(tree: ast.Module) -> set[str]:
    """Collect all imported names from an AST (handles 'from X import Y' and 'import X')."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
            for alias in node.names:
                names.add(alias.name)
    return names


def _class_fields(node: ast.ClassDef) -> set[str]:
    """Get annotated field names from a class definition."""
    fields = set()
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            fields.add(item.target.id)
    return fields


def _base_class_names(node: ast.ClassDef) -> set[str]:
    """Get base class names (without module prefixes) for a class definition."""
    bases = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.add(base.id)
        elif isinstance(base, ast.Attribute):
            bases.add(base.attr)
    return bases


def _route_paths(tree: ast.Module) -> list[str]:
    """Extract route path strings from decorator arguments (e.g. @app.get("/people"))."""
    paths = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and dec.args:
                    for arg in dec.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            paths.append(arg.value)
    return paths


@regulation(
    "fastapi_framework",
    description=(
        "Backend must define an ASGI application instance using a framework that "
        "provides automatic request/response validation and OpenAPI documentation. "
        "The check scans Python files for an import of 'fastapi' and a call to "
        "FastAPI() that creates the application instance."
    ),
)
def fastapi_framework():
    for tree in _parse_all():
        names = _import_names(tree)
        if "fastapi" in names:
            # Check for FastAPI() call
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if (isinstance(func, ast.Name) and func.id == "FastAPI") or \
                       (isinstance(func, ast.Attribute) and func.attr == "FastAPI"):
                        return RegulationResult(passed=True, name="fastapi_framework", message="FastAPI app found")
    return RegulationResult(passed=False, name="fastapi_framework", message="No FastAPI app found")


@regulation(
    "cors_middleware",
    description=(
        "Backend must import CORSMiddleware and register it via add_middleware() "
        "on the application instance to allow cross-origin requests. The check "
        "scans Python files for 'CORSMiddleware' in imports or in an "
        "add_middleware() call."
    ),
)
def cors_middleware():
    for tree in _parse_all():
        names = _import_names(tree)
        if "CORSMiddleware" in names:
            return RegulationResult(passed=True, name="cors_middleware", message="CORS middleware configured")
        # Also check for add_middleware(CORSMiddleware, ...) pattern
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "add_middleware":
                    for arg in node.args:
                        name = arg.id if isinstance(arg, ast.Name) else (arg.attr if isinstance(arg, ast.Attribute) else None)
                        if name == "CORSMiddleware":
                            return RegulationResult(passed=True, name="cors_middleware", message="CORS middleware configured")
    return RegulationResult(passed=False, name="cors_middleware", message="No CORS middleware found")


@regulation(
    "person_model",
    description=(
        "A Pydantic model class (inheriting from BaseModel) must define annotated "
        "fields: id, name, title, country_or_organization, and power_rank. "
        "The check uses AST parsing to find classes with BaseModel in their bases "
        "and verifies all five field names are present as annotated assignments."
    ),
)
def person_model():
    required = {"id", "name", "title", "country_or_organization", "power_rank"}
    for tree in _parse_all():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = _base_class_names(node)
                if "BaseModel" in bases:
                    fields = _class_fields(node)
                    if required.issubset(fields):
                        return RegulationResult(passed=True, name="person_model", message="Person model has all required fields")
                    missing = required - fields
                    if missing.issubset(required) and len(fields) > 0:
                        return RegulationResult(passed=False, name="person_model", message=f"Person model missing: {missing}")
    return RegulationResult(passed=False, name="person_model", message="No Pydantic model with required fields found")


@regulation(
    "activity_model",
    description=(
        "A Pydantic model class (inheriting from BaseModel) must define annotated "
        "fields: id, person_id, timestamp, location, and description. "
        "The check uses AST parsing to find classes with BaseModel in their bases "
        "and verifies all five field names are present as annotated assignments."
    ),
)
def activity_model():
    required = {"id", "person_id", "timestamp", "location", "description"}
    for tree in _parse_all():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = _base_class_names(node)
                if "BaseModel" in bases:
                    fields = _class_fields(node)
                    if required.issubset(fields):
                        return RegulationResult(passed=True, name="activity_model", message="Activity model has all required fields")
    return RegulationResult(passed=False, name="activity_model", message="Activity model not found or missing required fields")


@regulation(
    "people_endpoint",
    description=(
        "Backend must define a route handler whose path contains '/people'. "
        "The check uses AST parsing to scan all Python files for function "
        "decorator arguments containing the substring '/people'."
    ),
)
def people_endpoint():
    try:
        for tree in _parse_all():
            for path in _route_paths(tree):
                if "/people" in path:
                    return RegulationResult(passed=True, name="people_endpoint", message="GET /people endpoint found")
    except (OSError, SyntaxError) as e:
        return RegulationResult(passed=False, name="people_endpoint", message=f"Check error: {e}")
    return RegulationResult(passed=False, name="people_endpoint", message="GET /people endpoint not found")


@regulation(
    "activities_endpoint",
    description=(
        "Backend must define a route handler whose path contains both 'person_id' "
        "and 'activit' (matching patterns like /people/{person_id}/activities). "
        "The check uses AST parsing to scan all Python files for function "
        "decorator arguments matching both substrings."
    ),
)
def activities_endpoint():
    try:
        for tree in _parse_all():
            for path in _route_paths(tree):
                if "person_id" in path and "activit" in path:
                    return RegulationResult(passed=True, name="activities_endpoint", message="Activities endpoint found")
    except (OSError, SyntaxError) as e:
        return RegulationResult(passed=False, name="activities_endpoint", message=f"Check error: {e}")
    return RegulationResult(passed=False, name="activities_endpoint", message="Activities endpoint not found")


@regulation(
    "sse_endpoint",
    description=(
        "Backend must define a streaming route handler that uses EventSourceResponse, "
        "StreamingResponse, or WebSocket for real-time data delivery. "
        "The check verifies that a Python file both imports one of these streaming "
        "classes and defines a route whose path contains 'stream'."
    ),
)
def sse_endpoint():
    sse_imports = {"EventSourceResponse", "StreamingResponse", "WebSocket"}
    try:
        for tree in _parse_all():
            names = _import_names(tree)
            if names & sse_imports:
                for path in _route_paths(tree):
                    if "stream" in path:
                        return RegulationResult(passed=True, name="sse_endpoint", message="SSE/streaming endpoint found")
    except (OSError, SyntaxError) as e:
        return RegulationResult(passed=False, name="sse_endpoint", message=f"Check error: {e}")
    return RegulationResult(passed=False, name="sse_endpoint", message="No SSE/streaming endpoint found")


@regulation(
    "error_handling",
    description=(
        "Backend must handle errors using HTTPException (imported from the web "
        "framework) or by setting status_code on route decorators or response "
        "objects. The check scans Python files for an 'HTTPException' import or "
        "a keyword argument status_code=404 in any function call."
    ),
)
def error_handling():
    try:
        for tree in _parse_all():
            names = _import_names(tree)
            if "HTTPException" in names:
                return RegulationResult(passed=True, name="error_handling", message="Error handling found")
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant) and kw.value.value == 404:
                            return RegulationResult(passed=True, name="error_handling", message="Error handling found")
    except (OSError, SyntaxError) as e:
        return RegulationResult(passed=False, name="error_handling", message=f"Check error: {e}")
    return RegulationResult(passed=False, name="error_handling", message="No HTTP error handling found")
