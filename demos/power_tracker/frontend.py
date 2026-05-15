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
    description=(
        "Frontend HTML must contain a visible section that displays people data. "
        "The check reads all HTML files and passes if the combined content "
        "contains the word 'people' or 'powerful' (case-insensitive)."
    ),
)
def people_display():
    html = _read_all_html().lower()
    if "people" in html or "powerful" in html:
        return RegulationResult(passed=True, name="people_display", message="People display section found")
    return RegulationResult(passed=False, name="people_display", message="No people display section found")


@regulation(
    "live_activity_feed",
    description=(
        "Frontend HTML must contain a section for displaying real-time activity "
        "events. The check reads all HTML files and passes if the combined content "
        "contains the word 'activity' AND at least one of 'feed', 'stream', or "
        "'live' (case-insensitive)."
    ),
)
def live_activity_feed():
    html = _read_all_html().lower()
    if "activity" in html and ("feed" in html or "stream" in html or "live" in html):
        return RegulationResult(passed=True, name="live_activity_feed", message="Live activity feed section found")
    return RegulationResult(passed=False, name="live_activity_feed", message="No live activity feed found")


@regulation(
    "fetches_people",
    description=(
        "Frontend JavaScript or HTML must contain a fetch call to a /people "
        "endpoint. The check reads all .js and .html files and passes if the "
        "combined content contains both the substring 'fetch' and 'people'."
    ),
)
def fetches_people():
    content = _combined_frontend_content()
    if "fetch" in content and "people" in content:
        return RegulationResult(passed=True, name="fetches_people", message="Fetches /people found")
    return RegulationResult(passed=False, name="fetches_people", message="No fetch /people found")


@regulation(
    "sse_connection",
    description=(
        "Frontend JavaScript or HTML must establish a real-time connection using "
        "the EventSource API, WebSocket API, or reference SSE. The check reads "
        "all .js and .html files and passes if the combined content contains "
        "'EventSource', 'WebSocket', or 'sse' (case-insensitive)."
    ),
)
def sse_connection():
    content = _combined_frontend_content()
    has_sse = "EventSource" in content or "WebSocket" in content or "sse" in content.lower()
    if has_sse:
        return RegulationResult(passed=True, name="sse_connection", message="SSE/WebSocket connection found")
    return RegulationResult(passed=False, name="sse_connection", message="No real-time connection found")


@regulation(
    "reconnect_handling",
    description=(
        "Frontend JavaScript must implement connection retry logic. The check "
        "reads all .js and .html files and passes if the combined content "
        "(case-insensitive) contains at least one of 'reconnect', 'retry', or "
        "'settimeout' AND contains 'error' together with at least one of 'close' "
        "or 'disconnect'."
    ),
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
    description=(
        "Frontend HTML must display connection status text. The check reads all "
        "HTML files and passes if the combined content (case-insensitive) contains "
        "at least one of: 'connected', 'disconnected', or 'connecting'."
    ),
)
def status_indicator():
    html = _read_all_html().lower()
    if "connected" in html or "disconnected" in html or "connecting" in html:
        return RegulationResult(passed=True, name="status_indicator", message="Status indicator found")
    return RegulationResult(passed=False, name="status_indicator", message="No connection status indicator found")
