import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

from nopz.agent import LLMAgent
from nopz.runner import Runner

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class AgentAdapter:
    """Adapts the Agent interface to the Runner's expected Protocol."""

    def __init__(self, agent):
        self.agent = agent

    def evaluate_and_act(self, conditions: list[str]) -> tuple[bool, str]:
        # Map to the method defined in agent.py
        return self.agent.enforce_conditions(conditions)


def load_conditions(file_path: str) -> list[str]:
    """Loads conditions from a YAML or plain text file."""
    path = Path(file_path)
    if not path.exists():
        logging.error(f"Conditions file not found: {file_path}")
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in [".yaml", ".yml"]:
                data = yaml.safe_load(f)
                if isinstance(data, dict) and "conditions" in data:
                    return data["conditions"]
                elif isinstance(data, list):
                    return [str(item) for item in data]
                else:
                    logging.error(
                        "Invalid YAML format: expected a list or a dict with a 'conditions' key."
                    )
                    sys.exit(1)
            else:
                # Treat as plain text, one condition per line
                return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"Failed to load conditions: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="nopz",
        description="Number One Point Zero (NOPZ) - Enforce conditions via AI agents.",
    )
    parser.add_argument(
        "conditions_files",
        nargs="*",
        help="Path(s) to the file(s) containing the conditions to enforce.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models and exit.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-pro",
        help="Specify the model to use (default: gemini-2.5-pro).",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Directory where agent activity should happen.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of agent loop iterations (default: 10).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_models:
        import llm

        print("Available models:")
        try:
            # llm.get_models() is available in recent llm versions
            for m in llm.get_models():
                print(f"  - {m.model_id}")
        except Exception as e:
            logging.error(f"Failed to list models: {e}")
            sys.exit(1)
        sys.exit(0)

    if not args.conditions_files:
        parser.error("the following arguments are required: conditions_files")

    conditions = []
    for file_path in args.conditions_files:
        conditions.extend(load_conditions(file_path))

    if not conditions:
        logging.warning("No conditions found in the provided file(s).")
        sys.exit(0)

    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(output_dir)

    # Initialize the agent
    raw_agent = LLMAgent(model=args.model)

    # Adapt the agent to match the Runner's expected protocol
    adapted_agent = AgentAdapter(raw_agent)

    # Initialize the runner
    runner = Runner(
        agent=adapted_agent,
        conditions=conditions,
        max_iterations=args.max_iterations,
    )

    try:
        success = runner.run()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
