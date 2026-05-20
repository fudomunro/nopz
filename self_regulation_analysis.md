# NOPZ Self-Regulation Analysis

## Part 1: Regulations Derived from NOPZ's Own Purpose

These regulations encode NOPZ's architectural guarantees and design principles as enforceable checks. If NOPZ were to regulate itself, these would verify that a codebase implements the NOPZ pattern correctly.

### 1. `separated_validation_and_action`
**Description:** The system must have two distinct agents: one that makes changes (Clerk) and one that validates (Bureaucrat). The validator must never modify the codebase, and the changer must never self-validate.
**Check:** Verify that the validation module contains no file-write or shell-execution tools, and the action module contains no regulation-checking logic.

### 2. `deterministic_validation`
**Description:** All regulation check functions must be deterministic -- the same input state must always produce the same pass/fail result. No LLM calls inside check functions.
**Check:** AST-inspect all `check()` functions to verify they contain no imports of LLM libraries (`llm`, `openai`, `anthropic`) and no calls to LLM client objects. Optionally run each check twice on the same state and confirm identical results.

### 3. `failure_context_propagation`
**Description:** When regulations fail, the failure context (regulation name + failure message) must be passed to the next iteration of the action agent.
**Check:** Verify that the runner/loop module passes `RegulationResult` objects (or equivalent failure data) from the validation phase to the action phase's prompt construction.

### 4. `loop_termination_guarantees`
**Description:** The regulation loop must terminate under three conditions: all regulations pass, a maximum iteration limit is reached, or the same regulations fail consecutively for a stuck limit.
**Check:** Verify the loop contains: (a) an `all_passed` exit condition, (b) a `max_iterations` counter that exits, (c) a stuck-detection mechanism that aborts when the same failure set repeats.

### 5. `review_before_execution`
**Description:** Regulations must be reviewed for quality (clear pass/fail, actionable description, single concern, etc.) before the enforcement loop begins.
**Check:** Verify that a review step exists in the pipeline that evaluates regulations against a guidelines document, and that the enforcement loop is only entered after review passes or is explicitly skipped.

### 6. `error_resilience`
**Description:** Transient errors (HTTP 429, 500, connection resets, timeouts) must be retried. Non-transient errors must abort. Exceptions in individual iterations must not crash the entire run.
**Check:** Verify that the runner catches transient HTTP error codes and continues the loop, catches non-transient errors and aborts, and wraps iteration execution in exception handling.

### 7. `git_branch_isolation`
**Description:** Each iteration of the enforcement loop must operate on its own git branch. On success, changes merge back to the original branch.
**Check:** Verify that the runner creates numbered branches (`nopz/N`), commits changes per iteration, and merges on success. Verify a `--no-git` flag exists for non-git workflows.

### 8. `tool_safety_limits`
**Description:** Agent tools must have safety constraints: shell command timeouts, process group kills on timeout, chunked file reads with truncation markers, and directory creation for writes.
**Check:** Verify that `execute_shell_command` has a timeout parameter and kills the process group on expiry. Verify `read_file` supports offset/limit and truncation markers. Verify `write_file` creates parent directories.

### 9. `turn_limits`
**Description:** The action agent must be turn-limited to prevent runaway execution.
**Check:** Verify that the Clerk's chain/conversation has a configurable `chain_limit` or `max_turns` parameter with a sensible default.

### 10. `shadow_config_isolation`
**Description:** The enforcement loop must not depend on or modify configuration files belonging to the parent project. Temporary config (e.g., `pyproject.toml`) must be created when absent and cleaned up after.
**Check:** Verify that the runner creates shadow config files when needed, never overwrites existing ones, and cleans up temporary files after the run.

---

## Part 2: Regulations Derived from the Agent Harness Implementation Guide

These regulations capture best practices from the "Learn Harness Engineering" guide (walkinglabs.github.io). They represent what a well-engineered agent harness *should* have, regardless of whether NOPZ currently implements it.

### A. `phased_architecture`
**Description:** The system must have distinct initialization, execution, and verification phases. Each phase must complete before the next begins.
**Check:** Verify that the codebase has separate modules/functions for initialization (loading context, reviewing regulations), execution (the clerk/bureaucrat loop), and verification (final validation, merge). No phase logic should be interleaved.

