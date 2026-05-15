"""Tests for the Beaurocrat class."""

import os
from unittest.mock import MagicMock, patch

import pytest

from nopz.agent import _setup_model
from nopz.beaurocrat import Beaurocrat
from nopz.regulations import Regulation, RegulationResult


def _make_regulation(name: str, check_return: RegulationResult | None = None) -> Regulation:
    reg = MagicMock()
    reg.name = name
    reg.description = f"Test: {name}"
    reg.llm_validate = None
    if check_return is None:
        check_return = RegulationResult(passed=True, name=name, message="ok")
    reg.check.return_value = check_return
    return reg


def test_validate_all_passes():
    regs = [_make_regulation("a"), _make_regulation("b")]
    b = Beaurocrat(regulations=regs)
    results = b.validate_all()
    assert len(results) == 2
    assert all(r.passed for r in results)


def test_validate_all_mixed():
    pass_reg = _make_regulation("a")
    fail_reg = _make_regulation("b", RegulationResult(passed=False, name="b", message="nope"))
    b = Beaurocrat(regulations=[pass_reg, fail_reg])
    results = b.validate_all()
    assert len(results) == 2
    assert results[0].passed is True
    assert results[1].passed is False


def test_validate_all_exception_handling():
    good_reg = _make_regulation("a")
    bad_reg = MagicMock()
    bad_reg.name = "bad"
    bad_reg.check.side_effect = RuntimeError("boom")

    b = Beaurocrat(regulations=[good_reg, bad_reg])
    results = b.validate_all()
    assert len(results) == 2
    assert results[0].passed is True
    assert results[1].passed is False
    assert "boom" in results[1].message


def test_all_passed_true():
    results = [
        RegulationResult(passed=True, name="a"),
        RegulationResult(passed=True, name="b"),
    ]
    b = Beaurocrat(regulations=[])
    assert b.all_passed(results) is True


def test_all_passed_false():
    results = [
        RegulationResult(passed=True, name="a"),
        RegulationResult(passed=False, name="b"),
    ]
    b = Beaurocrat(regulations=[])
    assert b.all_passed(results) is False


def test_failures_filters():
    results = [
        RegulationResult(passed=True, name="a"),
        RegulationResult(passed=False, name="b"),
        RegulationResult(passed=False, name="c"),
    ]
    b = Beaurocrat(regulations=[])
    failures = b.failures(results)
    assert len(failures) == 2
    assert [f.name for f in failures] == ["b", "c"]


def test_failures_empty():
    results = [
        RegulationResult(passed=True, name="a"),
    ]
    b = Beaurocrat(regulations=[])
    assert b.failures(results) == []


def test_setup_model_gemini(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    mock_model = MagicMock()
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        result = _setup_model("gemini-2.5-pro")
    assert result.key == "g-key"


def test_setup_model_gemini_no_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    mock_model = MagicMock()
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        result = _setup_model("gemini-2.5-pro")
    assert result == mock_model


def test_setup_model_gemini_fallback_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fallback-key")
    mock_model = MagicMock()
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        result = _setup_model("gemini-2.5-pro")
    assert result.key == "fallback-key"


def test_setup_model_mimo(monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "m-key")
    mock_model = MagicMock()
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        result = _setup_model("mimo-v2.5")
    assert result.key == "m-key"


def test_setup_model_mimo_no_key(monkeypatch):
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    mock_model = MagicMock()
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        result = _setup_model("mimo-v2.5")
    assert result == mock_model


def test_setup_model_mimo_openai_fallback(monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "mimo-fb")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    mock_model = MagicMock()
    with patch("nopz.agent.llm") as mock_llm:
        mock_llm.get_model.return_value = mock_model
        _setup_model("mimo-v2.5")
    assert os.environ.get("OPENAI_API_KEY") == "mimo-fb"


def test_setup_model_with_base_url():
    mock_model = MagicMock()
    with patch("nopz.agent.llm") as mock_llm, \
         patch("nopz.agent._register_extra_model") as mock_reg:
        mock_llm.get_model.return_value = mock_model
        result = _setup_model("custom-model", base_url="http://localhost:8000/v1")
    mock_reg.assert_called_once_with("custom-model")
    assert result.api_base == "http://localhost:8000/v1"


def test_llm_validate_pass():
    reg = MagicMock()
    reg.name = "test_reg"
    reg.description = "A test regulation"
    reg.llm_validate = lambda diff: None  # truthy — has LLM validate

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = "PASS — looks good"
    mock_model.prompt.return_value = mock_response

    b = Beaurocrat(regulations=[], llm_model="gemini-2.5-pro")
    with patch("nopz.beaurocrat._setup_model", return_value=mock_model):
        result = b.llm_validate(reg, "some diff")
    assert result.passed is True
    assert result.name == "test_reg"


def test_llm_validate_fail():
    reg = MagicMock()
    reg.name = "test_reg"
    reg.description = "A test regulation"
    reg.llm_validate = lambda diff: None

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = "FAIL — missing requirement"
    mock_model.prompt.return_value = mock_response

    b = Beaurocrat(regulations=[], llm_model="gemini-2.5-pro")
    with patch("nopz.beaurocrat._setup_model", return_value=mock_model):
        result = b.llm_validate(reg, "some diff")
    assert result.passed is False


def test_llm_validate_no_fn():
    reg = MagicMock()
    reg.name = "test_reg"
    reg.llm_validate = None

    b = Beaurocrat(regulations=[])
    result = b.llm_validate(reg, "diff")
    assert result.passed is True
    assert "No LLM validation" in result.message
