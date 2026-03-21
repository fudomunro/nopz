import logging
from typing import List, Protocol, Tuple

logger = logging.getLogger(__name__)


class Agent(Protocol):
    """Protocol defining the interface for a NOPZ agent."""

    def evaluate_and_act(self, conditions: List[str]) -> Tuple[bool, str, dict]:
        """
        Independently evaluate the given conditions and take actions if any conditions
        are not met. The agent determines entirely on its own if work was required.

        Args:
            conditions: A list of strings representing the desired state or rules.

        Returns:
            Tuple[bool, str, dict]: A tuple containing:
                - bool: True if the agent had to take an action to satisfy the conditions.
                - str: A summary of the work completed.
                - dict: Token usage information for this run.
        """
        ...


class Runner:
    """
    The core NOPZ runner that repeatedly executes an agent until all conditions
    are satisfied without requiring further action.
    """

    def __init__(
        self,
        agent: Agent,
        conditions: List[str],
        max_iterations: int = 10,
    ):
        """
        Initialize the Runner.

        Args:
            agent: The agent instance to use (e.g., Gemini-based agent).
            conditions: A list of conditions to enforce.
            max_iterations: The maximum number of times to prompt the agent before giving up.
        """
        import logging

        self.logger = logging.getLogger(__name__)
        self.logger.debug(
            "Runner initialized with %d conditions and max_iterations=%d",
            len(conditions),
            max_iterations,
        )
        self.agent = agent
        self.conditions = conditions
        self.max_iterations = max_iterations

    def run(self) -> bool:
        """
        Runs the agent loop.

        Returns:
            bool: True if the run completed successfully (no actions needed),
                  False if the maximum number of iterations was reached.
        """
        if not self.conditions:
            logger.warning("No conditions provided. Nothing to do.")
            return True

        logger.info(f"Starting NOPZ run with {len(self.conditions)} conditions.")

        timeline = []
        total_usage = {"input": 0, "output": 0}

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"--- Iteration {iteration}/{self.max_iterations} ---")

            try:
                action_taken, summary, usage = self.agent.evaluate_and_act(
                    self.conditions
                )
                timeline.append(f"Iteration {iteration}: {summary}")
                total_usage["input"] += usage.get("input", 0)
                total_usage["output"] += usage.get("output", 0)
            except Exception as e:
                logger.error(f"Agent encountered an error: {e}")
                # We can decide whether to abort or retry here. For now, abort.
                raise

            if not action_taken:
                logger.info("No action required by the agent. All conditions are met!")

                logger.info("--- Timeline of Activity ---")
                for entry in timeline:
                    logger.info(entry)

                logger.info(
                    f"Total Token Usage: Input: {total_usage['input']}, Output: {total_usage['output']}"
                )

                logger.info("You are technically correct. The BEST kind of correct.")
                return True

            if iteration < self.max_iterations:
                logger.debug(
                    "Action was taken. Re-evaluating with a completely independent run..."
                )

        logger.warning(
            f"Reached maximum iterations ({self.max_iterations}) without reaching a stable state."
        )
        logger.info("--- Timeline of Activity ---")
        for entry in timeline:
            logger.info(entry)

        logger.info(
            f"Total Token Usage: Input: {total_usage['input']}, Output: {total_usage['output']}"
        )

        return False
