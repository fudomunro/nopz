import logging
import os
import signal
import subprocess
from pathlib import Path

import llm
import yaml

logger = logging.getLogger(__name__)


class RunFinishedException(BaseException):
    """Exception raised when the agent calls the finish_run tool to signal completion.
    Inherits from BaseException to bypass llm's internal Exception catch block."""

    def __init__(self, actions_taken: bool, summary: str, usage: dict | None = None):
        self.actions_taken = actions_taken
        self.summary = summary
        self.usage = usage or {}
        super().__init__(summary)


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


def _register_extra_model(model_id: str) -> None:
    """Register a custom OpenAI-compatible model in the llm library's extra models config.

    Note: api_base is NOT set here because the llm plugin treats it as "no key needed"
    and uses a dummy key. Instead, api_base is set on the model object directly.
    """
    config_path = Path(llm.user_dir()) / "extra-openai-models.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if config_path.exists():
        with open(config_path, "r") as f:
            existing = yaml.safe_load(f) or []

    # Update or add the model entry (without api_base)
    updated = False
    for entry in existing:
        if entry.get("model_id") == model_id:
            entry["supports_tools"] = True
            updated = True
            break

    if not updated:
        existing.append({
            "model_id": model_id,
            "model_name": model_id,
            "supports_tools": True,
        })

    with open(config_path, "w") as f:
        yaml.dump(existing, f, default_flow_style=False)

    logger.debug(f"Registered model '{model_id}' in {config_path}")
