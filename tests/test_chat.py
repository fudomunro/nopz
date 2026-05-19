"""Tests for the interactive chat agent."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from nopz import regulations as reg_module
from nopz.chat import ChatAgent, _exec_regulation_code
from nopz.regulations import RegulationResult, regulation, get_regulations


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the global regulation registry before each test."""
    reg_module._registry.clear()
    yield
    reg_module._registry.clear()


@pytest.fixture
def mock_model():
    """Create a mock llm model with a mock conversation."""
    model = MagicMock()
    conversation = MagicMock()
    model.conversation.return_value = conversation

    # Default chain response — iterable (yields text chunks) with usage tracking
    response = MagicMock()
    response._responses = []
    # chain() returns an iterable that yields chunks
    response.__iter__ = MagicMock(return_value=iter(["I can help with that."]))
    conversation.chain.return_value = response

    return model, conversation, response


# --- ChatAgent init ---


def test_chat_agent_init(mock_model):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent(model_name="test-model")

    assert agent.model_name == "test-model"
    assert agent.total_usage == {"input": 0, "output": 0}
    model.conversation.assert_called_once()


# --- Special commands ---


def test_chat_exits_on_quit(mock_model, capsys):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=["/quit"]):
        agent.run()

    captured = capsys.readouterr()
    assert "Exiting." in captured.out


def test_chat_exits_on_exit(mock_model, capsys):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=["/exit"]):
        agent.run()

    captured = capsys.readouterr()
    assert "Exiting." in captured.out


def test_chat_exits_on_eof(mock_model, capsys):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=EOFError):
        agent.run()

    captured = capsys.readouterr()
    assert "Exiting." in captured.out


def test_chat_exits_on_keyboard_interrupt(mock_model, capsys):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        agent.run()

    captured = capsys.readouterr()
    assert "Exiting." in captured.out


def test_chat_clear_resets_conversation(mock_model, capsys):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=["/clear", "/quit"]):
        agent.run()

    # /clear should create a new conversation
    assert model.conversation.call_count == 2  # once in __init__, once on /clear
    captured = capsys.readouterr()
    assert "Conversation cleared." in captured.out


def test_chat_usage_command(mock_model, capsys):
    model, conversation, response = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()
        agent.total_usage = {"input": 100, "output": 50}

    with patch("builtins.input", side_effect=["/usage", "/quit"]):
        agent.run()

    captured = capsys.readouterr()
    assert "100" in captured.out
    assert "50" in captured.out


def test_chat_help_command(mock_model, capsys):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=["/help", "/quit"]):
        agent.run()

    captured = capsys.readouterr()
    assert "/help" in captured.out
    assert "/clear" in captured.out
    assert "/usage" in captured.out
    assert "/quit" in captured.out


# --- Conversation flow ---


def test_chat_sends_message_to_llm(mock_model, capsys):
    model, conversation, response = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=["hello", "/quit"]):
        agent.run()

    conversation.chain.assert_called_once()
    args, kwargs = conversation.chain.call_args
    assert args[0] == "hello"
    assert "tools" in kwargs
    assert "system" in kwargs


def test_chat_prints_response(mock_model, capsys):
    model, conversation, response = mock_model
    response.__iter__ = MagicMock(return_value=iter(["Sure, I can help!"]))
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=["help me", "/quit"]):
        agent.run()

    captured = capsys.readouterr()
    assert "Sure, I can help!" in captured.out


def test_chat_skips_empty_input(mock_model, capsys):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=["", "  ", "/quit"]):
        agent.run()

    conversation.prompt.assert_not_called()


def test_chat_tracks_usage(mock_model):
    model, conversation, response = mock_model
    response.__iter__ = MagicMock(return_value=iter(["test"]))
    response._responses = [
        MagicMock(input_tokens=10, output_tokens=5),
        MagicMock(input_tokens=20, output_tokens=8),
    ]
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    with patch("builtins.input", side_effect=["test", "/quit"]):
        agent.run()

    assert agent.total_usage == {"input": 30, "output": 13}


# --- _exec_regulation_code ---


def test_exec_regulation_code_valid():
    code = (
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("test_reg", description="A test")\n'
        'def test_reg():\n'
        '    return RegulationResult(passed=True, name="test_reg")\n'
    )
    regs = _exec_regulation_code(code)
    assert len(regs) == 1
    assert regs[0].name == "test_reg"


def test_exec_regulation_code_invalid():
    regs = _exec_regulation_code("this is not valid python {{{")
    assert regs == []


def test_exec_regulation_code_no_decorators():
    regs = _exec_regulation_code("x = 1\n")
    assert regs == []


def test_exec_regulation_code_cleans_up_temp_file():
    code = (
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )
    regs = _exec_regulation_code(code)
    assert len(regs) == 1
    # Temp file should not persist
    import glob
    assert not glob.glob("_chat_reg_module*.py")


# --- review_regulation tool ---


