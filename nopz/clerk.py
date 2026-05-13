"""Clerk — LLM agent that makes changes to satisfy regulations.

The clerk is a "low-level bureaucrat" that modifies files and runs
commands to satisfy regulations. It has no validation capability —
it only makes changes. The runner controls when the clerk starts
and stops (turn-limited).
"""

import logging
import os
from typing import Optional

import llm

from nopz.agent import (
    _register_extra_model,
    execute_shell_command,
    list_directory,
    read_file,
    write_file,
)
from nopz.regulations import Regulation, RegulationResult

logger = logging.getLogger(__name__)


class Clerk:
    """LLM agent that makes changes to satisfy regulations."""

    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        base_url: Optional[str] = None,
        turns: int = 30,
    ):
        self.model_name = model
        self.base_url = base_url
        self.turns = turns

    def work(
        self,
        regulations: list[Regulation],
        failure_context: Optional[list[RegulationResult]] = None,
    ) -> tuple[str, dict]:
        """Have the clerk make changes to satisfy regulations.

        Args:
            regulations: The full list of regulations to satisfy.
            failure_context: Results from a previous failed validation, providing
                context on what needs to be fixed.

        Returns:
            Tuple of (summary, usage_dict).
        """
        logger.info(f"Clerk ({self.model_name}) starting work with {self.turns} turn limit")

        if self.base_url:
            _register_extra_model(self.model_name)

        # Inject API keys before get_model — OpenAI plugin checks env var immediately
        if "mimo" in self.model_name.lower():
            mimo_key = os.environ.get("MIMO_API_KEY")
            if mimo_key and not os.environ.get("OPENAI_API_KEY"):
                os.environ["OPENAI_API_KEY"] = mimo_key

        try:
            model = llm.get_model(self.model_name)
        except llm.UnknownModelError:
            error_msg = f"Model '{self.model_name}' not found."
            logger.error(error_msg)
            return error_msg, {}

        # Inject API keys
        if "gemini" in self.model_name.lower():
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if api_key:
                model.key = api_key
        if "mimo" in self.model_name.lower():
            api_key = os.environ.get("MIMO_API_KEY")
            if api_key:
                model.key = api_key
        if self.base_url:
            model.api_base = self.base_url

        tools = [read_file, write_file, list_directory, execute_shell_command]

        # Build the prompt
        regulations_text = "\n".join(
            f"{i}. {reg.name}: {reg.description}" for i, reg in enumerate(regulations, 1)
        )

        system_instruction = (
            "You are a clerk — a focused worker that makes changes to a codebase.\n"
            "Your job is to modify files and run commands to satisfy the given regulations.\n"
            "You do NOT evaluate whether regulations are met — that is done by others.\n"
            "You simply make the changes you believe are needed.\n"
            "Use the provided tools to read files, write files, and execute commands.\n"
            "When you have made all the changes you believe are necessary, stop.\n"
        )

        prompt = "Regulations to satisfy:\n\n"
        prompt += regulations_text
        prompt += "\n\nUse the tools to inspect the codebase and make necessary changes."

        if failure_context:
            prompt += "\n\nPrevious validation FAILED. Here are the failures:\n"
            for f in failure_context:
                prompt += f"- {f.name}: {f.message}\n"
            prompt += "\nFix the issues described above."

        logger.debug(f"Starting clerk conversation with model {self.model_name}")
        conversation = model.conversation()

        def get_usage(chain_response):
            input_tokens = 0
            output_tokens = 0
            for r in getattr(chain_response, "_responses", []):
                input_tokens += getattr(r, "input_tokens", 0) or 0
                output_tokens += getattr(r, "output_tokens", 0) or 0
            return {"input": input_tokens, "output": output_tokens}

        try:
            response = conversation.chain(
                prompt,
                system=system_instruction,
                tools=tools,
                chain_limit=self.turns,
            )

            # Drive the generator
            for _ in response:
                pass

            # If chain completes without error, the clerk finished its work
            usage = get_usage(response)
            summary = "Clerk completed work."
            logger.info(summary)
            return summary, usage

        except Exception as e:
            logger.error(f"Clerk error: {e}")
            return f"Clerk error: {e}", {}
