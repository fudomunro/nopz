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
        except (OSError, UnicodeDecodeError):
            pass
    return "\n".join(parts)


def _read_all_js() -> str:
    """Read and concatenate all JS file contents."""
    parts = []
    for fpath in _find_js_files():
        try:
            with open(fpath) as f:
                parts.append(f.read())
        except (OSError, UnicodeDecodeError):
            pass
    return "\n".join(parts)


def _combined_frontend_content() -> str:
    """Get combined JS and HTML content."""
    return _read_all_js() + "\n" + _read_all_html()


@regulation(
    "has_index_html",
    description=(
        "Frontend must have an index.html file as the application entry point. "
        "The check scans for any file named index.html, excluding directories "
        "__pycache__, runs, .git, node_modules, and .venv."
    ),
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
        "Frontend HTML must contain a section that displays people data. "
        "Passing requires the HTML content to contain the word 'people' or "
        "'powerful' (case-insensitive). Scope: all HTML files excluding "
        "directories __pycache__, runs, .git, node_modules, and .venv. "
        "Missing or unreadable files are skipped."
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
        "Frontend HTML must contain a section for real-time activity events. "
        "Passing requires the HTML content to contain the word 'activity' AND "
        "at least one of 'feed', 'stream', or 'live' (case-insensitive). "
        "Scope: all HTML files excluding directories __pycache__, runs, .git, "
        "node_modules, and .venv. Missing or unreadable files are skipped."
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
        "Frontend must retrieve data from a /people API endpoint on page "
        "load. Passing requires any .js or .html file to contain the "
        "substring '/people'. Scope: all .js and .html files excluding "
        "directories __pycache__, runs, .git, node_modules, and .venv. "
        "Missing or unreadable files are skipped."
    ),
)
def fetches_people():
    content = _combined_frontend_content()
    if "/people" in content:
        return RegulationResult(passed=True, name="fetches_people", message="Fetches /people found")
    return RegulationResult(passed=False, name="fetches_people", message="No /people endpoint call found")


@regulation(
    "sse_connection",
    description=(
        "Frontend JavaScript or HTML must establish a real-time connection "
        "(e.g. EventSource, WebSocket, or other streaming mechanism). Passing "
        "requires the combined content to contain 'EventSource', 'WebSocket', "
        "or 'sse' (case-insensitive). Scope: all .js and .html files excluding "
        "directories __pycache__, runs, .git, node_modules, and .venv. "
        "Missing or unreadable files are skipped."
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
        "Frontend must detect disconnections and automatically retry the "
        "connection. Passing requires at least one .js or .html file to "
        "contain 'reconnect' or 'retry' AND to contain 'error' together "
        "with 'close' or 'disconnect' (all case-insensitive). Scope: all "
        ".js and .html files excluding directories __pycache__, runs, .git, "
        "node_modules, and .venv. Missing or unreadable files are skipped."
    ),
)
def reconnect_handling():
    content = _combined_frontend_content().lower()
    has_reconnect = "reconnect" in content or "retry" in content
    has_error_handling = "error" in content and ("close" in content or "disconnect" in content)
    if has_reconnect and has_error_handling:
        return RegulationResult(passed=True, name="reconnect_handling", message="Reconnect handling found")
    return RegulationResult(passed=False, name="reconnect_handling", message="No reconnect handling found")


@regulation(
    "status_indicator",
    description=(
        "Frontend HTML must display the current connection state. Passing "
        "requires the HTML content (case-insensitive) to contain at least "
        "one of: 'connected', 'disconnected', or 'connecting'. Scope: all "
        "HTML files excluding directories __pycache__, runs, .git, "
        "node_modules, and .venv. Missing or unreadable files are skipped."
    ),
)
def status_indicator():
    html = _read_all_html().lower()
    if "connected" in html or "disconnected" in html or "connecting" in html:
        return RegulationResult(passed=True, name="status_indicator", message="Status indicator found")
    return RegulationResult(passed=False, name="status_indicator", message="No connection status indicator found")
