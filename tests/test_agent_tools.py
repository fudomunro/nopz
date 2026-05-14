"""Tests for agent tool functions."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nopz.agent import (
    LLMAgent,
    RunFinishedException,
    _register_extra_model,
    execute_shell_command,
    finish_run,
    list_directory,
    read_file,
    write_file,
)


def test_read_file_basic(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    result = read_file(str(f))
    assert result == "hello world"


def test_read_file_with_offset_and_limit(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("abcdefghijklmnopqrstuvwxyz")
    result = read_file(str(f), offset=5, limit=5)
    assert "fghij" in result
    assert "TRUNCATED" in result


def test_read_file_nonexistent():
    result = read_file("/nonexistent/file.txt")
    assert "Error reading file" in result


def test_write_file_basic(tmp_path: Path):
    f = tmp_path / "out.txt"
    result = write_file(str(f), "new content")
    assert "Successfully wrote" in result
    assert f.read_text() == "new content"


def test_write_file_creates_dirs(tmp_path: Path):
    f = tmp_path / "sub" / "dir" / "out.txt"
    result = write_file(str(f), "nested")
    assert "Successfully wrote" in result
    assert f.read_text() == "nested"


def test_list_directory(tmp_path: Path):
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("")
    result = list_directory(str(tmp_path))
    assert "a.txt" in result
    assert "b.txt" in result


def test_list_directory_empty(tmp_path: Path):
    result = list_directory(str(tmp_path))
    assert "empty" in result.lower()


def test_list_directory_nonexistent():
    result = list_directory("/nonexistent/dir")
    assert "Error" in result


def test_execute_shell_command_success():
    result = execute_shell_command("echo hello")
    assert "EXIT CODE: 0" in result
    assert "hello" in result


def test_execute_shell_command_failure():
    result = execute_shell_command("exit 1")
    assert "EXIT CODE: 1" in result


def test_finish_run_raises_exception():
    with pytest.raises(RunFinishedException) as exc_info:
        finish_run(True, "done")
    assert exc_info.value.actions_taken is True
    assert exc_info.value.summary == "done"


def test_finish_run_string_actions_taken():
    with pytest.raises(RunFinishedException) as exc_info:
        finish_run("false", "nothing done")
    assert exc_info.value.actions_taken is False


def test_finish_run_string_true():
    with pytest.raises(RunFinishedException) as exc_info:
        finish_run("True", "did stuff")
    assert exc_info.value.actions_taken is True


def test_run_finished_exception_defaults():
    e = RunFinishedException(True, "done")
    assert e.actions_taken is True
    assert e.summary == "done"
    assert e.usage == {}


def test_register_extra_model_adds_new(tmp_path: Path):
    config = tmp_path / "extra-openai-models.yaml"
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.user_dir.return_value = str(tmp_path)
        _register_extra_model("test-model-1")
    import yaml
    with open(config) as f:
        data = yaml.safe_load(f)
    assert any(m["model_id"] == "test-model-1" for m in data)


def test_register_extra_model_updates_existing(tmp_path: Path):
    config = tmp_path / "extra-openai-models.yaml"
    import yaml
    with open(config, "w") as f:
        yaml.dump([{"model_id": "existing", "supports_tools": False}], f)
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.user_dir.return_value = str(tmp_path)
        _register_extra_model("existing")
    with open(config) as f:
        data = yaml.safe_load(f)
    entry = next(m for m in data if m["model_id"] == "existing")
    assert entry["supports_tools"] is True


def test_llmaagent_init():
    agent = LLMAgent(model="test-model", base_url="http://localhost:8000/v1")
    assert agent.model_name == "test-model"
    assert agent.base_url == "http://localhost:8000/v1"


def test_llmaagent_enforce_conditions_unknown_model():
    agent = LLMAgent(model="nonexistent-model")
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.UnknownModelError = Exception
        mock_llm.get_model.side_effect = Exception("Model not found")
        actions, summary, usage = agent.enforce_conditions(["condition A"])
    assert actions is True
    assert "not found" in summary


def test_llmaagent_enforce_conditions_gemini_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    agent = LLMAgent(model="gemini-2.5-pro")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation
    # Simulate chain returning without finish_run
    mock_conversation.chain.return_value = iter([])

    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        actions, summary, usage = agent.enforce_conditions(["cond A"])
    assert mock_model.key == "test-key-123"


def test_llmaagent_enforce_conditions_mimo_key(monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "mimo-key-456")
    agent = LLMAgent(model="mimo-v2.5", base_url="http://localhost:9001/v1")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation
    mock_conversation.chain.return_value = iter([])

    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        actions, summary, usage = agent.enforce_conditions(["cond A"])
    assert mock_model.key == "mimo-key-456"
    assert mock_model.api_base == "http://localhost:9001/v1"


def test_llmaagent_enforce_conditions_finish_run():
    agent = LLMAgent(model="test-model")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation

    def fake_chain(prompt, system=None, tools=None, chain_limit=100):
        # Simulate finish_run being called
        raise RunFinishedException(False, "nothing to do")

    mock_conversation.chain.side_effect = fake_chain

    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        actions, summary, usage = agent.enforce_conditions(["cond A"])
    assert actions is False
    assert summary == "nothing to do"


def test_llmaagent_enforce_conditions_exception():
    agent = LLMAgent(model="test-model")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation
    mock_conversation.chain.side_effect = RuntimeError("API error")

    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        actions, summary, usage = agent.enforce_conditions(["cond A"])
    assert actions is True
    assert "API error" in summary
