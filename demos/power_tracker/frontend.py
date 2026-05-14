"""Frontend regulations for Power Tracker."""

import os

from nopz.regulations import RegulationResult, regulation


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
    for path in ["index.html", "frontend/index.html", "static/index.html"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read().lower()
                has_people_section = "people" in content or "powerful" in content
                if has_people_section:
                    return RegulationResult(passed=True, name="people_display", message="People display section found")
    return RegulationResult(passed=False, name="people_display", message="No people display section found")


@regulation(
    "live_activity_feed",
    description="UI has a distinct Live Activity Feed section.",
)
def live_activity_feed():
    for path in ["index.html", "frontend/index.html", "static/index.html"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read().lower()
                has_feed = "activity" in content and ("feed" in content or "stream" in content or "live" in content)
                if has_feed:
                    return RegulationResult(passed=True, name="live_activity_feed", message="Live activity feed section found")
    return RegulationResult(passed=False, name="live_activity_feed", message="No live activity feed found")


@regulation(
    "fetches_people",
    description="Frontend fetches people from GET /people on load.",
)
def fetches_people():
    for path in ["script.js", "app.js", "frontend/script.js", "static/script.js", "static/app.js"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "fetch" in content and "people" in content:
                    return RegulationResult(passed=True, name="fetches_people", message="Fetches /people found")
    return RegulationResult(passed=False, name="fetches_people", message="No fetch /people found")


@regulation(
    "sse_connection",
    description="Frontend connects to real-time endpoint (SSE or WebSocket).",
)
def sse_connection():
    for path in ["script.js", "app.js", "frontend/script.js", "static/script.js", "static/app.js"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                has_sse = "EventSource" in content or "WebSocket" in content or "sse" in content.lower()
                if has_sse:
                    return RegulationResult(passed=True, name="sse_connection", message="SSE/WebSocket connection found")
    return RegulationResult(passed=False, name="sse_connection", message="No real-time connection found")


@regulation(
    "reconnect_handling",
    description="UI gracefully handles connection drops and attempts to reconnect.",
)
def reconnect_handling():
    for path in ["script.js", "app.js", "frontend/script.js", "static/script.js", "static/app.js"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
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
    for path in ["index.html", "frontend/index.html", "static/index.html"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read().lower()
                has_status = ("connected" in content or "disconnected" in content or "connecting" in content)
                if has_status:
                    return RegulationResult(passed=True, name="status_indicator", message="Status indicator found")
    return RegulationResult(passed=False, name="status_indicator", message="No connection status indicator found")
