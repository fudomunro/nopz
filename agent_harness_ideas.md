# Agent Harness Best Practices -- Future Work

Regulations derived from the Agent Harness implementation guide
(walkinglabs.github.io/learn-harness-engineering/en/). These represent
what a well-engineered agent harness *should* have. Not yet implemented
as NOPZ regulations -- saved for future work.

## A. `phased_architecture`
**Description:** The system must have distinct initialization, execution, and verification phases. Each phase must complete before the next begins.
**Check:** Verify that the codebase has separate modules/functions for initialization (loading context, reviewing regulations), execution (the clerk/bureaucrat loop), and verification (final validation, merge). No phase logic should be interleaved.

## B. `repository_as_system_of_record`
**Description:** The repository (codebase) must be the authoritative source of truth. Agent state, progress, and decisions must not rely solely on conversational context or ephemeral files.
**Check:** Verify that the system reads current state from the filesystem/repository rather than assuming state from prior conversation. Verify that no critical state exists only in memory or conversation history.

## C. `distributed_instructions`
**Description:** Guidance to the agent must be structured and distributed, not concentrated in a single monolithic instruction file.
**Check:** Verify that agent instructions (system prompts, regulation descriptions, guidelines) are split across multiple structured files (e.g., YAML guidelines, per-regulation descriptions, separate prompt templates) rather than a single large prompt string.

## D. `feature_list_as_work_unit`
**Description:** Work must be defined as discrete, atomic feature units (feature lists) rather than vague task descriptions.
**Check:** Verify that regulations are defined as individual, atomic units with clear names and descriptions. Verify that each regulation addresses exactly one concern (aligns with NOPZ's "Single Concern" guideline).

## E. `anti_premature_victory`
**Description:** The system must actively prevent the agent from declaring success too early. Completion must be verified by the validation layer, not self-declared by the action agent.
**Check:** Verify that the action agent cannot bypass the validation phase. Verify that the `finish_run` tool does not count as "success" -- only passing all regulation checks counts as success. Verify that the runner does not accept the Clerk's self-assessment.

## F. `scope_discipline`
**Description:** The agent must be constrained to the defined scope of work. It must not overreach (modify files outside its mandate) or under-finish (leave work incomplete).
**Check:** Verify that the agent's file operations are scoped to the output directory. Verify that regulations cover completeness (not just "does X exist" but "is X complete and functional"). Verify that the Clerk receives failure context for incomplete work.

## G. `observability`
**Description:** The system must provide runtime visibility into what the agent is doing, including logging, token tracking, and iteration progress.
**Check:** Verify that the system logs each iteration's actions, tracks token usage, reports which regulations passed/failed per iteration, and provides a debug mode for verbose output.

## H. `clean_session_state`
**Description:** Every run must leave the system in a clean, resumable state. Temporary files must be cleaned up. Git branches must be properly managed.
**Check:** Verify that the runner cleans up temporary files (shadow configs, stdout/stderr captures) after the run. Verify that git branches are properly merged or abandoned. Verify that no stale state persists between runs.

## I. `end_to_end_verification`
**Description:** The system must verify the complete pipeline, not just individual components. Regulations should test integrated behavior, not just isolated units.
**Check:** Verify that at least some regulations test end-to-end behavior (e.g., "the app starts and responds to a request") rather than just file existence or syntax. Verify that the system supports integration-level checks.

## J. `context_continuity`
**Description:** The system must maintain context across iterations. Failure information, progress, and decisions must persist between loop iterations.
**Check:** Verify that failure context from iteration N is available in iteration N+1. Verify that the system handles long-running tasks without losing track of which regulations still need work.

## K. `agent_behavior_constraints`
**Description:** The agent must be governed by explicit rules and boundaries, not trusted to self-regulate.
**Check:** Verify that the Clerk's system prompt includes explicit constraints (what it can and cannot do). Verify that tools enforce safety limits (timeouts, scope). Verify that the agent cannot modify the regulation definitions or validation logic.

## L. `structured_completion_criteria`
**Description:** Completion must be measured against objective, structured criteria (feature lists, test results), not subjective assessment.
**Check:** Verify that success is defined as "all regulation checks return passed=True" with no ambiguity. Verify that there is no "close enough" or "mostly passing" exit condition.

---

## NOPZ Coverage Summary

| Best Practice | NOPZ Status | Gap |
|---|---|---|
| Phased Architecture | Strong | -- |
| Repository as System of Record | Moderate | Clerk context is ephemeral |
| Distributed Instructions | Moderate | Clerk system prompt is one string |
| Feature List as Work Unit | Strong | -- |
| Anti-Premature Victory | Strong | -- |
| Scope Discipline | Moderate | No per-regulation scope constraints |
| Observability | Strong | -- |
| Clean Session State | Strong | -- |
| End-to-End Verification | Weak | Not scaffolded as first-class pattern |
| Context Continuity | Strong | -- |
| Agent Behavior Constraints | Strong | -- |
| Structured Completion Criteria | Strong | -- |

Most impactful future improvements:
1. Survey/initialization phase where the Clerk reads the codebase before acting
2. End-to-end test scaffolding as a first-class regulation pattern
3. Progress persistence so interrupted runs can resume
4. Scope metadata on regulations to constrain Clerk file access
