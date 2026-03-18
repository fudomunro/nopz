import logging
import os
import signal
import subprocess
from abc import ABC, abstractmethod
from typing import List, Tuple

import llm

logger = logging.getLogger(__name__)


class RunFinishedException(BaseException):
    """Exception raised when the agent calls the finish_run tool to signal completion.
    Inherits from BaseException to bypass llm's internal Exception catch block."""

    def __init__(self, actions_taken: bool, summary: str):
        self.actions_taken = actions_taken
        self.summary = summary
        super().__init__(summary)


class Agent(ABC):
    """Base class for all NOPZ agents."""

    @abstractmethod
    def enforce_conditions(self, conditions: List[str]) -> Tuple[bool, str]:
        """
        Evaluate the conditions and take action if they are not met.

        This method must be completely stateless. It should not rely on any
        previous runs or context. The agent must independently inspect the
        environment, determine if the conditions are met, and take actions
        if necessary.

        Args:
            conditions: A list of conditions to evaluate.

        Returns:
            Tuple[bool, str]: A tuple containing:
                - bool: True if the agent performed any actions to satisfy the conditions.
                        False if the agent determined all conditions were already met
                        and no actions were required. External verification is not used;
                        we trust the agent's report.
                - str: A summary of the work completed during this run, or why no work was needed.
        """
        pass


# --- Tools for the Agent ---


def read_file(path: str, offset: int = 0, limit: int = 4000) -> str:
    """Reads the content of a file in chunks. Use offset and limit to read large files."""
    logger.debug(f"Tool called: read_file(path={path}, offset={offset}, limit={limit})")
    try:
        with open(path, "r", encoding="utf-8") as f:
            f.seek(offset)
            content = f.read(limit)
            has_more = len(f.read(1)) > 0
            if has_more:
                content += f"\n...[TRUNCATED. Read more with offset={offset + limit}]"
            return content
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Writes content to a file. Creates the directory if it doesn't exist."""
    logger.debug(f"Tool called: write_file(path={path})")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_directory(path: str) -> str:
    """Lists the contents of a directory."""
    logger.debug(f"Tool called: list_directory(path={path})")
    try:
        items = os.listdir(path)
        return "\n".join(items) if items else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {e}"


def execute_shell_command(command: str, timeout: int = 120) -> str:
    """Executes a shell command and returns its stdout and stderr. Large outputs are written to files."""
    logger.debug(
        f"Tool called: execute_shell_command(command={command}, timeout={timeout})"
    )
    try:
        with subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
        ) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                exit_code = "TIMEOUT"
    except Exception as e:
        return f"Error executing command: {e}"

    res = f"EXIT CODE: {exit_code}\n"
    if len(stdout) > 4000:
        with open(".nopz_stdout.txt", "w", encoding="utf-8") as f:
            f.write(stdout)
        res += "STDOUT: Output too large, written to .nopz_stdout.txt\n"
    else:
        res += f"STDOUT:\n{stdout}\n"

    if len(stderr) > 4000:
        with open(".nopz_stderr.txt", "w", encoding="utf-8") as f:
            f.write(stderr)
        res += "STDERR: Output too large, written to .nopz_stderr.txt\n"
    else:
        res += f"STDERR:\n{stderr}\n"

    return res


def finish_run(actions_taken: bool, summary: str) -> str:
    """
    Call this tool when you have finished evaluating and (if necessary) enforcing the conditions.

    :param actions_taken: True if you had to perform ANY actions (e.g. creating files, modifying files, running shell commands) to satisfy the conditions. False if ALL conditions were already met and you only inspected the state.
    :param summary: A concise summary of the actions you took, or an explanation of why no actions were required.
    """
    logger.debug(
        f"Tool called: finish_run(actions_taken={actions_taken}, summary={summary})"
    )
    if isinstance(actions_taken, str):
        actions_taken = actions_taken.lower() == "true"
    else:
        actions_taken = bool(actions_taken)
    raise RunFinishedException(actions_taken, str(summary))


class LLMAgent(Agent):
    """An agent powered by the llm library (supports Gemini, OpenAI, Claude, etc)."""

    def __init__(self, model: str = "gemini-2.5-pro"):
        self.model_name = model

    def enforce_conditions(self, conditions: List[str]) -> Tuple[bool, str]:
        """
        Evaluate conditions using the specified model and take necessary actions independently.
        """
        logger.info(
            f"LLMAgent ({self.model_name}) is independently evaluating {len(conditions)} condition(s)..."
        )

        try:
            model = llm.get_model(self.model_name)
        except llm.UnknownModelError:
            error_msg = f"Model '{self.model_name}' not found. Make sure the appropriate llm plugin is installed."
            logger.error(error_msg)
            return True, error_msg

        # If it's a Gemini model, we can inject the key from standard Google env vars.
        # Otherwise, we rely on the llm library's native key management for that model.
        if "gemini" in self.model_name.lower():
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get(
                "GEMINI_API_KEY"
            )
            if api_key:
                model.key = api_key
            else:
                logger.warning(
                    "Neither GOOGLE_API_KEY nor GEMINI_API_KEY environment variable is set. API calls may fail depending on the model."
                )

        tools = [
            read_file,
            write_file,
            list_directory,
            execute_shell_command,
            finish_run,
        ]

        system_instruction = (
            "You are NOPZ, a strict, autonomous agent that enforces conditions on a system.\n"
            "Your task is to independently evaluate the given conditions and take actions to satisfy them if they are not met.\n"
            "You MUST use the provided tools to inspect the environment to see if conditions are met.\n"
            "If conditions are not met, you MUST use the tools to modify the environment so they become true.\n"
            "When you are completely finished, you MUST call the `finish_run` tool.\n"
            "- Set `actions_taken` to true if you had to perform any actions (e.g., executing state-changing commands, writing or modifying files) to satisfy the conditions.\n"
            "- Set `actions_taken` to false ONLY if ALL conditions were already perfectly met and you only performed read-only operations (e.g., reading files, running tests that passed without requiring any fixes).\n"
            "- Set `summary` to a concise description of what you did or why no actions were needed."
        )

        prompt = "Here are the conditions you need to enforce:\n\n"
        for i, c in enumerate(conditions, 1):
            prompt += f"{i}. {c}\n"
        prompt += "\nPlease inspect the environment, make any necessary changes, and then call finish_run."

        logger.debug(f"Starting chat session with model {self.model_name}")
        conversation = model.conversation()

        try:
            logger.debug("Sending initial prompt to the model...")
            # The chain function handles looping back tool responses automatically.
            response = conversation.chain(
                prompt,
                system=system_instruction,
                tools=tools,
                chain_limit=100,
            )

            # Drive the generator to trigger tool execution
            for _ in response:
                pass

            logger.warning(
                "LLMAgent exceeded maximum turns without calling finish_run."
            )
            # We assume actions were taken to force another run iteration and prevent premature convergence.
            return True, "Exceeded maximum turns without calling finish_run."

        except RunFinishedException as e:
            logger.debug(
                f"Model signaled finish_run. Actions taken: {e.actions_taken}, Summary: {e.summary}"
            )
            return e.actions_taken, e.summary
        except Exception as e:
            logger.error(f"Error during agent execution: {e}")
            return True, f"Error: {e}"