### B. `repository_as_system_of_record`
**Description:** The repository (codebase) must be the authoritative source of truth. Agent state, progress, and decisions must not rely solely on conversational context or ephemeral files.
**Check:** Verify that the system reads current state from the filesystem/repository rather than assuming state from prior conversation. Verify that no critical state exists only in memory or conversation history.

### C. `distributed_instructions`
**Description:** Guidance to the agent must be structured and distributed, not concentrated in a single monolithic instruction file.
**Check:** Verify that agent instructions (system prompts, regulation descriptions, guidelines) are split across multiple structured files (e.g., YAML guidelines, per-regulation descriptions, separate prompt templates) rather than a single large prompt string.

### D. `feature_list_as_work_unit`
**Description:** Work must be defined as discrete, atomic feature units (feature lists) rather than vague task descriptions.
**Check:** Verify that regulations are defined as individual, atomic units with clear names and descriptions. Verify that each regulation addresses exactly one concern (aligns with NOPZ's "Single Concern" guideline).

### E. `anti_premature_victory`
**Description:** The system must actively prevent the agent from declaring success too early. Completion must be verified by the validation layer, not self-declared by the action agent.
**Check:** Verify that the action agent cannot bypass the validation phase. Verify that the `finish_run` tool does not count as "success" -- only passing all regulation checks counts as success. Verify that the runner does not accept the Clerk's self-assessment.

### F. `scope_discipline`
**Description:** The agent must be constrained to the defined scope of work. It must not overreach (modify files outside its mandate) or under-finish (leave work incomplete).
**Check:** Verify that the agent's file operations are scoped to the output directory. Verify that regulations cover completeness (not just "does X exist" but "is X complete and functional"). Verify that the Clerk receives failure context for incomplete work.

### G. `observability`
**Description:** The system must provide runtime visibility into what the agent is doing, including logging, token tracking, and iteration progress.
**Check:** Verify that the system logs each iteration's actions, tracks token usage, reports which regulations passed/failed per iteration, and provides a debug mode for verbose output.

### H. `clean_session_state`
**Description:** Every run must leave the system in a clean, resumable state. Temporary files must be cleaned up. Git branches must be properly managed.
**Check:** Verify that the runner cleans up temporary files (shadow configs, stdout/stderr captures) after the run. Verify that git branches are properly merged or abandoned. Verify that no stale state persists between runs.

### I. `end_to_end_verification`
**Description:** The system must verify the complete pipeline, not just individual components. Regulations should test integrated behavior, not just isolated units.
**Check:** Verify that at least some regulations test end-to-end behavior (e.g., "the app starts and responds to a request") rather than just file existence or syntax. Verify that the system supports integration-level checks.

### J. `context_continuity`
**Description:** The system must maintain context across iterations. Failure information, progress, and decisions must persist between loop iterations.
**Check:** Verify that failure context from iteration N is available in iteration N+1. Verify that the system handles long-running tasks without losing track of which regulations still need work.

### K. `agent_behavior_constraints`
**Description:** The agent must be governed by explicit rules and boundaries, not trusted to self-regulate.
**Check:** Verify that the Clerk's system prompt includes explicit constraints (what it can and cannot do). Verify that tools enforce safety limits (timeouts, scope). Verify that the agent cannot modify the regulation definitions or validation logic.

### L. `structured_completion_criteria`
**Description:** Completion must be measured against objective, structured criteria (feature lists, test results), not subjective assessment.
**Check:** Verify that success is defined as "all regulation checks return passed=True" with no ambiguity. Verify that there is no "close enough" or "mostly passing" exit condition.

---

## Part 3: Comparison

### What NOPZ Already Implements Well

| Harness Best Practice | NOPZ Implementation | Coverage |
|---|---|---|
| **Phased Architecture** | Yes -- Number One review (init) -> Clerk/Bureaucrat loop (exec) -> merge (verify) | Strong |
| **Repository as System of Record** | Yes -- the Clerk reads/writes the actual codebase; the Bureaucrat validates the filesystem | Strong |
| **Anti-Premature Victory** | Yes -- the Clerk cannot self-validate; only the Bureaucrat's deterministic checks determine success | Strong |
| **Scope Discipline** | Partial -- the `--output` flag scopes the CWD, but the Clerk can technically write anywhere within it | Moderate |
| **Agent Behavior Constraints** | Yes -- turn limits, tool timeouts, explicit system prompt with regulation list | Strong |
| **Structured Completion Criteria** | Yes -- success = all `check()` functions return `passed=True` | Strong |
| **Clean Session State** | Yes -- shadow pyproject.toml cleanup, git branch management | Strong |
| **Failure Context Continuity** | Yes -- `RegulationResult` objects passed between iterations | Strong |
| **Observability** | Yes -- `--debug` flag, logging, token usage tracking, per-iteration results | Strong |
| **Error Resilience** | Yes -- transient error retry, exception isolation per iteration, stuck detection | Strong |
| **Distributed Instructions** | Partial -- guidelines in YAML, regulations as separate decorated functions, but the Clerk system prompt is a single constructed string | Moderate |
| **Feature List as Work Unit** | Yes -- each regulation is an atomic unit with name, description, and check. The "Single Concern" guideline enforces this. | Strong |

### What NOPZ is Missing or Under-Implements

| Harness Best Practice | Gap | Recommendation |
|---|---|---|
| **End-to-End Verification** | NOPZ regulations can test anything (file existence, syntax, HTTP endpoints), but there is no built-in mechanism for running the target app and testing it end-to-end. The `execute_shell_command` tool enables this, but it's not a first-class pattern. | Add a regulation template or helper that starts the target app, sends requests, and validates responses. Consider a `@e2e_regulation` decorator that handles setup/teardown. |
| **Repository as System of Record (full)** | NOPZ uses the filesystem as truth for regulation checks, but the Clerk's context is ephemeral (conversation history). If the conversation is lost, the Clerk starts fresh with no memory of prior attempts. | Persist a progress file (e.g., `.nopz/progress.json`) that tracks which regulations passed in prior iterations, so a restarted run doesn't repeat work. |
| **Distributed Instructions (full)** | The Clerk receives all regulations in a single system prompt string. For large regulation sets, this could become unwieldy or exceed context limits. | Consider chunking regulations by domain or priority, or providing a regulation index with drill-down. |
| **Scope Discipline (full)** | The Clerk has unrestricted file access within the output directory. There's no mechanism to restrict it to specific files or directories per regulation. | Add optional `scope` metadata to regulations (e.g., `scope=["backend/"]`) that constrains which files the Clerk should modify for that regulation. |
| **Structured Initialization Phase** | NOPZ has Number One review as a pre-step, but there's no formal "context loading" phase where the agent reads the existing codebase structure before acting. The Clerk starts writing immediately. | Add an explicit "survey" phase where the Clerk reads the directory structure and key files before making changes, producing a brief plan. |
| **Observability (external)** | NOPZ logs internally, but there's no external observability (e.g., a dashboard, structured JSON logs, or a progress file that external tools can consume). | Add structured JSON logging alongside human-readable logs, enabling integration with monitoring tools. |

### Summary

NOPZ implements approximately **75-80%** of the Agent Harness best practices natively. Its strongest areas are the core harness loop pattern (separated validation/action, deterministic checks, failure context propagation, stuck detection) and safety mechanisms (turn limits, error resilience, git isolation).

The main gaps are in **end-to-end verification** (NOPZ can do it but doesn't enforce or scaffold it), **full repository-centric state** (the Clerk's context is ephemeral), and **formal initialization/survey phases** (the Clerk jumps straight to action without first understanding the codebase).

Notably, several of NOPZ's existing patterns (Number One review, the `@regulation` decorator system, deterministic `check()` functions) go *beyond* what the Agent Harness guide explicitly prescribes -- NOPZ has a more rigorous validation model than most harnesses, since it enforces deterministic pass/fail rather than relying on LLM judgment.

The most impactful improvements would be:
1. A **survey/initialization phase** where the Clerk reads the codebase before acting
2. **End-to-end test scaffolding** as a first-class regulation pattern
3. **Progress persistence** so interrupted runs can resume
4. **Scope metadata** on regulations to constrain the Clerk's file access
