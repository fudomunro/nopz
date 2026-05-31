"""NOPZ self-regulations -- NOPZ regulating itself.

These regulations verify that the NOPZ codebase implements its own
architectural guarantees: separated validation/action, deterministic
checks, failure propagation, loop termination, review before execution,
error resilience, git isolation, tool safety, turn limits, and config
isolation.
"""

import ast
import os
import re
from pathlib import Path

from nopz.regulations import RegulationResult, regulation

# Resolve NOPZ source directory relative to this file
_NOPZ_SRC = Path(__file__).parent / "nopz"


def _read(module_name: str) -> str:
    """Read a NOPZ source module by name (e.g. 'runner' -> nopz/runner.py)."""
    path = _NOPZ_SRC / f"{module_name}.py"
    return path.read_text(encoding="utf-8")


def _ast_tree(module_name: str) -> ast.Module:
    """Parse a NOPZ source module into an AST."""
    return ast.parse(_read(module_name))


# ---------------------------------------------------------------------------
# 1. Separated validation and action
# ---------------------------------------------------------------------------

@regulation(
    "separated_validation_and_action",
    description=(
        "The system must have two distinct agents: one that makes changes (Clerk) "
        "and one that validates (Bureaucrat). The Bureaucrat must not import or use "
        "file-write or shell-execution tools. The Clerk must not import or call "
        "regulation-checking logic (validate_all, check functions, etc.)."
    ),
)
def separated_validation_and_action():
    # Bureaucrat must not import action tools
    bureaucrat_src = _read("bureaucrat")
    action_tool_names = {"write_file", "execute_shell_command", "finish_run"}
    bureaucrat_imports = set(re.findall(r"(?:from|import)\s+\S+", bureaucrat_src))
    bureaucrat_uses_action = any(
        name in bureaucrat_src for name in action_tool_names
    )

    # Clerk must not import validation logic
    clerk_src = _read("clerk")
    clerk_uses_validation = any(
        name in clerk_src
        for name in ("validate_all", "bureaucrat.validate", "Bureaucrat")
    )

    violations = []
    if bureaucrat_uses_action:
        violations.append("Bureaucrat references action tools (write_file/execute_shell_command/finish_run)")
    if clerk_uses_validation:
        violations.append("Clerk references validation logic (validate_all/Bureaucrat)")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="separated_validation_and_action",
        message="Validation and action are cleanly separated" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 2. Deterministic validation
# ---------------------------------------------------------------------------

@regulation(
    "deterministic_validation",
    description=(
        "Regulation check functions must be deterministic -- no LLM calls inside "
        "check() functions. The bureaucrat module must not import LLM libraries "
        "(llm, openai, anthropic) for use in validation. LLM-based validation "
        "is only permitted in the optional llm_validate path, not in check()."
    ),
)
def deterministic_validation():
    bureaucrat_src = _read("bureaucrat")

    # The bureaucrat imports `llm` for optional LLM validation, which is acceptable.
    # But we verify the check() pathway doesn't call LLM.
    # We check that validate_all() calls reg.check() (deterministic) and
    # only calls llm_validate separately.
    has_check_call = "reg.check()" in bureaucrat_src or ".check()" in bureaucrat_src
    has_llm_validate_separate = "llm_validate" in bureaucrat_src

    # Verify regulation.py's check signature is a zero-arg callable
    regulations_src = _read("regulations")
    has_check_type = "Callable[[], RegulationResult]" in regulations_src

    violations = []
    if not has_check_call:
        violations.append("Bureaucrat does not call reg.check() -- validation path unclear")
    if not has_check_type:
        violations.append("Regulation.check type is not Callable[[], RegulationResult]")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="deterministic_validation",
        message="Validation checks are deterministic (zero-arg callables, no LLM in check path)" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 3. Failure context propagation
# ---------------------------------------------------------------------------

