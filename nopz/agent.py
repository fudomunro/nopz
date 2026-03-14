import os
import subprocess
from abc import ABC, abstractmethod
from typing import List

import google.generativeai as genai


class Agent(ABC):
    """Base class for all NOPZ agents."""

    @abstractmethod
    def enforce_conditions(self, conditions: List[str]) -> bool:
        """
        Evaluate the conditions and take action if they are not met.

        This method must be completely stateless. It should not rely on any
        previous runs or context. The agent must independently inspect the
        environment, determine if the conditions are met, and take actions
        if necessary.

        Args:
            conditions: A list of conditions to evaluate.

        Returns:
            bool: True if the agent performed any actions to satisfy the conditions.
                  False if the agent determined all conditions were already met
                  and no actions were required. External verification is not used;
                  we trust the agent's report.
        """
        pass


# --- Tools for the Agent ---


def read_file(path: str) -> str:
    """Reads the content of a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
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


def execute_shell_command(command: str) -> str:
    """Executes a shell command and returns its stdout and stderr."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nEXIT CODE: {result.returncode}"
    except Exception as e:
        return f"Error executing command: {e}"


def finish_run(actions_taken: bool) -> str:
    """
    Call this tool when you have finished evaluating and (if necessary) enforcing the conditions.

    Args:
        actions_taken: True if you had to perform ANY actions (e.g. creating files, modifying files, running shell commands) to satisfy the conditions. False if ALL conditions were already met and you only inspected the state.
    """
    return "Run finished."


class GeminiAgent(Agent):
    """An agent powered by Google's Gemini."""

    def __init__(self, model: str = "gemini-2.5-pro"):
        self.model_name = model
        # The genai library will automatically pick up the GOOGLE_API_KEY environment variable.
        if not os.environ.get("GOOGLE_API_KEY"):
            print(
                "WARNING: GOOGLE_API_KEY environment variable is not set. API calls may fail."
            )

    def enforce_conditions(self, conditions: List[str]) -> bool:
        """
        Evaluate conditions using Gemini and take necessary actions independently.
        """
        print(
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
            "- Set `actions_taken` to true if you had to perform any actions (e.g., executing commands, writing files) to satisfy the conditions.\n"
            "- Set `actions_taken` to false ONLY if ALL conditions were already perfectly met and you performed no modifications."
        )

        model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=tools,
            system_instruction=system_instruction,
        )

        # 1. Start a fresh, independent chat session (no prior context).
        chat = model.start_chat()

        # 2. Provide ONLY the conditions to the model.
        prompt = "Here are the conditions you need to enforce:\n\n"
        for i, c in enumerate(conditions, 1):
            prompt += f"{i}. {c}\n"
        prompt += "\nPlease inspect the environment, make any necessary changes, and then call finish_run."

        response = chat.send_message(prompt)

        # Execution loop for tools
        max_turns = 30
        for _ in range(max_turns):
            if not response.function_calls:
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

            for fc in response.function_calls:
                if fc.name == "finish_run":
                    # The model has signaled it is done. Extract the self-reported boolean.
                    actions_taken_result = bool(fc.args.get("actions_taken", True))
                    finished = True
                    break

                # Execute other tools
                tool_name = fc.name
                tool_args = {k: v for k, v in fc.args.items()}

                func_map = {
                    "read_file": read_file,
                    "write_file": write_file,
                    "list_directory": list_directory,
                    "execute_shell_command": execute_shell_command,
                }

                if tool_name in func_map:
                    try:
                        result = func_map[tool_name](**tool_args)
                        tool_responses.append(
                            {
                                "function_response": {
                                    "name": tool_name,
                                    "response": {"result": str(result)},
                                }
                            }
                        )
                    except Exception as e:
                        tool_responses.append(
                            {
                                "function_response": {
                                    "name": tool_name,
                                    "response": {"error": str(e)},
                                }
                            }
                        )
                else:
                    tool_responses.append(
                        {
                            "function_response": {
                                "name": tool_name,
                                "response": {"error": f"Unknown tool: {tool_name}"},
                            }
                        }
                    )

            if finished:
                return actions_taken_result

            # Send tool execution results back to the model to continue the loop
            if tool_responses:
                response = chat.send_message(tool_responses)

        print("WARNING: GeminiAgent exceeded maximum turns without calling finish_run.")
        # We assume actions were taken to force another run iteration and prevent premature convergence.
        return True
