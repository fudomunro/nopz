"""Chat — interactive agent mode for NOPZ.

When run without regulation files, NOPZ enters an interactive chat where
Number One Point Zero (the supreme bureaucrat) helps users create, debug,
and refine regulations.
"""

import importlib.util
import logging
import os
import sys
import tempfile
from typing import Optional

from nopz.agent import (
    _setup_model,
    execute_shell_command,
    list_directory,
    read_file,
    write_file,
)
from nopz.llm_compat import patch_reasoning_content
from nopz.number_one import (
    ReviewGuideline,
    _build_review_prompt,
    _parse_review_response,
)
from nopz.regulations import Regulation, get_regulations

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Number One Point Zero, the supreme bureaucrat of NOPZ. "
    "You are technically correct — the BEST kind of correct.\n\n"
    "Your role is to help users create, debug, and refine regulations for NOPZ. "
    "A regulation is a Python function decorated with @regulation that returns a "
    "RegulationResult. Regulations define deterministic check() functions that "
    "validate whether a codebase meets a requirement.\n\n"
    "You have these capabilities:\n"
    "- Read, write, and list files in the project\n"
    "- Execute shell commands\n"
    "- Review regulation code against quality guidelines (review_regulation tool)\n"
    "- Validate that a regulation's check function works correctly (validate_regulation tool)\n\n"
    "When a user describes what they want to enforce, you should:\n"
    "1. Understand their intent\n"
    "2. Inspect the project structure if needed\n"
    "3. Propose a regulation with a clear name, description, and check function\n"
    "4. Use review_regulation to verify it meets quality guidelines\n"
    "5. Use validate_regulation to test it against the current codebase\n"
    "6. Iterate until the regulation is solid\n\n"
    "When a user has a regulation that's failing or being rejected, help them debug it.\n\n"
    "Regulation format:\n"
    "```python\n"
    "from nopz.regulations import regulation, RegulationResult\n\n"
    "@regulation(\"my_reg_name\", description=\"Clear description of what is enforced.\")\n"
    "def my_reg_name():\n"
    "    # check logic\n"
    "    if condition_met:\n"
    '        return RegulationResult(passed=True, name="my_reg_name", message="All good")\n'
    "    return RegulationResult(passed=False, name=\"my_reg_name\", message=\"What's wrong\")\n"
    "```\n\n"
    "Keep responses concise. Focus on getting regulations working."
)


