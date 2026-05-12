"""Backend regulations for Power Tracker."""

import ast
import importlib.util
import os
import subprocess

from nopz.regulations import RegulationResult, regulation


@regulation(
    "fastapi_framework",
    description="Backend must use FastAPI with app initialized in main.py.",
)
def fastapi_framework():
    main_exists = os.path.exists("main.py") or os.path.exists("backend/main.py")
    uses_fastapi = False
    if main_exists:
        for path in ["main.py", "backend/main.py"]:
            if os.path.exists(path):
                with open(path) as f:
                    content = f.read()
                    uses_fastapi = "FastAPI" in content
                break
    return RegulationResult(
        passed=main_exists and uses_fastapi,
        name="fastapi_framework",
        message="FastAPI app found in main.py" if main_exists and uses_fastapi else "Missing FastAPI app in main.py",
    )


@regulation(
    "cors_middleware",
    description="CORS middleware must be configured.",
)
def cors_middleware():
    for path in ["main.py", "backend/main.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "CORSMiddleware" in content:
                    return RegulationResult(passed=True, name="cors_middleware", message="CORS middleware configured")
    return RegulationResult(passed=False, name="cors_middleware", message="No CORS middleware found")


@regulation(
    "person_model",
    description="Pydantic Person model with id, name, title, country_or_organization, power_rank.",
)
def person_model():
    for path in ["models.py", "backend/models.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            required = ["id", "name", "title", "country_or_organization", "power_rank"]
            found = [field for field in required if field in content]
            if len(found) == len(required):
                return RegulationResult(passed=True, name="person_model", message="Person model has all required fields")
            missing = set(required) - set(found)
            return RegulationResult(passed=False, name="person_model", message=f"Person model missing: {missing}")
    return RegulationResult(passed=False, name="person_model", message="No models.py found")


@regulation(
    "activity_model",
    description="Pydantic Activity model with id, person_id, timestamp, location, description.",
)
def activity_model():
    for path in ["models.py", "backend/models.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            required = ["id", "person_id", "timestamp", "location", "description"]
            found = [field for field in required if field in content]
            if len(found) == len(required):
                return RegulationResult(passed=True, name="activity_model", message="Activity model has all required fields")
            missing = set(required) - set(found)
            return RegulationResult(passed=False, name="activity_model", message=f"Activity model missing: {missing}")
    return RegulationResult(passed=False, name="activity_model", message="No models.py found")


@regulation(
    "people_endpoint",
    description="GET /people returns list of people ordered by power_rank.",
)
def people_endpoint():
    for path in ["main.py", "backend/main.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if '/people' in content and ('get' in content.lower() or '@app.get' in content):
                    return RegulationResult(passed=True, name="people_endpoint", message="GET /people endpoint found")
    return RegulationResult(passed=False, name="people_endpoint", message="GET /people endpoint not found")


@regulation(
    "activities_endpoint",
    description="GET /people/{person_id}/activities returns activities for a person.",
)
def activities_endpoint():
    for path in ["main.py", "backend/main.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if 'person_id' in content and 'activities' in content:
                    return RegulationResult(passed=True, name="activities_endpoint", message="Activities endpoint found")
    return RegulationResult(passed=False, name="activities_endpoint", message="Activities endpoint not found")


@regulation(
    "sse_endpoint",
    description="GET /activities/stream provides SSE or WebSocket for real-time updates.",
)
def sse_endpoint():
    for path in ["main.py", "backend/main.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if 'stream' in content and ('EventSourceResponse' in content or 'WebSocket' in content or 'StreamingResponse' in content):
                    return RegulationResult(passed=True, name="sse_endpoint", message="SSE/streaming endpoint found")
    return RegulationResult(passed=False, name="sse_endpoint", message="No SSE/streaming endpoint found")


@regulation(
    "error_handling",
    description="Standard HTTP status codes and clear error messages.",
)
def error_handling():
    for path in ["main.py", "backend/main.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                has_404 = "404" in content or "HTTPException" in content
                if has_404:
                    return RegulationResult(passed=True, name="error_handling", message="Error handling found")
    return RegulationResult(passed=False, name="error_handling", message="No HTTP error handling found")