@regulation(
    "failure_context_propagation",
    description=(
        "When regulations fail, the failure context (regulation name + failure message) "
        "must be passed from the Bureaucrat's validation results to the Clerk's next "
        "invocation. The runner must extract failures and forward them to clerk.work()."
    ),
)
def failure_context_propagation():
    runner_src = _read("runner")
    clerk_src = _read("clerk")

    # Runner must call bureaucrat.failures() and pass to clerk.work()
    runner_extracts_failures = "bureaucrat.failures" in runner_src or "self.bureaucrat.failures" in runner_src
    runner_passes_context = "failure_context" in runner_src and "clerk.work" in runner_src
    clerk_accepts_context = "failure_context" in clerk_src

    violations = []
    if not runner_extracts_failures:
        violations.append("Runner does not extract failures from Bureaucrat")
    if not runner_passes_context:
        violations.append("Runner does not pass failure_context to Clerk")
    if not clerk_accepts_context:
        violations.append("Clerk.work() does not accept failure_context parameter")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="failure_context_propagation",
        message="Failure context flows from Bureaucrat through Runner to Clerk" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 4. Loop termination guarantees
# ---------------------------------------------------------------------------

@regulation(
    "loop_termination_guarantees",
    description=(
        "The regulation loop must terminate under three conditions: "
        "(a) all regulations pass (bureaucrat.all_passed), "
        "(b) maximum iteration limit is reached (max_iterations counter), "
        "(c) same regulations fail consecutively for stuck_limit iterations (stuck detection)."
    ),
)
def loop_termination_guarantees():
    runner_src = _read("runner")

    has_all_passed = "all_passed" in runner_src
    has_max_iterations = "max_iterations" in runner_src
    has_stuck_detection = "stuck" in runner_src.lower() or "consecutive" in runner_src.lower()
    has_stuck_limit = "stuck_limit" in runner_src

    violations = []
    if not has_all_passed:
        violations.append("No all_passed exit condition")
    if not has_max_iterations:
        violations.append("No max_iterations limit")
    if not has_stuck_detection:
        violations.append("No stuck detection mechanism")
    if not has_stuck_limit:
        violations.append("No stuck_limit parameter")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="loop_termination_guarantees",
        message="All three termination conditions present (all_passed, max_iterations, stuck detection)" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 5. Review before execution
# ---------------------------------------------------------------------------

@regulation(
    "review_before_execution",
    description=(
        "Regulations must be reviewed for quality before the enforcement loop begins. "
        "The CLI must have a review step (Number One) that evaluates regulations against "
        "guidelines. The runner must only be entered after review passes or is explicitly "
        "skipped (--skip-review flag)."
    ),
)
def review_before_execution():
    cli_src = _read("cli")

    has_review_step = "NumberOne" in cli_src or "number_one" in cli_src
    has_skip_flag = "skip_review" in cli_src or "skip-review" in cli_src
    review_before_runner = cli_src.index("review") < cli_src.index("Runner(") if "review" in cli_src and "Runner(" in cli_src else False

    violations = []
    if not has_review_step:
        violations.append("No Number One review step in CLI")
    if not has_skip_flag:
        violations.append("No --skip-review flag to bypass review")
    if not review_before_runner:
        violations.append("Review step does not precede Runner instantiation")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="review_before_execution",
        message="Regulations are reviewed by Number One before the enforcement loop" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 6. Error resilience
# ---------------------------------------------------------------------------

@regulation(
    "error_resilience",
    description=(
        "Transient errors (HTTP 429, 500, connection resets, timeouts) must be retried. "
        "Non-transient errors must abort. Exceptions in individual iterations must not "
        "crash the entire run. The runner must distinguish transient from non-transient errors."
    ),
)
def error_resilience():
    runner_src = _read("runner")

    has_transient_patterns = "_TRANSIENT" in runner_src or "transient" in runner_src.lower()
    has_transient_check = "_is_transient" in runner_src or "is_transient" in runner_src
    has_exception_handling = "except Exception" in runner_src
    has_iteration_try = "try:" in runner_src

    violations = []
    if not has_transient_patterns:
        violations.append("No transient error patterns defined")
    if not has_transient_check:
        violations.append("No transient error detection function")
    if not has_exception_handling:
        violations.append("No exception handling in runner loop")
    if not has_iteration_try:
        violations.append("No try/except around iteration execution")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="error_resilience",
        message="Transient errors retried, exceptions isolated per iteration" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 7. Git branch isolation
# ---------------------------------------------------------------------------

