"""Tests for the Number One Point Zero regulation review module."""

from unittest.mock import MagicMock, patch

import pytest
import yaml

from nopz.number_one import (
    NumberOne,
    ReviewGuideline,
    ReviewResult,
    _build_review_prompt,
    _parse_review_response,
    _regulation_cache_key,
    load_guidelines,
)
from nopz.regulations import Regulation, RegulationResult


# --- load_guidelines ---


def test_load_guidelines_default():
    guidelines = load_guidelines()
    assert len(guidelines) >= 5
    assert all(g.id and g.name and g.description for g in guidelines)


def test_load_guidelines_custom_file(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text(
        yaml.dump(
            {
                "guidelines": [
                    {"id": "test", "name": "Test", "description": "A test guideline"}
                ]
            }
        )
    )
    guidelines = load_guidelines(str(custom))
    assert len(guidelines) == 1
    assert guidelines[0].id == "test"
    assert guidelines[0].name == "Test"


def test_load_guidelines_missing_file():
    with pytest.raises(FileNotFoundError):
        load_guidelines("/nonexistent/guidelines.yaml")


# --- _build_review_prompt ---


def _make_regulation(name="test_reg", description="desc", llm_validate=None):
    def check():
        return RegulationResult(passed=True, name=name)
    reg = MagicMock(spec=Regulation)
    reg.name = name
    reg.description = description
    reg.llm_validate = llm_validate
    reg.check = check
    return reg


def test_build_review_prompt_contains_regulation():
    reg = _make_regulation(name="my_reg", description="does stuff")
    guidelines = [ReviewGuideline(id="g1", name="G1", description="guideline text")]
    prompt = _build_review_prompt(reg, guidelines)
    assert "my_reg" in prompt
    assert "does stuff" in prompt


def test_build_review_prompt_contains_guidelines():
    reg = _make_regulation()
    guidelines = [
        ReviewGuideline(id="g1", name="First", description="first guideline"),
        ReviewGuideline(id="g2", name="Second", description="second guideline"),
    ]
    prompt = _build_review_prompt(reg, guidelines)
    assert "First" in prompt
    assert "first guideline" in prompt
    assert "Second" in prompt
    assert "second guideline" in prompt


def test_build_review_prompt_no_llm_validate():
    reg = _make_regulation(llm_validate=None)
    prompt = _build_review_prompt(reg, [])
    assert "LLM-based validation: No" in prompt


def test_build_review_prompt_with_llm_validate():
    reg = _make_regulation(llm_validate=lambda diff: None)
    prompt = _build_review_prompt(reg, [])
    assert "LLM-based validation: Yes" in prompt
    assert "llm_validate" in prompt


# --- _parse_review_response ---


def test_parse_review_response_valid():
    passed, issues = _parse_review_response('{"passed": true, "issues": []}')
    assert passed is True
    assert issues == []


def test_parse_review_response_failed():
    text = '{"passed": false, "issues": ["too vague", "brittle paths"]}'
    passed, issues = _parse_review_response(text)
    assert passed is False
    assert issues == ["too vague", "brittle paths"]


def test_parse_review_response_code_fences():
    text = '```json\n{"passed": false, "issues": ["bad"]}\n```'
    passed, issues = _parse_review_response(text)
    assert passed is False
    assert issues == ["bad"]


def test_parse_review_response_with_preamble():
    text = 'Here is my review:\n{"passed": true, "issues": []}\nDone.'
    passed, issues = _parse_review_response(text)
    assert passed is True
    assert issues == []


def test_parse_review_response_malformed():
    passed, issues = _parse_review_response("I cannot evaluate this.")
    assert passed is False
    assert len(issues) == 1
    assert "Could not parse" in issues[0]


def test_parse_review_response_issues_not_list():
    text = '{"passed": false, "issues": "single issue as string"}'
    passed, issues = _parse_review_response(text)
    assert passed is False
    assert issues == ["single issue as string"]


# --- NumberOne ---


def test_number_one_review_all_pass():
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    reg = _make_regulation()

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = '{"passed": true, "issues": []}'
    mock_model.prompt.return_value = mock_response

    no = NumberOne(guidelines=guidelines, model_name="test-model")
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        results = no.review([reg])
    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].regulation_name == "test_reg"


def test_number_one_review_failure():
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    reg = _make_regulation()

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = '{"passed": false, "issues": ["too vague"]}'
    mock_model.prompt.return_value = mock_response

    no = NumberOne(guidelines=guidelines, model_name="test-model")
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        results = no.review([reg])
    assert results[0].passed is False
    assert results[0].issues == ["too vague"]


def test_number_one_review_llm_error():
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    reg = _make_regulation()

    mock_model = MagicMock()
    mock_model.prompt.side_effect = RuntimeError("API down")

    no = NumberOne(guidelines=guidelines, model_name="test-model")
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        results = no.review([reg])
    assert results[0].passed is False
    assert "API down" in results[0].issues[0]


