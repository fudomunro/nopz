"""Tests for the Runner class."""

from unittest.mock import MagicMock, patch

import pytest

from nopz.bureaucrat import Bureaucrat
from nopz.clerk import Clerk
from nopz.regulations import Regulation, RegulationResult
from nopz.runner import Runner, _is_transient_error


def _make_regulation(name: str) -> Regulation:
    """Create a dummy regulation that always passes."""
    reg = MagicMock()
    reg.name = name
    reg.description = f"Test regulation: {name}"
    reg.check.return_value = RegulationResult(passed=True, name=name, message="ok")
    return reg


def _make_clerk(summary: str = "Clerk completed work.", usage: dict | None = None) -> MagicMock:
    """Create a mock Clerk that returns a fixed summary."""
    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = (summary, usage or {"input": 10, "output": 5})
    return clerk


def _make_bureaucrat(results: list[RegulationResult]) -> MagicMock:
    """Create a mock Bureaucrat with fixed validation results."""
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.return_value = results
    bureaucrat.all_passed.return_value = all(r.passed for r in results)
    bureaucrat.failures.return_value = [r for r in results if not r.passed]
    return bureaucrat


@patch("nopz.runner._git")
def test_empty_regulations_returns_true(mock_git: MagicMock):
    runner = Runner(
        clerk=_make_clerk(),
        bureaucrat=_make_bureaucrat([]),
        regulations=[],
        use_git=False,
    )
    assert runner.run() is True


@patch("nopz.runner._git")
def test_all_pass_returns_true(mock_git: MagicMock):
    regs = [_make_regulation("reg_a"), _make_regulation("reg_b")]
    results = [
        RegulationResult(passed=True, name="reg_a"),
        RegulationResult(passed=True, name="reg_b"),
    ]
    runner = Runner(
        clerk=_make_clerk(),
        bureaucrat=_make_bureaucrat(results),
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )
    assert runner.run() is True


@patch("nopz.runner._git")
def test_max_iterations_returns_false(mock_git: MagicMock):
    regs = [_make_regulation("reg_a")]
    fail_result = RegulationResult(passed=False, name="reg_a", message="not met")
    clerk = _make_clerk()
    bureaucrat = _make_bureaucrat([fail_result])

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=3,
        use_git=False,
    )
    assert runner.run() is False
    assert clerk.work.call_count == 3


@patch("nopz.runner._git")
def test_chain_limit_error_is_recoverable(mock_git: MagicMock):
    """Chain limit errors should continue to validation, not abort."""
    regs = [_make_regulation("reg_a")]
    fail_result = RegulationResult(passed=False, name="reg_a", message="not met")
    pass_result = RegulationResult(passed=True, name="reg_a")

    clerk = MagicMock(spec=Clerk)
    # First call: chain limit error, second call: success
    clerk.work.side_effect = [
        ("Clerk error: Chain limit of 30 exceeded.", {"input": 0, "output": 0}),
        ("Clerk completed work.", {"input": 10, "output": 5}),
    ]
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.side_effect = [
        [fail_result],  # validation after chain limit error
        [pass_result],  # validation after successful clerk work
    ]
    bureaucrat.all_passed.side_effect = [False, True]
    bureaucrat.failures.return_value = [fail_result]

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )
    assert runner.run() is True
    # Clerk was called twice: once for chain limit, once for success
    assert clerk.work.call_count == 2


@patch("nopz.runner._git")
def test_non_chain_limit_clerk_error_aborts(mock_git: MagicMock):
    regs = [_make_regulation("reg_a")]
    clerk = _make_clerk(summary="Clerk error: Model 'bad-model' not found.")
    bureaucrat = _make_bureaucrat([])

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )
    assert runner.run() is False
    # Only called once — aborted immediately
    assert clerk.work.call_count == 1
    # Bureaucrat never validated
    bureaucrat.validate_all.assert_not_called()


def test_is_transient_error_matches_patterns():
    assert _is_transient_error("Clerk error: 400 - Connection prematurely closed")
    assert _is_transient_error("Clerk error: Error code: 502 Bad Gateway")
    assert _is_transient_error("Clerk error: 408 Request Timeout")
    assert _is_transient_error("Clerk error: 429 Too Many Requests")
    assert _is_transient_error("Clerk error: Connection reset by peer")
    assert _is_transient_error("Clerk error: timed out")
    assert not _is_transient_error("Clerk error: Model 'bad' not found.")
    assert not _is_transient_error("Clerk error: Chain limit of 30 exceeded.")
    assert not _is_transient_error("Clerk completed work.")


@patch("nopz.runner._git")
def test_transient_api_error_is_recoverable(mock_git: MagicMock):
    """Transient API errors should retry, not abort."""
    regs = [_make_regulation("reg_a")]
    fail_result = RegulationResult(passed=False, name="reg_a", message="not met")
    pass_result = RegulationResult(passed=True, name="reg_a")

    clerk = MagicMock(spec=Clerk)
    clerk.work.side_effect = [
        ("Clerk error: 400 - Connection prematurely closed BEFORE response", {"input": 0, "output": 0}),
        ("Clerk completed work.", {"input": 10, "output": 5}),
    ]
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.side_effect = [
        [fail_result],  # validation after transient error
        [pass_result],  # validation after successful retry
    ]
    bureaucrat.all_passed.side_effect = [False, True]
    bureaucrat.failures.return_value = [fail_result]

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )
    assert runner.run() is True
    assert clerk.work.call_count == 2


