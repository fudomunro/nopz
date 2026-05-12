"""Beaurocrat — runs regulations against the current state.

The beaurocrat is the "senior bureaucrat" that validates whether
a codebase satisfies all regulations. It runs deterministic checks
and optionally uses LLM-based validation for subjective regulations.
"""

import logging
import os
from typing import Optional

import llm

from nopz.regulations import Regulation, RegulationResult

logger = logging.getLogger(__name__)


def _setup_model(model_name: str, base_url: Optional[str] = None) -> llm.Model:
    """Configure and return an llm model instance."""
    if base_url:
        from nopz.agent import _register_extra_model
        _register_extra_model(model_name)

    # Inject API keys before get_model — OpenAI plugin checks env var immediately
    if "mimo" in model_name.lower():
        mimo_key = os.environ.get("MIMO_API_KEY")
        if mimo_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = mimo_key

    model = llm.get_model(model_name)

    if "gemini" in model_name.lower():
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            model.key = api_key
    if base_url:
        model.api_base = base_url

    return model


class Beaurocrat:
    """Validates regulations against the current state of the codebase."""

    def __init__(
        self,
        regulations: list[Regulation],
        llm_model: str = "gemini-2.5-pro",
        base_url: Optional[str] = None,
    ):
        self.regulations = regulations
        self.llm_model_name = llm_model
        self.base_url = base_url

    def validate_all(self) -> list[RegulationResult]:
        """Run all deterministic regulation checks."""
        results = []
        for reg in self.regulations:
            logger.info(f"Checking regulation: {reg.name}")
            try:
                result = reg.check()
                results.append(result)
            except Exception as e:
                logger.error(f"Regulation '{reg.name}' raised an exception: {e}")
                results.append(RegulationResult(
                    passed=False,
                    name=reg.name,
                    message=f"Exception during check: {e}",
                ))
        return results

    def llm_validate(self, regulation: Regulation, diff: str) -> RegulationResult:
        """Run LLM-based validation for a single regulation."""
        if not regulation.llm_validate:
            return RegulationResult(passed=True, name=regulation.name, message="No LLM validation defined")

        model = _setup_model(self.llm_model_name, self.base_url)

        prompt = (
            f"You are validating whether the following regulation is satisfied.\n\n"
            f"Regulation: {regulation.name}\n"
            f"Description: {regulation.description}\n\n"
            f"Here is the diff of recent changes:\n{diff}\n\n"
            f"Based on the diff and the regulation, is the regulation satisfied? "
            f"Respond with PASS or FAIL and a brief explanation."
        )

        response = model.prompt(prompt)
        text = response.text().strip().upper()

        passed = text.startswith("PASS")
        return RegulationResult(
            passed=passed,
            name=regulation.name,
            message=response.text().strip(),
        )

    def all_passed(self, results: list[RegulationResult]) -> bool:
        """Check if all regulation results passed."""
        return all(r.passed for r in results)

    def failures(self, results: list[RegulationResult]) -> list[RegulationResult]:
        """Return only the failed regulation results."""
        return [r for r in results if not r.passed]
