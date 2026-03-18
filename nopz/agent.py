import logging
import os
import subprocess
from abc import ABC, abstractmethod
from typing import List, Tuple

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


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
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_directory(path: str) -> str:
    """Lists the contents of a directory."""
    try:
        items = os.listdir(path)
        return "\n".join(items) if items else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {e}"


def execute_shell_command(command: str, timeout: int = 120) -> str:
    """Executes a shell command and returns its stdout and stderr. Large outputs are written to files."""
    import signal

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

    Args:
        actions_taken: True if you had to perform ANY actions (e.g. creating files, modifying files, running shell commands) to satisfy the conditions. False if ALL conditions were already met and you only inspected the state.
        summary: A concise summary of the actions you took, or an explanation of why no actions were required.
    """
    return "Run finished."


class GeminiAgent(Agent):
    """An agent powered by Google's Gemini."""

    def __init__(self, model: str = "gemini-2.5-pro"):
        self.model_name = model

        # Determine the API key
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning(
                "Neither GOOGLE_API_KEY nor GEMINI_API_KEY environment variable is set. API calls may fail."
            )

        self.client = genai.Client(api_key=api_key, http_options={"timeout": 600000})

    def enforce_conditions(self, conditions: List[str]) -> Tuple[bool, str]:
        """
        Evaluate conditions using Gemini and take necessary actions independently.
        """
        logger.info(
            f"GeminiAgent is independently evaluating {len(conditions)} condition(s)..."
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

        config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=system_instruction,
            temperature=0.0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        # 1. Start a fresh, independent chat session (no prior context).
        logger.debug(f"Starting chat session with model {self.model_name}")
        chat = self.client.chats.create(
            model=self.model_name,
            config=config,
        )

        # 2. Provide ONLY the conditions to the model.
        prompt = "Here are the conditions you need to enforce:\n\n"
        for i, c in enumerate(conditions, 1):
            prompt += f"{i}. {c}\n"
        prompt += "\nPlease inspect the environment, make any necessary changes, and then call finish_run."

        logger.debug("Sending initial prompt to the model...")
        response = chat.send_message(prompt)

        # Execution loop for tools
        max_turns = 100
        for turn_num in range(1, max_turns + 1):
            logger.debug(f"--- Turn {turn_num} ---")

            if response.text:
                logger.debug(f"Model response text:\n{response.text}")

            if not response.function_calls:
                logger.debug(
                    "No function calls in response. Prompting model to use finish_run."
                )
                # If the model didn't call any tools (including finish_run), prompt it to do so.
                response = chat.send_message(
                    "Please use the finish_run tool to report your status and conclude the run."
                )
                continue

            tool_responses = []
            finished = False
            actions_taken_result = (
                True  # Default to True in case of early exit/parsing failure
            )
            summary_result = "No summary provided."

            for fc in response.function_calls:
                tool_args = fc.args or {}

                logger.debug(f"Model called tool: {fc.name} with args: {tool_args}")

                if fc.name == "finish_run":
                    # The model has signaled it is done. Extract the self-reported boolean.
                    val = tool_args.get("actions_taken", True)
                    if isinstance(val, str):
                        actions_taken_result = val.lower() == "true"
                    else:
                        actions_taken_result = bool(val)
                    summary_result = str(
                        tool_args.get("summary", "No summary provided.")
                    )
                    finished = True
                    break

                # Execute other tools
                tool_name = fc.name

                func_map = {
                    "read_file": read_file,
                    "write_file": write_file,
                    "list_directory": list_directory,
                    "execute_shell_command": execute_shell_command,
                }

                if tool_name in func_map:
                    try:
                        result = func_map[tool_name](**tool_args)
                        logger.debug(f"Tool {tool_name} returned successfully.")
                        tool_responses.append(
                            types.Part.from_function_response(
                                name=tool_name, response={"result": str(result)}
                            )
                        )
                    except Exception as e:
                        logger.debug(f"Tool {tool_name} raised exception: {e}")
                        tool_responses.append(
                            types.Part.from_function_response(
                                name=tool_name, response={"error": str(e)}
                            )
                        )
                else:
                    logger.debug(f"Unknown tool called: {tool_name}")
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"error": f"Unknown tool: {tool_name}"},
                        )
                    )

            if finished:
                logger.debug(
                    f"Model signaled finish_run. Actions taken: {actions_taken_result}, Summary: {summary_result}"
                )
                return actions_taken_result, summary_result

            # Send tool execution results back to the model to continue the loop
            if tool_responses:
                logger.debug(
                    f"Sending {len(tool_responses)} tool response(s) back to the model."
                )
                response = chat.send_message(tool_responses)

        logger.warning("GeminiAgent exceeded maximum turns without calling finish_run.")
        # We assume actions were taken to force another run iteration and prevent premature convergence.
        return True, "Exceeded maximum turns without calling finish_run."
