import os
import sys

import llm


class RunFinishedException(Exception):
    """Exception raised when the agent calls the finish_run tool to signal completion."""

    def __init__(self, actions_taken: bool, summary: str):
        self.actions_taken = actions_taken
        self.summary = summary
        super().__init__(summary)


def read_file(path: str, offset: int = 0, limit: int = 4000) -> str:
    """
    Reads the content of a file in chunks. Use offset and limit to read large files.

    :param path: The path to the file.
    :param offset: The byte offset to start reading from.
    :param limit: The maximum number of bytes to read.
    """
    print(f"\n[TOOL CALLED] read_file(path='{path}', offset={offset}, limit={limit})")
    if "dummy" in path:
        return "This is a dummy file with no real content."
    return f"File {path} not found."


def execute_shell_command(command: str, timeout: int = 120) -> str:
    """
    Executes a shell command and returns its stdout and stderr.

    :param command: The bash command to execute.
    :param timeout: Maximum execution time in seconds.
    """
    print(
        f"\n[TOOL CALLED] execute_shell_command(command='{command}', timeout={timeout})"
    )
    return "EXIT CODE: 0\nSTDOUT: Success\nSTDERR:"


def finish_run(actions_taken: bool, summary: str) -> str:
    """
    Call this tool when you have finished evaluating and (if necessary) enforcing the conditions.

    :param actions_taken: True if you had to perform ANY actions (e.g. creating files, modifying files, running shell commands) to satisfy the conditions. False if ALL conditions were already met.
    :param summary: A concise summary of the actions you took, or an explanation of why no actions were required.
    """
    print(
        f"\n[TOOL CALLED] finish_run(actions_taken={actions_taken}, summary='{summary}')"
    )
    raise RunFinishedException(actions_taken, summary)


def main():
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "Warning: GOOGLE_API_KEY or GEMINI_API_KEY environment variable is not set."
        )
        print("Please export an API key before running.")
        sys.exit(1)

    # We use a standard Gemini model available via llm-gemini
    model_name = "gemini-1.5-flash-latest"
    try:
        model = llm.get_model(model_name)
    except llm.UnknownModelError:
        print(
            f"Model '{model_name}' not found. Check if llm-gemini is installed properly."
        )
        sys.exit(1)

    model.key = api_key

    print(f"=== Testing LLM Chain with {model.model_id} ===")

    system_instruction = (
        "You are an autonomous agent testing a new tool system. "
        "Your task: "
        "1. First, use the `read_file` tool to inspect 'dummy.txt'. "
        "2. Then, use the `execute_shell_command` tool to run 'echo hello'. "
        "3. Finally, call the `finish_run` tool to report your completion. "
        "You must perform these steps iteratively and evaluate the tool responses."
    )

    prompt_text = (
        "Please follow the system instructions and execute the sequence of tools."
    )

    tools = [read_file, execute_shell_command, finish_run]

    # Using conversation to maintain history and chain for iterative tool calling
    conversation = model.conversation()

    print(f"\nUser: {prompt_text}")
    print("\n--- Starting Agent Chain ---")

    try:
        # conversation.chain automatically re-prompts the model with tool results
        # until the model returns a standard text response or an exception is raised
        response = conversation.chain(
            prompt_text, system=system_instruction, tools=tools
        )

        # We must iterate over the response or call .text() to drive the chain generator
        for chunk in response:
            if chunk:
                print(chunk, end="", flush=True)
        print()

        print("\nWarning: Model finished the chain without calling finish_run!")

    except RunFinishedException as e:
        print("\n\n=== Agent successfully finished the run! ===")
        print(f"Actions Taken: {e.actions_taken}")
        print(f"Summary:       {e.summary}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during the chain: {e}")


if __name__ == "__main__":
    main()
