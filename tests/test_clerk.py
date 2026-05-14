"""Tests for the Clerk class."""

from unittest.mock import MagicMock, patch

import pytest

from nopz.clerk import Clerk
from nopz.regulations import Regulation, RegulationResult


def _make_reg(name: str) -> Regulation:
    reg = MagicMock()
    reg.name = name
    reg.description = f"Test: {name}"
    return reg


def test_clerk_init_defaults():
    c = Clerk()
    assert c.model_name == "gemini-2.5-pro"
    assert c.turns == 30
    assert c.base_url is None


def test_clerk_init_custom():
    c = Clerk(model="mimo-v2.5", base_url="http://localhost:9001/v1", turns=50)
    assert c.model_name == "mimo-v2.5"
    assert c.base_url == "http://localhost:9001/v1"
    assert c.turns == 50


def test_clerk_unknown_model():
    c = Clerk(model="nonexistent-model")
    with patch("nopz.clerk.llm") as mock_llm:
        mock_llm.UnknownModelError = Exception
        mock_llm.get_model.side_effect = Exception("not found")
        summary, usage = c.work([_make_reg("a")])
    assert "not found" in summary
    assert usage == {}


def test_clerk_gemini_key_injection(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "gem-key")
    c = Clerk(model="gemini-2.5-pro")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation
    mock_conversation.chain.return_value = iter([])

    with patch("nopz.clerk.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        summary, usage = c.work([_make_reg("a")])
    assert mock_model.key == "gem-key"


def test_clerk_mimo_key_injection(monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "mimo-key")
    c = Clerk(model="mimo-v2.5")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation
    mock_conversation.chain.return_value = iter([])

    with patch("nopz.clerk.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        summary, usage = c.work([_make_reg("a")])
    assert mock_model.key == "mimo-key"


def test_clerk_mimo_openai_key_fallback(monkeypatch):
    """When MIMO_API_KEY is set but OPENAI_API_KEY is not, it should copy it."""
    monkeypatch.setenv("MIMO_API_KEY", "mimo-fallback")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = Clerk(model="mimo-v2.5")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation
    mock_conversation.chain.return_value = iter([])

    with patch("nopz.clerk.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        summary, usage = c.work([_make_reg("a")])
    assert os.environ.get("OPENAI_API_KEY") == "mimo-fallback"


def test_clerk_chain_limit_error():
    c = Clerk(model="test-model")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation
    mock_conversation.chain.side_effect = Exception("Chain limit of 30 exceeded.")

    with patch("nopz.clerk.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        summary, usage = c.work([_make_reg("a")])
    assert "Chain limit" in summary
    assert usage == {"input": 0, "output": 0}


def test_clerk_failure_context_in_prompt():
    c = Clerk(model="test-model")
    mock_model = MagicMock()
    mock_conversation = MagicMock()
    mock_model.conversation.return_value = mock_conversation
    mock_conversation.chain.return_value = iter([])

    fail = RegulationResult(passed=False, name="reg_x", message="broken")

    with patch("nopz.clerk.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        summary, usage = c.work([_make_reg("reg_x")], failure_context=[fail])

    # Check that the prompt included failure context
    call_args = mock_conversation.chain.call_args
    prompt = call_args[0][0]
    assert "Previous validation FAILED" in prompt
    assert "reg_x" in prompt
    assert "broken" in prompt


import os
