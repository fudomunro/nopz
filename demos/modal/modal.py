"""Regulations for the Modal demo."""

import glob
import os
import re

from nopz.regulations import RegulationResult, regulation


def _find_html():
    """Find the main HTML file."""
    for path in glob.glob("**/*.html", recursive=True):
        parts = path.split(os.sep)
        if any(d in parts for d in ("__pycache__", "runs", ".git", "node_modules", ".venv")):
            continue
        return path
    return None


@regulation(
    "index_exists",
    description="An index.html file must exist as the entry point.",
)
def index_exists():
    path = _find_html()
    return RegulationResult(
        passed=path is not None,
        name="index_exists",
        message=f"Found {path}" if path else "No index.html found",
    )


@regulation(
    "has_button",
    description="The page must contain a button element.",
)
def has_button():
    path = _find_html()
    if not path:
        return RegulationResult(passed=False, name="has_button", message="No HTML file to check")
    with open(path) as f:
        content = f.read()
    has = bool(re.search(r"<button[\s>]", content, re.IGNORECASE))
    return RegulationResult(
        passed=has,
        name="has_button",
        message="Button element found" if has else "No button element found",
    )


@regulation(
    "has_modal",
    description="The page must contain a modal or dialog element.",
)
def has_modal():
    path = _find_html()
    if not path:
        return RegulationResult(passed=False, name="has_modal", message="No HTML file to check")
    with open(path) as f:
        content = f.read().lower()
    has_dialog = "<dialog" in content
    has_role = 'role="dialog"' in content or "role='dialog'" in content
    has_modal_class = bool(re.search(r'class="[^"]*modal[^"]*"', content))
    passed = has_dialog or has_role or has_modal_class
    return RegulationResult(
        passed=passed,
        name="has_modal",
        message="Modal element found" if passed else "No modal element found",
    )


@regulation(
    "button_opens_modal",
    description="The button must be wired to open the modal via JavaScript.",
)
def button_opens_modal():
    path = _find_html()
    if not path:
        return RegulationResult(passed=False, name="button_opens_modal", message="No HTML file to check")
    with open(path) as f:
        content = f.read()
    has_onclick = "onclick" in content and ("modal" in content.lower() or "dialog" in content.lower() or "show" in content.lower())
    has_event_listener = bool(re.search(r"addEventListener\s*\(\s*['\"]click['\"]", content))
    has_show_modal = "showModal" in content or ".modal(" in content or "modal(" in content.lower()
    passed = has_onclick or has_event_listener or has_show_modal
    return RegulationResult(
        passed=passed,
        name="button_opens_modal",
        message="Button-to-modal wiring found" if passed else "No button-to-modal wiring found",
    )


@regulation(
    "modal_closes",
    description="The modal must have a close mechanism (close button, Escape key, or click-outside).",
)
def modal_closes():
    path = _find_html()
    if not path:
        return RegulationResult(passed=False, name="modal_closes", message="No HTML file to check")
    with open(path) as f:
        content = f.read()
    has_close_btn = bool(re.search(r"close|dismiss|cancel", content, re.IGNORECASE)) and bool(re.search(r"<button", content, re.IGNORECASE))
    has_escape = "Escape" in content or "keydown" in content.lower()
    has_click_outside = "backdrop" in content.lower() or "overlay" in content.lower() or "click" in content.lower()
    passed = has_close_btn or has_escape or has_click_outside
    return RegulationResult(
        passed=passed,
        name="modal_closes",
        message="Modal close mechanism found" if passed else "No modal close mechanism found",
    )


@regulation(
    "proper_structure",
    description="The modal must use semantic HTML (<dialog> or role='dialog').",
)
def proper_structure():
    path = _find_html()
    if not path:
        return RegulationResult(passed=False, name="proper_structure", message="No HTML file to check")
    with open(path) as f:
        content = f.read().lower()
    has_dialog = "<dialog" in content
    has_role = 'role="dialog"' in content or "role='dialog'" in content
    passed = has_dialog or has_role
    return RegulationResult(
        passed=passed,
        name="proper_structure",
        message="Semantic modal structure found" if passed else "No semantic modal structure found",
    )


@regulation(
    "styled",
    description="The page must include CSS styling for the modal (overlay, positioning, or transitions).",
)
def styled():
    path = _find_html()
    if not path:
        return RegulationResult(passed=False, name="styled", message="No HTML file to check")
    with open(path) as f:
        content = f.read().lower()
    has_style_tag = "<style" in content
    has_link = 'rel="stylesheet"' in content
    has_inline = "style=" in content
    has_overlay = "overlay" in content or "backdrop" in content or "position: fixed" in content or "position:fixed" in content
    passed = (has_style_tag or has_link or has_inline) and has_overlay
    return RegulationResult(
        passed=passed,
        name="styled",
        message="Modal styling found" if passed else "No modal styling found",
    )
