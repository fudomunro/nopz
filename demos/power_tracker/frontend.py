"""Frontend regulations for Power Tracker."""

import os

from nopz.regulations import RegulationResult, regulation


def _read_index_html() -> str:
    """Read index.html content from common locations."""
    for path in ["index.html", "frontend/index.html", "static/index.html"]:
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
    return ""


def _read_all_js() -> str:
    """Read all JS file contents from common locations."""
    parts = []
    for path in ["script.js", "app.js", "frontend/script.js", "static/script.js", "static/app.js"]:
        if os.path.exists(path):
            with open(path) as f:
                parts.append(f.read())
    return "\n".join(parts)


def _combined_frontend_content() -> str:
    """Get combined JS content from both files and inline scripts in index.html."""
    js = _read_all_js()
    html = _read_index_html()
    return js + "\n" + html


@regulation(
    "has_index_html",
    description="Frontend entry point must be an index.html file.",
)
def has_index_html():
    exists = os.path.exists("index.html") or os.path.exists("frontend/index.html") or os.path.exists("static/index.html")
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
    html = _read_index_html().lower()
    if "people" in html or "powerful" in html:
        return RegulationResult(passed=True, name="people_display", message="People display section found")
    return RegulationResult(passed=False, name="people_display", message="No people display section found")


@regulation(
    "live_activity_feed",
    description="UI has a distinct Live Activity Feed section.",
)
def live_activity_feed():
    html = _read_index_html().lower()
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
    content = _combined_frontend_content()
    has_reconnect = "reconnect" in content.lower() or "retry" in content.lower() or "setTimeout" in content
    has_error_handling = "error" in content.lower() and ("close" in content.lower() or "disconnect" in content.lower())
    if has_reconnect and has_error_handling:
        return RegulationResult(passed=True, name="reconnect_handling", message="Reconnect handling found")
    return RegulationResult(passed=False, name="reconnect_handling", message="No reconnect handling found")


@regulation(
    "status_indicator",
    description="UI shows connection status (Connected/Disconnected/Connecting).",
)
def status_indicator():
    html = _read_index_html().lower()
    if "connected" in html or "disconnected" in html or "connecting" in html:
        return RegulationResult(passed=True, name="status_indicator", message="Status indicator found")
    return RegulationResult(passed=False, name="status_indicator", message="No connection status indicator found")
