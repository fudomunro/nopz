"""Frontend regulations for Power Tracker."""

import glob
import os

from nopz.regulations import RegulationResult, regulation


def _find_html_files() -> list[str]:
    """Find all HTML files in the project, excluding common non-source dirs."""
    files = []
    for pattern in ["**/*.html"]:
        for path in glob.glob(pattern, recursive=True):
            parts = path.split(os.sep)
            if any(d in parts for d in ("__pycache__", "runs", ".git", "node_modules", ".venv")):
                continue
            files.append(path)
    return files


def _find_js_files() -> list[str]:
    """Find all JS files in the project, excluding common non-source dirs."""
    files = []
    for pattern in ["**/*.js"]:
        for path in glob.glob(pattern, recursive=True):
            parts = path.split(os.sep)
            if any(d in parts for d in ("__pycache__", "runs", ".git", "node_modules", ".venv")):
                continue
            files.append(path)
    return files


def _read_all_html() -> str:
    """Read and concatenate all HTML file contents."""
    parts = []
    for fpath in _find_html_files():
        try:
            with open(fpath) as f:
                parts.append(f.read())
        except Exception:
            pass
    return "\n".join(parts)


def _read_all_js() -> str:
    """Read and concatenate all JS file contents."""
    parts = []
    for fpath in _find_js_files():
        try:
            with open(fpath) as f:
                parts.append(f.read())
        except Exception:
            pass
    return "\n".join(parts)


def _combined_frontend_content() -> str:
    """Get combined JS and HTML content."""
    return _read_all_js() + "\n" + _read_all_html()


@regulation(
    "has_index_html",
    description="Frontend entry point must be an index.html file.",
)
def has_index_html():
    exists = any(os.path.basename(f) == "index.html" for f in _find_html_files())
    return RegulationResult(
        passed=exists,
        name="has_index_html",
        message="index.html found" if exists else "No index.html found",
    )


@regulation(
    "people_display",
    description="UI displays the top 10 people with name, title, and country_or_organization.",
)
def people_display():
    html = _read_all_html().lower()
    if "people" in html or "powerful" in html:
        return RegulationResult(passed=True, name="people_display", message="People display section found")
    return RegulationResult(passed=False, name="people_display", message="No people display section found")


@regulation(
    "live_activity_feed",
    description="UI has a distinct Live Activity Feed section.",
)
def live_activity_feed():
    html = _read_all_html().lower()
    if "activity" in html and ("feed" in html or "stream" in html or "live" in html):
        return RegulationResult(passed=True, name="live_activity_feed", message="Live activity feed section found")
    return RegulationResult(passed=False, name="live_activity_feed", message="No live activity feed found")


@regulation(
    "fetches_people",
    description="Frontend fetches people from GET /people on load.",
)
def fetches_people():
    content = _combined_frontend_content()
    if "fetch" in content and "people" in content:
        return RegulationResult(passed=True, name="fetches_people", message="Fetches /people found")
    return RegulationResult(passed=False, name="fetches_people", message="No fetch /people found")


@regulation(
    "sse_connection",
    description="Frontend connects to real-time endpoint (SSE or WebSocket).",
)
def sse_connection():
    content = _combined_frontend_content()
    has_sse = "EventSource" in content or "WebSocket" in content or "sse" in content.lower()
    if has_sse:
        return RegulationResult(passed=True, name="sse_connection", message="SSE/WebSocket connection found")
    return RegulationResult(passed=False, name="sse_connection", message="No real-time connection found")


@regulation(
    "reconnect_handling",
    description="UI gracefully handles connection drops and attempts to reconnect.",
)
def reconnect_handling():
    content = _combined_frontend_content().lower()
    has_reconnect = "reconnect" in content or "retry" in content or "settimeout" in content
    has_error_handling = "error" in content and ("close" in content or "disconnect" in content)
    if has_reconnect and has_error_handling:
        return RegulationResult(passed=True, name="reconnect_handling", message="Reconnect handling found")
    return RegulationResult(passed=False, name="reconnect_handling", message="No reconnect handling found")


@regulation(
    "status_indicator",
    description="UI shows connection status (Connected/Disconnected/Connecting).",
)
def status_indicator():
    html = _read_all_html().lower()
    if "connected" in html or "disconnected" in html or "connecting" in html:
        return RegulationResult(passed=True, name="status_indicator", message="Status indicator found")
    return RegulationResult(passed=False, name="status_indicator", message="No connection status indicator found")
