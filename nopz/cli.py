"""NOPZ CLI — entry point for the NOPZ tool.

Loads regulations from a Python file and runs the clerk/bureaucrat loop.
"""

import argparse
import importlib.util
import logging
import os
import sys
from pathlib import Path

from nopz.bureaucrat import Bureaucrat
from nopz.chat import ChatAgent
from nopz.clerk import Clerk
from nopz.llm_compat import patch_reasoning_content
from nopz.number_one import NumberOne, load_guidelines
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
        nargs="*",
        help="Path(s) to Python file(s) defining regulations with @regulation. "
        "If omitted, enters interactive chat mode.",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Enter interactive chat mode with Number One Point Zero.",
    )
    parser.add_argument(
        "--clerk-model",
        type=str,
        default="gemini-2.5-pro",
        help="Model for the clerk (default: gemini-2.5-pro).",
    )
    parser.add_argument(
        "--bureaucrat-model",
        type=str,
        default="gemini-2.5-pro",
        help="Model for the bureaucrat (default: gemini-2.5-pro).",
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
        help="Maximum clerk/bureaucrat iterations (default: 10).",
    )
    parser.add_argument(
        "--stuck-limit",
        type=int,
        default=2,
        help="Abort after N consecutive iterations with identical failures (default: 2).",
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
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Disable git branch management. Files are created directly in the output directory.",
    )
    parser.add_argument(
        "--nopz-model",
        type=str,
        default=None,
        help="Model for regulation review (default: same as --bureaucrat-model).",
    )
    parser.add_argument(
        "--guidelines",
        type=str,
        default=None,
        help="Path to YAML guidelines file for regulation review. Uses built-in defaults if omitted.",
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Skip the Number One Point Zero regulation review step.",
    )
    parser.add_argument(
        "--no-review-cache",
        action="store_true",
        help="Disable caching of Number One regulation review results.",
    )

    args = parser.parse_args()

    # Patch llm library for reasoning_content support (MiMo, etc.)
    patch_reasoning_content()

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

    # --- Chat mode ---
    if not args.regulations_files or args.chat:
        if args.output:
            os.chdir(args.output)

        try:
            guidelines = load_guidelines(args.guidelines)
        except FileNotFoundError as e:
            logging.error(str(e))
            sys.exit(1)

        chat_model = args.nopz_model or args.clerk_model
        chat_agent = ChatAgent(
            model_name=chat_model,
            base_url=args.mimo_server,
            guidelines=guidelines,
            max_turns=args.clerk_turns,
        )
        try:
            chat_agent.run()
        except KeyboardInterrupt:
            logging.info("Interrupted by user.")
        sys.exit(0)

    # Load regulations from all files
    regulations = []
    for file_path in args.regulations_files:
        regulations.extend(load_regulations(file_path))
    if not regulations:
        logging.error("No regulations found. Nothing to do.")
        sys.exit(1)

    logging.info(f"Loaded {len(regulations)} regulation(s): {[r.name for r in regulations]}")

    # --- Number One Point Zero: regulation review ---
    if not args.skip_review:
        nopz_model = args.nopz_model or args.bureaucrat_model
        try:
            guidelines = load_guidelines(args.guidelines)
        except FileNotFoundError as e:
            logging.error(str(e))
            sys.exit(1)

        cache_dir = None if args.no_review_cache else ".nopz"
        number_one = NumberOne(
            guidelines=guidelines,
            model_name=nopz_model,
            base_url=args.mimo_server,
            cache_dir=cache_dir,
        )
        logging.info("Number One Point Zero: reviewing regulations...")
        review_results = number_one.review(regulations)

        if not number_one.all_passed(review_results):
            # Build failure context for chat
            lines = ["Regulation review FAILED. Issues found:\n"]
            for result in number_one.failures(review_results):
                lines.append(f"  Regulation: {result.regulation_name}")
                for issue in result.issues:
                    lines.append(f"    - {issue}")
                lines.append("")
            lines.append(
                "Fix these regulation issues. The regulation files are:\n"
                + "\n".join(f"  - {f}" for f in args.regulations_files)
            )
            failure_context = "\n".join(lines)

            logging.error(failure_context)

            # Drop into chat to debug
            chat_model = args.nopz_model or args.clerk_model
            chat_agent = ChatAgent(
                model_name=chat_model,
                base_url=args.mimo_server,
                guidelines=guidelines,
                max_turns=args.clerk_turns,
                initial_context=failure_context,
            )
            try:
                chat_agent.run()
            except KeyboardInterrupt:
                logging.info("Interrupted by user.")
            sys.exit(1)

        logging.info("Number One Point Zero: all regulations approved. We kept it gray.")

    # Chdir to output directory so clerk/bureaucrat work there directly
    if args.output:
        os.chdir(args.output)

    # Build components
    clerk = Clerk(
        model=args.clerk_model,
        base_url=args.mimo_server,
        turns=args.clerk_turns,
    )
    bureaucrat = Bureaucrat(
        regulations=regulations,
        llm_model=args.bureaucrat_model,
        base_url=args.mimo_server,
    )
    runner = Runner(
        clerk=clerk,
        bureaucrat=bureaucrat,
        regulations=regulations,
        max_iterations=args.max_iterations,
        use_git=not args.no_git,
        stuck_limit=args.stuck_limit,
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