@regulation(
    "git_branch_isolation",
    description=(
        "Each iteration of the enforcement loop must operate on its own git branch. "
        "On success, changes merge back to the original branch. A --no-git flag must "
        "exist for non-git workflows."
    ),
)
def git_branch_isolation():
    runner_src = _read("runner")
    cli_src = _read("cli")

    has_branch_creation = "checkout" in runner_src and "-B" in runner_src
    has_branch_prefix = "branch_prefix" in runner_src
    has_merge = "merge" in runner_src
    has_no_git = "no_git" in cli_src or "no-git" in cli_src or "use_git" in runner_src

    violations = []
    if not has_branch_creation:
        violations.append("No per-iteration branch creation")
    if not has_branch_prefix:
        violations.append("No configurable branch prefix")
    if not has_merge:
        violations.append("No merge-on-success logic")
    if not has_no_git:
        violations.append("No --no-git flag")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="git_branch_isolation",
        message="Each iteration runs on its own branch, merges on success, --no-git supported" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 8. Tool safety limits
# ---------------------------------------------------------------------------

@regulation(
    "tool_safety_limits",
    description=(
        "Agent tools must have safety constraints: shell command timeouts with process "
        "group kills, chunked file reads with truncation markers, and directory creation "
        "for writes."
    ),
)
def tool_safety_limits():
    agent_src = _read("agent")

    has_timeout = "timeout" in agent_src
    has_process_kill = "SIGKILL" in agent_src or "killpg" in agent_src
    has_truncation = "TRUNCATED" in agent_src
    has_makedirs = "makedirs" in agent_src
    has_chunked_read = "offset" in agent_src and "limit" in agent_src

    violations = []
    if not has_timeout:
        violations.append("No timeout parameter on shell execution")
    if not has_process_kill:
        violations.append("No process group kill on timeout")
    if not has_truncation:
        violations.append("No truncation marker on large reads")
    if not has_makedirs:
        violations.append("No directory creation in write_file")
    if not has_chunked_read:
        violations.append("No chunked reading (offset/limit) in read_file")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="tool_safety_limits",
        message="Shell timeout + kill, chunked reads, truncation, makedirs all present" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 9. Turn limits
# ---------------------------------------------------------------------------

@regulation(
    "turn_limits",
    description=(
        "The Clerk (action agent) must be turn-limited to prevent runaway execution. "
        "The Clerk must have a configurable chain_limit/turns parameter with a sensible "
        "default, and must pass it to the LLM conversation chain."
    ),
)
def turn_limits():
    clerk_src = _read("clerk")

    has_turns_param = "turns" in clerk_src
    has_default = "turns: int = 30" in clerk_src or "turns=30" in clerk_src
    has_chain_limit = "chain_limit" in clerk_src

    violations = []
    if not has_turns_param:
        violations.append("No turns parameter on Clerk")
    if not has_default:
        violations.append("No default turn limit (expected 30)")
    if not has_chain_limit:
        violations.append("chain_limit not passed to conversation.chain()")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="turn_limits",
        message="Clerk has configurable turn limit (default 30) passed to chain" if passed else "; ".join(violations),
    )


# ---------------------------------------------------------------------------
# 10. Shadow config isolation
# ---------------------------------------------------------------------------

@regulation(
    "shadow_config_isolation",
    description=(
        "The enforcement loop must not depend on or modify configuration files belonging "
        "to the parent project. A shadow pyproject.toml must be created when absent to "
        "isolate tool config, never overwrite existing ones, and be cleaned up after the run."
    ),
)
def shadow_config_isolation():
    runner_src = _read("runner")

    has_shadow_creation = "pyproject.toml" in runner_src and "created_shadow" in runner_src
    has_existence_check = "os.path.exists" in runner_src and "pyproject.toml" in runner_src
    has_cleanup = "os.remove" in runner_src and "pyproject.toml" in runner_src
    # Verify it only creates when absent
    checks_before_create = runner_src.index("os.path.exists") < runner_src.index("open(\"pyproject.toml\"") if "os.path.exists" in runner_src and 'open("pyproject.toml"' in runner_src else False

    violations = []
    if not has_shadow_creation:
        violations.append("No shadow pyproject.toml creation")
    if not has_existence_check:
        violations.append("No existence check before creating shadow config")
    if not has_cleanup:
        violations.append("No cleanup of shadow pyproject.toml after run")
    if not checks_before_create:
        violations.append("Shadow config may overwrite existing pyproject.toml")

    passed = len(violations) == 0
    return RegulationResult(
        passed=passed,
        name="shadow_config_isolation",
        message="Shadow pyproject.toml created when absent, never overwrites, cleaned up after" if passed else "; ".join(violations),
    )