@patch("nopz.runner._git")
def test_non_transient_clerk_error_still_aborts(mock_git: MagicMock):
    """Non-transient errors (e.g. unknown model) should still abort."""
    regs = [_make_regulation("reg_a")]
    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk error: Model 'bad-model' not found.", {"input": 0, "output": 0})
    bureaucrat = _make_bureaucrat([])

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )
    assert runner.run() is False
    assert clerk.work.call_count == 1
    bureaucrat.validate_all.assert_not_called()


@patch("nopz.runner._git")
def test_stuck_detection_aborts_on_same_failures(mock_git: MagicMock):
    """Same failures twice in a row triggers stuck detection (default limit=2)."""
    regs = [_make_regulation("reg_a"), _make_regulation("reg_b")]
    fail_a = RegulationResult(passed=False, name="reg_a", message="fail")
    fail_b = RegulationResult(passed=False, name="reg_b", message="fail")
    pass_b = RegulationResult(passed=True, name="reg_b")

    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk completed work.", {"input": 10, "output": 5})
    bureaucrat = MagicMock(spec=Bureaucrat)
    # Iteration 1: both fail, iteration 2: both fail again → stuck
    fail_results = [fail_a, fail_b]
    bureaucrat.validate_all.side_effect = [fail_results, fail_results]
    bureaucrat.all_passed.return_value = False
    bureaucrat.failures.return_value = [fail_a, fail_b]

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=10,
        use_git=False,
        stuck_limit=2,
    )
    assert runner.run() is False
    # Baseline (iter 1) + 2 consecutive identical failures → aborts on iter 3
    assert clerk.work.call_count == 3


@patch("nopz.runner._git")
def test_stuck_detection_resets_when_failures_change(mock_git: MagicMock):
    """Counter resets when the failure set changes."""
    regs = [_make_regulation("reg_a"), _make_regulation("reg_b")]
    fail_a = RegulationResult(passed=False, name="reg_a", message="fail")
    fail_b = RegulationResult(passed=False, name="reg_b", message="fail")

    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk completed work.", {"input": 10, "output": 5})
    bureaucrat = MagicMock(spec=Bureaucrat)
    # Iteration 1: {a} fails, iteration 2: {b} fails, iteration 3: {a} fails,
    # iteration 4: {b} fails — alternating, never stuck
    bureaucrat.validate_all.side_effect = [
        [fail_a],
        [fail_b],
        [fail_a],
        [fail_b],
    ]
    bureaucrat.all_passed.return_value = False
    bureaucrat.failures.side_effect = [
        [fail_a],
        [fail_b],
        [fail_a],
        [fail_b],
    ]

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=4,
        use_git=False,
        stuck_limit=2,
    )
    assert runner.run() is False
    # All 4 iterations ran — never triggered stuck
    assert clerk.work.call_count == 4


@patch("nopz.runner._git")
def test_stuck_limit_1_aborts_immediately(mock_git: MagicMock):
    """With stuck_limit=1, a single repeated failure triggers abort."""
    regs = [_make_regulation("reg_a")]
    fail_a = RegulationResult(passed=False, name="reg_a", message="fail")

    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk completed work.", {"input": 10, "output": 5})
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.return_value = [fail_a]
    bureaucrat.all_passed.return_value = False
    bureaucrat.failures.return_value = [fail_a]

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=10,
        use_git=False,
        stuck_limit=1,
    )
    assert runner.run() is False
    assert clerk.work.call_count == 2


@patch("nopz.runner._git")
def test_exception_during_iteration_continues(mock_git: MagicMock):
    """An exception in one iteration doesn't kill the whole run."""
    regs = [_make_regulation("reg_a")]
    pass_result = RegulationResult(passed=True, name="reg_a")

    clerk = MagicMock(spec=Clerk)
    clerk.work.side_effect = [
        RuntimeError("transient error"),
        ("Clerk completed work.", {"input": 10, "output": 5}),
    ]
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.return_value = [pass_result]
    bureaucrat.all_passed.return_value = True

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )
    assert runner.run() is True
    assert clerk.work.call_count == 2


