"""Number One Point Zero — the supreme Bureaucrat that reviews regulations.

Before the clerk/bureaucrat loop begins, Number One evaluates each regulation
against a set of guidelines to catch brittle, ambiguous, or poorly specified
regulations early.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Optional

import yaml

from nopz.agent import _setup_model
from nopz.regulations import Regulation

logger = logging.getLogger(__name__)


@dataclass
class ReviewGuideline:
    """A single guideline that regulations should satisfy."""

    id: str
    name: str
    description: str


@dataclass
class ReviewResult:
    """Result of reviewing a single regulation against all guidelines."""

    passed: bool
    regulation_name: str
    issues: list[str] = field(default_factory=list)


def load_guidelines(file_path: Optional[str] = None) -> list[ReviewGuideline]:
    """Load guidelines from a YAML file.

    Args:
        file_path: Path to a YAML guidelines file. If None, loads the
                   default guidelines shipped with the package.

    Returns:
        List of ReviewGuideline objects.
    """
    if file_path is not None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Guidelines file not found: {file_path}")
        with open(path) as f:
            data = yaml.safe_load(f)
    else:
        ref = resources.files("nopz").joinpath("regulation_guidelines.yaml")
        data = yaml.safe_load(ref.read_text())

    guidelines = []
    for entry in data.get("guidelines", []):
        guidelines.append(
            ReviewGuideline(
                id=entry["id"],
                name=entry["name"],
                description=entry["description"].strip(),
            )
        )
    return guidelines


def _build_review_prompt(
    regulation: Regulation, guidelines: list[ReviewGuideline]
) -> str:
    """Build the LLM prompt for reviewing a single regulation."""
    guidelines_text = "\n\n".join(
        f"Guideline {i + 1} — {g.name} (id: {g.id}):\n{g.description}"
        for i, g in enumerate(guidelines)
    )

    has_llm_validate = regulation.llm_validate is not None
    llm_validate_note = ""
    if has_llm_validate:
        llm_validate_note = (
            "\n\nThis regulation also has an LLM-based validation function "
            "(llm_validate). Consider whether the LLM validation is "
            "well-specified and whether its prompt provides clear criteria."
        )

    return (
        "You are Number One Point Zero, the supreme regulator. Your job is "
        "to review a regulation against a set of quality guidelines and "
        "determine if the regulation is well-specified enough to be "
        "reliably enforced.\n\n"
        "=== REGULATION ===\n"
        f"Name: {regulation.name}\n"
        f"Description: {regulation.description}\n"
        f"Has deterministic check: Yes\n"
        f"Has LLM-based validation: {'Yes' if has_llm_validate else 'No'}"
        f"{llm_validate_note}\n\n"
        "=== GUIDELINES ===\n"
        f"{guidelines_text}\n\n"
        "=== INSTRUCTIONS ===\n"
        "Evaluate the regulation against each guideline. Respond with ONLY "
        "a JSON object in this exact format (no markdown, no explanation "
        "outside the JSON):\n\n"
        "{\n"
        '  "passed": true/false,\n'
        '  "issues": ["issue 1 description", "issue 2 description"]\n'
        "}\n\n"
        'If the regulation satisfies all guidelines, set "passed" to true '
        'and "issues" to [].\n'
        'If it violates any guideline, set "passed" to false and list each '
        "specific issue."
    )


def _parse_review_response(response_text: str) -> tuple[bool, list[str]]:
    """Parse the LLM's JSON response into a (passed, issues) tuple.

    Handles edge cases: markdown code fences, preamble text, malformed JSON.
    """
    text = response_text.strip()

    # Strip markdown code fences if present
    code_block = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()

    # Try to find a JSON object in the text
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

    try:
        data = json.loads(text)
        passed = bool(data.get("passed", False))
        issues = data.get("issues", [])
        if not isinstance(issues, list):
            issues = [str(issues)]
        return passed, issues
    except (json.JSONDecodeError, ValueError):
        return False, [f"Could not parse review response: {response_text[:200]}"]


def _regulation_cache_key(
    regulation: Regulation, guidelines: list[ReviewGuideline]
) -> str:
    """Compute a stable cache key from a regulation's definition and guidelines."""
    hasher = hashlib.sha256()
    hasher.update(regulation.name.encode())
    hasher.update(regulation.description.encode())
    try:
        hasher.update(inspect.getsource(regulation.check).encode())
    except (OSError, TypeError):
        # getsource can fail for builtins/C functions — fall back to repr
        hasher.update(repr(regulation.check).encode())
    for g in guidelines:
        hasher.update(g.id.encode())
        hasher.update(g.name.encode())
        hasher.update(g.description.encode())
    return hasher.hexdigest()


def _load_cache(cache_path: Path) -> dict:
    """Load the review cache from disk."""
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache_path: Path, cache: dict) -> None:
    """Save the review cache to disk."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)


class NumberOne:
    """Reviews regulations against guidelines before the run begins."""

    def __init__(
        self,
        guidelines: list[ReviewGuideline],
        model_name: str,
        base_url: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        self.guidelines = guidelines
        self.model_name = model_name
        self.base_url = base_url
        self.cache_path = Path(cache_dir).joinpath("review_cache.json") if cache_dir else None

    def review(self, regulations: list[Regulation]) -> list[ReviewResult]:
        """Review all regulations against the guidelines.

        Args:
            regulations: The loaded regulations to review.

        Returns:
            List of ReviewResult, one per regulation.
        """
        results = []
        model = _setup_model(self.model_name, self.base_url)

        cache = _load_cache(self.cache_path) if self.cache_path else {}
        cache_dirty = False

        for reg in regulations:
            cache_key = _regulation_cache_key(reg, self.guidelines)

            if cache_key in cache:
                cached = cache[cache_key]
                result = ReviewResult(
                    passed=cached["passed"],
                    regulation_name=cached["regulation_name"],
                    issues=cached.get("issues", []),
                )
                results.append(result)
                status = "PASS" if result.passed else "FAIL"
                logger.info(f"Reviewing regulation: {reg.name} (cached) — {status}")
                continue

            logger.info(f"Reviewing regulation: {reg.name}")
            prompt = _build_review_prompt(reg, self.guidelines)

            try:
                response = model.prompt(prompt)
                response_text = response.text()
                passed, issues = _parse_review_response(response_text)
            except Exception as e:
                logger.error(f"LLM error reviewing '{reg.name}': {e}")
                passed = False
                issues = [f"LLM call failed: {e}"]

            result = ReviewResult(
                passed=passed,
                regulation_name=reg.name,
                issues=issues,
            )
            results.append(result)

            cache[cache_key] = {
                "passed": result.passed,
                "regulation_name": result.regulation_name,
                "issues": result.issues,
            }
            cache_dirty = True

            status = "PASS" if passed else "FAIL"
            logger.info(f"  {reg.name}: {status}")
            if not passed:
                for issue in issues:
                    logger.warning(f"    - {issue}")

        if self.cache_path and cache_dirty:
            _save_cache(self.cache_path, cache)

        return results

    def all_passed(self, results: list[ReviewResult]) -> bool:
        return all(r.passed for r in results)

    def failures(self, results: list[ReviewResult]) -> list[ReviewResult]:
        return [r for r in results if not r.passed]
