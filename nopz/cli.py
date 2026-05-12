"""NOPZ CLI — entry point for the NOPZ tool.

Loads regulations from a Python file and runs the clerk/beaurocrat loop.
"""

import argparse
import importlib.util
import logging
import os
import sys
from pathlib import Path

from nopz.beaurocrat import Beaurocrat
from nopz.clerk import Clerk
from nopz.regulations import Regulation, get_regulations
from nopz.runner import Runner

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def load_regulations(file_path: str) -> list[Regulation]:
    """Load regulations from a Python file.

    The file should use the @regulation decorator from nopz.regulations.
    After importing, the decorated functions are collected from the global registry.
    """
    path = Path(file_path)
    if not path.exists():
        logging.error(f"Regulations file not found: {file_path}")
        sys.exit(1)

    # Import the module dynamically
    spec = importlib.util.spec_from_file_location("regulations_module", path)
    if spec is None or spec.loader is None:
        logging.error(f"Could not load module: {file_path}")
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)
    sys.modules["regulations_module"] = module
    spec.loader.exec_module(module)

    # Collect registered regulations
    regulations = get_regulations()
    if not regulations:
        logging.warning(f"No @regulation decorators found in {file_path}")

    return regulations


def main():
    parser = argparse.ArgumentParser(
        prog="nopz",
        description="Number One Point Zero (NOPZ) — enforce regulations via AI agents.",
    )
    parser.add_argument(
        "regulations_files",
        nargs="+",
        help="Path(s) to Python file(s) defining regulations with @regulation.",
    )
    parser.add_argument(
        "--clerk-model",
        type=str,
        default="gemini-2.5-pro",
        help="Model for the clerk (default: gemini-2.5-pro).",
    )
    parser.add_argument(
        "--beaurocrat-model",
        type=str,
        default="gemini-2.5-pro",
        help="Model for the beaurocrat (default: gemini-2.5-pro).",
    )
    parser.add_argument(
        "--clerk-turns",
        type=int,
        default=30,
        help="Max tool-call turns per clerk invocation (default: 30).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum clerk/beaurocrat iterations (default: 10).",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Working directory for the run.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models and exit.",
    )
    parser.add_argument(
        "--mimo-server",
        type=str,
        default=None,
        help="Base URL for MiMo API server.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to logfile. Defaults to {output}/nopz.log when --output is set.",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Set up file logging
    log_file = args.log_file
    if not log_file and args.output:
        log_file = os.path.join(args.output, "nopz.log")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(file_handler)

    if args.list_models:
        import llm
        print("Available models:")
        for m in llm.get_models():
            print(f"  - {m.model_id}")
        sys.exit(0)

    # Load regulations from all files
    regulations = []
    for file_path in args.regulations_files:
        regulations.extend(load_regulations(file_path))
    if not regulations:
        logging.error("No regulations found. Nothing to do.")
        sys.exit(1)

    logging.info(f"Loaded {len(regulations)} regulation(s): {[r.name for r in regulations]}")

    # Change to output directory if specified
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(output_dir)

    # Build components
    clerk = Clerk(
        model=args.clerk_model,
        base_url=args.mimo_server,
        turns=args.clerk_turns,
    )
    beaurocrat = Beaurocrat(
        regulations=regulations,
        llm_model=args.beaurocrat_model,
        base_url=args.mimo_server,
    )
    runner = Runner(
        clerk=clerk,
        beaurocrat=beaurocrat,
        regulations=regulations,
        max_iterations=args.max_iterations,
    )

    try:
        success = runner.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