def test_number_one_review_multiple_regulations():
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    regs = [_make_regulation(name="a"), _make_regulation(name="b")]

    mock_model = MagicMock()
    pass_resp = MagicMock()
    pass_resp.text.return_value = '{"passed": true, "issues": []}'
    fail_resp = MagicMock()
    fail_resp.text.return_value = '{"passed": false, "issues": ["bad"]}'
    mock_model.prompt.side_effect = [pass_resp, fail_resp]

    no = NumberOne(guidelines=guidelines, model_name="test-model")
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        results = no.review(regs)
    assert len(results) == 2
    assert results[0].passed is True
    assert results[1].passed is False


def test_number_one_all_passed_true():
    no = NumberOne(guidelines=[], model_name="test")
    results = [
        ReviewResult(passed=True, regulation_name="a"),
        ReviewResult(passed=True, regulation_name="b"),
    ]
    assert no.all_passed(results) is True


def test_number_one_all_passed_false():
    no = NumberOne(guidelines=[], model_name="test")
    results = [
        ReviewResult(passed=True, regulation_name="a"),
        ReviewResult(passed=False, regulation_name="b", issues=["bad"]),
    ]
    assert no.all_passed(results) is False


def test_number_one_failures():
    no = NumberOne(guidelines=[], model_name="test")
    results = [
        ReviewResult(passed=True, regulation_name="a"),
        ReviewResult(passed=False, regulation_name="b", issues=["bad"]),
        ReviewResult(passed=False, regulation_name="c", issues=["worse"]),
    ]
    failures = no.failures(results)
    assert len(failures) == 2
    assert [f.regulation_name for f in failures] == ["b", "c"]


# --- Review cache ---


def _make_real_regulation(name="test_reg", description="desc"):
    """Create a real Regulation with a check function (needed for inspect.getsource)."""
    def check():
        return RegulationResult(passed=True, name=name)
    return Regulation(name=name, description=description, check=check)


def test_cache_key_stable():
    """Same regulation + guidelines produce the same cache key."""
    reg = _make_real_regulation()
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    key1 = _regulation_cache_key(reg, guidelines)
    key2 = _regulation_cache_key(reg, guidelines)
    assert key1 == key2


def test_cache_key_changes_on_name():
    reg_a = _make_real_regulation(name="a")
    reg_b = _make_real_regulation(name="b")
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    assert _regulation_cache_key(reg_a, guidelines) != _regulation_cache_key(reg_b, guidelines)


def test_cache_key_changes_on_description():
    reg_a = _make_real_regulation(description="desc A")
    reg_b = _make_real_regulation(description="desc B")
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    assert _regulation_cache_key(reg_a, guidelines) != _regulation_cache_key(reg_b, guidelines)


def test_cache_key_changes_on_guidelines():
    reg = _make_real_regulation()
    gl_a = [ReviewGuideline(id="g1", name="G1", description="alpha")]
    gl_b = [ReviewGuideline(id="g1", name="G1", description="beta")]
    assert _regulation_cache_key(reg, gl_a) != _regulation_cache_key(reg, gl_b)


def test_cache_hit_skips_llm(tmp_path):
    """On cache hit, the LLM should not be called."""
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    reg = _make_real_regulation()

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = '{"passed": true, "issues": []}'
    mock_model.prompt.return_value = mock_response

    cache_dir = str(tmp_path / "cache")

    # First run — LLM called, result cached
    no = NumberOne(guidelines=guidelines, model_name="test", cache_dir=cache_dir)
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        results = no.review([reg])
    assert results[0].passed is True
    assert mock_model.prompt.call_count == 1

    # Second run — cache hit, LLM not called
    no2 = NumberOne(guidelines=guidelines, model_name="test", cache_dir=cache_dir)
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        results2 = no2.review([reg])
    assert results2[0].passed is True
    assert mock_model.prompt.call_count == 1  # still 1, not 2


def test_cache_miss_after_change(tmp_path):
    """When the regulation changes, the cache misses and the LLM is called again."""
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]

    def check_v1():
        return RegulationResult(passed=True, name="reg")

    reg_v1 = Regulation(name="reg", description="v1", check=check_v1)

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = '{"passed": true, "issues": []}'
    mock_model.prompt.return_value = mock_response

    cache_dir = str(tmp_path / "cache")

    # First run
    no = NumberOne(guidelines=guidelines, model_name="test", cache_dir=cache_dir)
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        no.review([reg_v1])
    assert mock_model.prompt.call_count == 1

    # New regulation with different description
    def check_v2():
        return RegulationResult(passed=True, name="reg")

    reg_v2 = Regulation(name="reg", description="v2", check=check_v2)

    no2 = NumberOne(guidelines=guidelines, model_name="test", cache_dir=cache_dir)
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        no2.review([reg_v2])
    assert mock_model.prompt.call_count == 2  # cache miss, LLM called again


def test_no_cache_when_cache_dir_none():
    """When cache_dir is None, no caching occurs."""
    guidelines = [ReviewGuideline(id="g1", name="G1", description="test")]
    reg = _make_real_regulation()

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text.return_value = '{"passed": true, "issues": []}'
    mock_model.prompt.return_value = mock_response

    # Two runs with no cache_dir
    no = NumberOne(guidelines=guidelines, model_name="test", cache_dir=None)
    with patch("nopz.number_one._setup_model", return_value=mock_model):
        no.review([reg])
        no.review([reg])
    assert mock_model.prompt.call_count == 2  # LLM called both times
