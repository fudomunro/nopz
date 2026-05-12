"""Runner — orchestrates the clerk/beaurocrat workflow.

The runner manages git branches and coordinates the cycle:
  1. Create a branch
  2. Clerk makes changes
  3. Beaurocrat validates
  4. Merge on pass, retry on failure
"""

import logging
import subprocess
from typing import Optional

from nopz.beaurocrat import Beaurocrat
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


class Runner:
    """Orchestrates the clerk/beaurocrat loop with git branch management."""

    def __init__(
        self,
        clerk: Clerk,
        beaurocrat: Beaurocrat,
        regulations: list[Regulation],
        max_iterations: int = 10,
        branch_prefix: str = "nopz/",
    ):
        self.clerk = clerk
        self.beaurocrat = beaurocrat
        self.regulations = regulations
        self.max_iterations = max_iterations
        self.branch_prefix = branch_prefix

    def run(self) -> bool:
        """Run the clerk/beaurocrat loop.

        Returns:
            True if all regulations passed, False if max iterations reached.
        """
        if not self.regulations:
            logger.warning("No regulations provided. Nothing to do.")
            return True

        logger.info(f"Starting NOPZ run with {len(self.regulations)} regulations.")

        # Ensure we're in a git repo
        _git("rev-parse", "--is-inside-work-tree")

        # Get the current branch to return to later
        original_branch = _git("branch", "--show-current")
        if not original_branch:
            original_branch = "main"

        timeline: list[str] = []
        total_usage = {"input": 0, "output": 0}
        failure_context: Optional[list[RegulationResult]] = None

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"--- Iteration {iteration}/{self.max_iterations} ---")

            branch_name = f"{self.branch_prefix}{iteration}"

            # Create and checkout the branch (-B force-creates if it already exists)
            _git("checkout", "-B", branch_name, original_branch)

            try:
                # Clerk makes changes
                summary, usage = self.clerk.work(self.regulations, failure_context)
                timeline.append(f"Iteration {iteration} (clerk): {summary}")
                total_usage["input"] += usage.get("input", 0)
                total_usage["output"] += usage.get("output", 0)

                # If clerk failed to do any work, skip this iteration
                if summary.startswith("Clerk error:"):
                    logger.warning(f"Clerk failed: {summary}. Skipping validation.")
                    # Abort if same error repeated (e.g., missing API key)
                    if len(timeline) >= 2 and all(
                        "Clerk error:" in t for t in timeline[-2:]
                    ):
                        logger.error("Clerk failed repeatedly. Aborting.")
                        break
                    continue

                # Commit the clerk's changes
                _git("add", "-A")
                _git("commit", "-m", f"NOPZ iteration {iteration}: {summary}")

                # Beaurocrat validates
                logger.info("Beaurocrat validating regulations...")
                results = self.beaurocrat.validate_all()

                for r in results:
                    status = "PASS" if r.passed else "FAIL"
                    logger.info(f"  {r.name}: {status} — {r.message}")

                if self.beaurocrat.all_passed(results):
                    # Merge into original branch
                    logger.info("All regulations passed. Merging.")
                    _git("checkout", original_branch)
                    _git("merge", "--no-ff", "-m", f"NOPZ: all regulations satisfied", branch_name)

                    logger.info("--- Timeline of Activity ---")
                    for entry in timeline:
                        logger.info(entry)
                    logger.info(
                        f"Total Token Usage: Input: {total_usage['input']}, Output: {total_usage['output']}"
                    )
                    logger.info("You are technically correct. The BEST kind of correct.")
                    return True

                # Validation failed — record failures for next iteration
                failure_context = self.beaurocrat.failures(results)
                failed_names = [f.name for f in failure_context]
                timeline.append(
                    f"Iteration {iteration} (beaurocrat): FAILED — {', '.join(failed_names)}"
                )
                logger.info(f"Validation failed: {', '.join(failed_names)}")

            except Exception as e:
                logger.error(f"Error during iteration {iteration}: {e}")
                timeline.append(f"Iteration {iteration}: ERROR — {e}")

            finally:
                # Return to original branch for the next iteration
                _git("checkout", original_branch)

        logger.warning(
            f"Reached maximum iterations ({self.max_iterations}) without all regulations passing."
        )
        logger.info("--- Timeline of Activity ---")
        for entry in timeline:
            logger.info(entry)
        logger.info(
            f"Total Token Usage: Input: {total_usage['input']}, Output: {total_usage['output']}"
        )
        return False