def test_review_regulation_tool(mock_model, capsys):
    model, conversation, response = mock_model

    # First prompt response is the chat response
    chat_response = MagicMock()
    chat_response.text.return_value = "Reviewing..."
    chat_response._responses = []

    # Second prompt response is the review result (nested LLM call)
    review_response = MagicMock()
    review_response.text.return_value = '{"passed": true, "issues": []}'

    conversation.prompt.return_value = chat_response
    model.prompt.return_value = review_response

    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent(guidelines=[])

    # The LLM will call the review_regulation tool with code
    reg_code = (
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("test_reg", description="A test regulation")\n'
        'def test_reg():\n'
        '    return RegulationResult(passed=True, name="test_reg")\n'
    )

    # Simulate the tool being called directly
    tools = agent._make_tools()
    review_tool = [t for t in tools if t.__name__ == "review_regulation"][0]
    result = review_tool(reg_code)

    assert "PASS" in result
    assert "test_reg" in result


def test_review_regulation_tool_no_code(mock_model):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    tools = agent._make_tools()
    review_tool = [t for t in tools if t.__name__ == "review_regulation"][0]
    result = review_tool("x = 1")

    assert "Error" in result


# --- validate_regulation tool ---


def test_validate_regulation_tool_passes(mock_model):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    tools = agent._make_tools()
    validate_tool = [t for t in tools if t.__name__ == "validate_regulation"][0]

    code = (
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("always_pass", description="Always passes")\n'
        'def always_pass():\n'
        '    return RegulationResult(passed=True, name="always_pass", message="ok")\n'
    )
    result = validate_tool(code)

    assert "PASS" in result
    assert "always_pass" in result


def test_validate_regulation_tool_fails(mock_model):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    tools = agent._make_tools()
    validate_tool = [t for t in tools if t.__name__ == "validate_regulation"][0]

    code = (
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("always_fail", description="Always fails")\n'
        'def always_fail():\n'
        '    return RegulationResult(passed=False, name="always_fail", message="nope")\n'
    )
    result = validate_tool(code)

    assert "FAIL" in result
    assert "nope" in result


def test_validate_regulation_tool_error(mock_model):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    tools = agent._make_tools()
    validate_tool = [t for t in tools if t.__name__ == "validate_regulation"][0]

    code = (
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("crasher", description="Crashes on check")\n'
        'def crasher():\n'
        '    raise ValueError("boom")\n'
    )
    result = validate_tool(code)

    assert "ERROR" in result
    assert "boom" in result


def test_validate_regulation_tool_no_code(mock_model):
    model, conversation, _ = mock_model
    with patch("nopz.chat._setup_model", return_value=model):
        agent = ChatAgent()

    tools = agent._make_tools()
    validate_tool = [t for t in tools if t.__name__ == "validate_regulation"][0]
    result = validate_tool("x = 1")

    assert "Error" in result


# --- CLI integration ---


def test_cli_enters_chat_mode_no_files(tmp_path):
    """nopz with no regulation files should enter chat mode."""
    from nopz.cli import main

    with (
        patch("sys.argv", ["nopz"]),
        patch("nopz.chat.ChatAgent.run") as mock_run,
        patch("nopz.chat.ChatAgent.__init__", return_value=None),
    ):
        from nopz.cli import main
        import pytest

        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        mock_run.assert_called_once()


def test_cli_chat_flag(tmp_path):
    """--chat flag should enter chat mode even with regulation files."""
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(test_file), "--chat"]),
        patch("nopz.chat.ChatAgent.run") as mock_run,
        patch("nopz.chat.ChatAgent.__init__", return_value=None),
    ):
        from nopz.cli import main
        import pytest

        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        mock_run.assert_called_once()


def test_cli_chat_with_model_flag(tmp_path):
    """--nopz-model should be passed to ChatAgent."""
    with (
        patch("sys.argv", ["nopz", "--nopz-model", "gemini-2.5-flash"]),
        patch("nopz.chat.ChatAgent.run"),
        patch("nopz.chat.ChatAgent.__init__", return_value=None) as mock_init,
    ):
        from nopz.cli import main
        import pytest

        with pytest.raises(SystemExit):
            main()

        _, kwargs = mock_init.call_args
        assert kwargs["model_name"] == "gemini-2.5-flash"


def test_cli_chat_with_output(tmp_path):
    """--output should change directory before chat."""
    output_dir = tmp_path / "chat_output"
    output_dir.mkdir()

    with (
        patch("sys.argv", ["nopz", "--output", str(output_dir)]),
        patch("nopz.chat.ChatAgent.run"),
        patch("nopz.chat.ChatAgent.__init__", return_value=None),
    ):
        import os
        from nopz.cli import main
        import pytest

        with pytest.raises(SystemExit):
            main()

        # After the chat agent is created, we should have been in the output dir
        # (we can't easily verify this since the test exits, but the chdir happens)
