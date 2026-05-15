"""Runner — orchestrates the clerk/bureaucrat workflow.

The runner coordinates the cycle:
  1. Clerk makes changes
  2. Bureaucrat validates
  3. Merge on pass (git mode), retry on failure
"""

import logging
import os
import re
import subprocess
from typing import Optional

from nopz.bureaucrat import Bureaucrat
from nopz.clerk import Clerk
from nopz.regulations import Regulation, RegulationResult

logger = logging.getLogger(__name__)


def _git(*args: str) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


_TRANSIENT_PATTERNS = [
    re.compile(r"\b40[08]\b"),  # 400 Bad Request, 408 Timeout
    re.compile(r"\b429\b"),  # Rate limit
    re.compile(r"\b50[0-4]\b"),  # 500, 502, 503, 504
    re.compile(r"connection.*(?:closed|reset|refused|timeout|prematurely)", re.IGNORECASE),
    re.compile(r"timed?\s*out", re.IGNORECASE),
]


def _is_transient_error(summary: str) -> bool:
    """Check if a clerk error summary indicates a transient/retryable failure."""
    return any(p.search(summary) for p in _TRANSIENT_PATTERNS)


class Runner:
    """Orchestrates the clerk/bureaucrat loop."""

    def __init__(
        self,
        clerk: Clerk,
        bureaucrat: Bureaucrat,
        regulations: list[Regulation],
        max_iterations: int = 10,
        branch_prefix: str = "nopz/",
        use_git: bool = True,
        stuck_limit: int = 2,
    ):
        self.clerk = clerk
        self.bureaucrat = bureaucrat
        self.regulations = regulations
        self.max_iterations = max_iterations
        self.branch_prefix = branch_prefix
        self.use_git = use_git
        self.stuck_limit = stuck_limit

    def run(self) -> bool:
        """Run the clerk/bureaucrat loop.

        Returns:
            True if all regulations passed, False if max iterations reached.
        """
        if not self.regulations:
            logger.warning("No regulations provided. Nothing to do.")
            return True

        logger.info(f"Starting NOPZ run with {len(self.regulations)} regulations.")

        original_branch = None
        if self.use_git:
            _git("rev-parse", "--is-inside-work-tree")
            original_branch = _git("branch", "--show-current")
            if not original_branch:
                original_branch = "main"

        timeline: list[str] = []
        total_usage = {"input": 0, "output": 0}
        failure_context: Optional[list[RegulationResult]] = None

        # Create a shadow pyproject.toml so tools like pytest don't walk up
        # to a parent project's config and run the wrong test suite.
        created_shadow = False
        if not os.path.exists("pyproject.toml"):
            with open("pyproject.toml", "w") as f:
                f.write('[project]\nname = "nopz-output"\nversion = "0.0.0"\n')
            created_shadow = True
            logger.debug("Created shadow pyproject.toml to isolate tool config.")
        previous_failed: Optional[set[str]] = None
        consecutive_stuck = 0

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"--- Iteration {iteration}/{self.max_iterations} ---")

            if self.use_git:
                branch_name = f"{self.branch_prefix}{iteration}"
                _git("checkout", "-B", branch_name, original_branch)

            try:
                # Clerk makes changes
                summary, usage = self.clerk.work(self.regulations, failure_context)
                timeline.append(f"Iteration {iteration} (clerk): {summary}")
                total_usage["input"] += usage.get("input", 0)
                total_usage["output"] += usage.get("output", 0)

                # Recoverable clerk errors: chain limit (partial progress) and
                # transient API/network errors (retryable).
                if summary.startswith("Clerk error:") and "Chain limit" in summary:
                    logger.warning(f"Clerk hit turn limit: {summary}. Validating progress.")
                elif summary.startswith("Clerk error:") and _is_transient_error(summary):
                    logger.warning(f"Clerk hit transient error: {summary}. Retrying next iteration.")
                elif summary.startswith("Clerk error:"):
                    logger.warning(f"Clerk failed: {summary}. Skipping validation.")
                    logger.error("Clerk error is not recoverable. Aborting.")
                    break

                # Commit the clerk's changes (git mode only)
                if self.use_git:
                    _git("add", "-A")
                    result = subprocess.run(
                        ["git", "diff", "--cached", "--quiet"],
                        capture_output=True,
                    )
                    if result.returncode != 0:
                        _git("commit", "-m", f"NOPZ iteration {iteration}: {summary}")
                    else:
                        logger.info("No changes to commit.")

                # Bureaucrat validates
                logger.info("Bureaucrat validating regulations...")
                results = self.bureaucrat.validate_all()

                for r in results:
                    status = "PASS" if r.passed else "FAIL"
                    logger.info(f"  {r.name}: {status} — {r.message}")

                if self.bureaucrat.all_passed(results):
                    if self.use_git:
                        logger.info("All regulations passed. Merging.")
                        _git("checkout", original_branch)
                        _git("merge", "--no-ff", "-m", "NOPZ: all regulations satisfied", branch_name)
                    else:
                        logger.info("All regulations passed.")

                    logger.info("--- Timeline of Activity ---")
                    for entry in timeline:
                        logger.info(entry)
                    logger.info(
                        f"Total Token Usage: Input: {total_usage['input']}, Output: {total_usage['output']}"
                    )
                    logger.info("You are technically correct. The BEST kind of correct.")
                    if created_shadow:
                        os.remove("pyproject.toml")
                    return True

                # Validation failed — record failures for next iteration
                failure_context = self.bureaucrat.failures(results)
                failed_names = [f.name for f in failure_context]
                failed_set = set(failed_names)
                timeline.append(
                    f"Iteration {iteration} (bureaucrat): FAILED — {', '.join(failed_names)}"
                )
                logger.info(f"Validation failed: {', '.join(failed_names)}")

            except Exception as e:
                logger.error(f"Error during iteration {iteration}: {e}")
                timeline.append(f"Iteration {iteration}: ERROR — {e}")
                failed_set = previous_failed  # no change on error

            finally:
                if self.use_git:
                    _git("checkout", original_branch)

            # Detect stuck clerk — same regulations failing repeatedly
            if previous_failed is not None and failed_set == previous_failed:
                consecutive_stuck += 1
            else:
                consecutive_stuck = 0
            previous_failed = failed_set

            if consecutive_stuck >= self.stuck_limit:
                logger.error(
                    f"Clerk stuck: same {len(failed_set)} regulation(s) failing for "
                    f"{consecutive_stuck + 1} consecutive iterations. Aborting."
                )
                timeline.append(
                    f"Iteration {iteration}: STUCK — same regulations failing repeatedly"
                )
                break

        logger.warning(
            f"Reached maximum iterations ({self.max_iterations}) without all regulations passing."
        )
        logger.info("--- Timeline of Activity ---")
        for entry in timeline:
            logger.info(entry)
        logger.info(
            f"Total Token Usage: Input: {total_usage['input']}, Output: {total_usage['output']}"
        )
        if created_shadow:
            os.remove("pyproject.toml")
        return False