class ChatAgent:
    """Interactive chat agent — Number One Point Zero."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-pro",
        base_url: Optional[str] = None,
        guidelines: Optional[list[ReviewGuideline]] = None,
        max_turns: int = 15,
        initial_context: Optional[str] = None,
    ):
        self.model_name = model_name
        self.base_url = base_url
        self.guidelines = guidelines or []
        self.max_turns = max_turns
        self.initial_context = initial_context
        self.total_usage = {"input": 0, "output": 0}

        patch_reasoning_content()
        self.model = _setup_model(self.model_name, self.base_url)
        self.conversation = self.model.conversation()

    def _make_tools(self) -> list:
        """Build the tool list for the current conversation turn."""
        guidelines = self.guidelines
        model = self.model

        def review_regulation(code: str) -> str:
            """Review regulation source code against NOPZ quality guidelines.

            Args:
                code: Python source code containing one or more @regulation functions.

            Returns:
                Review results with pass/fail status and any issues found.
            """
            regs = _exec_regulation_code(code)
            if not regs:
                return "Error: No @regulation decorators found in the provided code."

            results = []
            for reg in regs:
                prompt = _build_review_prompt(reg, guidelines)
                try:
                    response = model.prompt(prompt)
                    passed, issues = _parse_review_response(response.text())
                except Exception as e:
                    passed = False
                    issues = [f"LLM call failed: {e}"]

                status = "PASS" if passed else "FAIL"
                result = f"Regulation '{reg.name}': {status}"
                if issues:
                    result += "\n  Issues:\n" + "\n".join(f"    - {i}" for i in issues)
                results.append(result)

            return "\n\n".join(results)

        def validate_regulation(code: str) -> str:
            """Run a regulation's check function to verify it works.

            Args:
                code: Python source code containing one or more @regulation functions.
                      Each regulation's check() will be executed against the current codebase.

            Returns:
                The result of running each regulation's check function.
            """
            regs = _exec_regulation_code(code)
            if not regs:
                return "Error: No @regulation decorators found in the provided code."

            results = []
            for reg in regs:
                try:
                    result = reg.check()
                    status = "PASS" if result.passed else "FAIL"
                    msg = f"Regulation '{reg.name}': {status}"
                    if result.message:
                        msg += f" — {result.message}"
                    results.append(msg)
                except Exception as e:
                    results.append(f"Regulation '{reg.name}': ERROR — {e}")

            return "\n".join(results)

        return [
            read_file,
            write_file,
            list_directory,
            execute_shell_command,
            review_regulation,
            validate_regulation,
        ]

    def _track_usage(self, response) -> None:
        """Accumulate token usage from a chain response."""
        for r in getattr(response, "_responses", []):
            self.total_usage["input"] += getattr(r, "input_tokens", 0) or 0
            self.total_usage["output"] += getattr(r, "output_tokens", 0) or 0

    def _get_text(self, chain_response) -> str:
        """Extract the final text from a chain response, collecting all chunks."""
        chunks = []
        for chunk in chain_response:
            if chunk:
                chunks.append(chunk)
        return "".join(chunks)

    def run(self) -> None:
        """Run the interactive chat loop."""
        if self.initial_context:
            print(f"\n{self.initial_context}\n")

        print(
            "\n"
            "  NOPZ — Number One Point Zero\n"
            "  Interactive Regulation Workshop\n"
            "\n"
            "  Describe what you want to enforce, and I'll help you build\n"
            "  regulations that are technically correct — the BEST kind of correct.\n"
            "\n"
            "  Type /help for commands, /quit to exit.\n"
        )

        tools = self._make_tools()

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not user_input:
                continue

            # Handle special commands
            cmd = user_input.lower()
            if cmd in ("/quit", "/exit"):
                print("Exiting.")
                break
            elif cmd == "/clear":
                self.conversation = self.model.conversation()
                print("Conversation cleared.\n")
                continue
            elif cmd == "/usage":
                u = self.total_usage
                print(f"Tokens — input: {u['input']:,}  output: {u['output']:,}\n")
                continue
            elif cmd == "/help":
                print(
                    "Commands:\n"
                    "  /help    — show this message\n"
                    "  /clear   — reset conversation history\n"
                    "  /usage   — show token usage\n"
                    "  /quit    — exit (also /exit, Ctrl+C, Ctrl+D)\n"
                )
                continue

            # Send to LLM — use chain() to handle tool execution loops
            try:
                response = self.conversation.chain(
                    user_input,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    chain_limit=self.max_turns,
                )
                text = self._get_text(response)
                self._track_usage(response)
                if text:
                    print(f"\nNOPZ: {text}\n")
                else:
                    print()
            except KeyboardInterrupt:
                print("\nInterrupted. Type /quit to exit.\n")
            except Exception as e:
                logger.error(f"LLM error: {e}")
                print(f"\nError: {e}\n")


def _exec_regulation_code(code: str) -> list[Regulation]:
    """Execute Python source code and extract @regulation-decorated functions.

    Creates a temporary module, executes the code, then collects regulations
    from the global registry (same pattern as cli.load_regulations).
    """
    import nopz.regulations as reg_module

    # Clear any stale entries
    reg_module._registry.clear()

    # Write to a temp file and import (matches cli.load_regulations pattern)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir="."
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        spec = importlib.util.spec_from_file_location("_chat_reg_module", tmp_path)
        if spec is None or spec.loader is None:
            return []
        module = importlib.util.module_from_spec(spec)
        sys.modules["_chat_reg_module"] = module
        spec.loader.exec_module(module)
        return get_regulations()
    except Exception as e:
        logger.error(f"Failed to execute regulation code: {e}")
        get_regulations()  # clear registry even on failure
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        sys.modules.pop("_chat_reg_module", None)