@patch("nopz.runner._git")
def test_failure_context_passed_to_clerk(mock_git: MagicMock):
    """Failed regulations from one iteration are passed to the next."""
    regs = [_make_regulation("reg_a")]
    fail_a = RegulationResult(passed=False, name="reg_a", message="fix me")
    pass_a = RegulationResult(passed=True, name="reg_a")

    clerk = MagicMock(spec=Clerk)
    clerk.work.side_effect = [
        ("Clerk completed work.", {"input": 10, "output": 5}),
        ("Clerk completed work.", {"input": 10, "output": 5}),
    ]
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.side_effect = [
        [fail_a],
        [pass_a],
    ]
    bureaucrat.all_passed.side_effect = [False, True]
    bureaucrat.failures.return_value = [fail_a]

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )
    assert runner.run() is True

    # First call: no failure context
    first_call_regs = clerk.work.call_args_list[0]
    assert first_call_regs[0][1] is None  # failure_context

    # Second call: failure context from first iteration
    second_call_regs = clerk.work.call_args_list[1]
    assert second_call_regs[0][1] == [fail_a]


@patch("nopz.runner._git")
def test_usage_accumulated(mock_git: MagicMock):
    """Token usage is accumulated across iterations."""
    regs = [_make_regulation("reg_a")]
    pass_a = RegulationResult(passed=True, name="reg_a")

    clerk = MagicMock(spec=Clerk)
    clerk.work.side_effect = [
        ("Clerk completed work.", {"input": 100, "output": 50}),
        ("Clerk completed work.", {"input": 200, "output": 75}),
    ]
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.side_effect = [
        [RegulationResult(passed=False, name="reg_a", message="nope")],
        [pass_a],
    ]
    bureaucrat.all_passed.side_effect = [False, True]
    bureaucrat.failures.return_value = [RegulationResult(passed=False, name="reg_a")]

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )
    assert runner.run() is True


@patch("nopz.runner._git")
@patch("nopz.runner.subprocess")
def test_git_mode_commits_changes(mock_subprocess: MagicMock, mock_git: MagicMock):
    """In git mode, changes are committed."""
    regs = [_make_regulation("reg_a")]
    pass_a = RegulationResult(passed=True, name="reg_a")

    mock_git.return_value = "main"
    # git diff --cached --quiet returns 1 (changes exist)
    mock_subprocess.run.return_value = MagicMock(returncode=1)

    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk completed work.", {"input": 10, "output": 5})
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.return_value = [pass_a]
    bureaucrat.all_passed.return_value = True

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=True,
    )
    assert runner.run() is True
    # Verify commit was called
    commit_calls = [c for c in mock_git.call_args_list if c[0][0] == "commit"]
    assert len(commit_calls) == 1


@patch("nopz.runner._git")
@patch("nopz.runner.subprocess")
def test_git_mode_no_changes(mock_subprocess: MagicMock, mock_git: MagicMock):
    """In git mode, no commit when no changes."""
    regs = [_make_regulation("reg_a")]
    pass_a = RegulationResult(passed=True, name="reg_a")

    mock_git.return_value = "main"
    # git diff --cached --quiet returns 0 (no changes)
    mock_subprocess.run.return_value = MagicMock(returncode=0)

    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk completed work.", {"input": 10, "output": 5})
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.return_value = [pass_a]
    bureaucrat.all_passed.return_value = True

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=True,
    )
    assert runner.run() is True
    commit_calls = [c for c in mock_git.call_args_list if c[0][0] == "commit"]
    assert len(commit_calls) == 0


@patch("nopz.runner._git")
def test_git_branch_fallback_to_main(mock_git: MagicMock):
    """When git branch returns empty, fallback to main."""
    regs = [_make_regulation("reg_a")]
    pass_a = RegulationResult(passed=True, name="reg_a")

    mock_git.return_value = "main"

    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk completed work.", {"input": 10, "output": 5})
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.return_value = [pass_a]
    bureaucrat.all_passed.return_value = True

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=True,
    )
    assert runner.run() is True


@patch("nopz.runner._git")
def test_shadow_pyproject_created_and_cleaned_up(mock_git: MagicMock, tmp_path):
    """A shadow pyproject.toml is created when none exists and cleaned up after."""
    regs = [_make_regulation("reg_a")]
    pass_a = RegulationResult(passed=True, name="reg_a")

    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk completed work.", {"input": 10, "output": 5})
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.return_value = [pass_a]
    bureaucrat.all_passed.return_value = True

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        assert not (tmp_path / "pyproject.toml").exists()
        assert runner.run() is True
        assert not (tmp_path / "pyproject.toml").exists()
    finally:
        os.chdir(original_cwd)


@patch("nopz.runner._git")
def test_shadow_pyproject_not_overwritten(mock_git: MagicMock, tmp_path):
    """If pyproject.toml already exists, it is not overwritten or removed."""
    regs = [_make_regulation("reg_a")]
    pass_a = RegulationResult(passed=True, name="reg_a")

    clerk = MagicMock(spec=Clerk)
    clerk.work.return_value = ("Clerk completed work.", {"input": 10, "output": 5})
    bureaucrat = MagicMock(spec=Bureaucrat)
    bureaucrat.validate_all.return_value = [pass_a]
    bureaucrat.all_passed.return_value = True

    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regs,
        max_iterations=5,
        use_git=False,
    )

    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "real"\n')
        assert runner.run() is True
        assert (tmp_path / "pyproject.toml").read_text() == '[project]\nname = "real"\n'
    finally:
        os.chdir(original_cwd)
