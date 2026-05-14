# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NOPZ** (Number One Point Zero) is a Python CLI tool that enforces regulations on a codebase using a two-agent system: a **Clerk** (makes changes) and a **Beaurocrat** (validates). The loop repeats until all regulations pass or the iteration limit is reached. It uses Simon Willison's `llm` library as an abstraction layer, defaulting to Google Gemini models.

> *"You are technically correct, the BEST kind of correct."* – Number 1.0, Futurama

## Tech Stack

- **Language:** Python 3.13+
- **Package manager:** `uv` (with `uv.lock` for reproducible installs)
- **Build system:** `setuptools` via `pyproject.toml`
- **LLM abstraction:** `llm` library + `llm-gemini` plugin + built-in OpenAI plugin (supports Gemini, MiMo, OpenAI, Claude via plugins)
- **CLI framework:** `argparse` (in `cli.py`)
- **Config:** `pyyaml` (used by the `llm` library for model registration)
- **Tests:** `pytest`
- **CI:** GitHub Actions (`.github/workflows/test.yml`)

## Project Structure

```
nopz/
├── pyproject.toml          # Project metadata, dependencies, scripts
├── README.md               # User-facing docs
├── uv.lock                 # Lockfile for uv
├── nopz/                   # Main package
│   ├── __init__.py         # Version (0.1.0)
│   ├── cli.py              # Entry point: argparse CLI, regulation loading
│   ├── runner.py           # Orchestrates the clerk/beaurocrat loop
│   ├── clerk.py            # LLM agent that makes changes to satisfy regulations
│   ├── beaurocrat.py       # Validates regulations against current state
│   ├── agent.py            # Tool definitions (read/write/exec), model registration
│   ├── regulations.py      # Regulation dataclass, @regulation decorator, global registry
│   ├── llm_compat.py       # Patches for llm library compatibility
│   ├── test_llm_chain.py   # LLM chain integration test script (excluded from coverage)
│   └── test_llm_tools.py   # LLM tools integration test script (excluded from coverage)
├── tests/
│   ├── test_cli.py         # Unit tests for CLI and regulation loading
│   ├── test_agent_tools.py # Unit tests for agent tool functions
│   ├── test_beaurocrat.py  # Unit tests for the beaurocrat
│   ├── test_runner.py      # Unit tests for the runner
│   └── test_clerk.py       # Unit tests for the clerk
├── demos/
│   ├── power_tracker/      # Demo app built by NOPZ (FastAPI backend + SPA frontend)
│   │   ├── README.md
│   │   ├── *.py            # Regulation files for the demo
│   │   └── runs/           # Agent run output
│   └── modal/              # Modal deployment demo
│       ├── modal.py
│       └── README.md
└── .github/workflows/
    └── test.yml            # CI: runs pytest on push to main / PRs
```

## Architecture

### Regulation Loop (`runner.py`)
- `Runner` orchestrates the clerk/beaurocrat cycle: Clerk makes changes, Beaurocrat validates, merge on pass (git mode) or retry on failure.
- Failure context is carried between iterations so the Clerk knows what to fix.
- Loop terminates when all regulations pass or max iterations / stuck limit is reached.

### Clerk (`clerk.py`)
- LLM agent that makes changes to the codebase to satisfy regulations.
- Uses tool calling (`read_file`, `write_file`, `list_directory`, `execute_shell_command`) via the `llm` library's `conversation().chain()`.
- Turn-limited (`--clerk-turns`, default 30) to prevent runaway agents.

### Beaurocrat (`beaurocrat.py`)
- Validates whether the codebase satisfies all regulations via deterministic `check()` functions.
- Optionally supports LLM-based validation for subjective regulations.
- Provides failure context back to the runner for the next iteration.

### Regulations (`regulations.py`)
- Regulations are Python functions decorated with `@regulation` that return `RegulationResult(passed=..., name=..., message=...)`.
- Each regulation file is a standalone Python module imported dynamically by the CLI.

### Tool Functions (`agent.py`)
- `read_file`, `write_file`, `list_directory`, `execute_shell_command` are used by the Clerk.
- `_register_extra_model` handles custom OpenAI-compatible model registration for the `llm` library.

### CLI (`cli.py`)
- Entry point: `nopz.cli:main` (registered as `nopz` script in pyproject.toml)
- Loads regulations from Python files via `load_regulations()` (dynamic import + `@regulation` decorator registry).
- Supports `--clerk-model`, `--beaurocrat-model`, `--clerk-turns`, `--max-iterations`, `--stuck-limit`, `--output`, `--debug`, `--list-models`, `--mimo-server`, `--log-file`, `--no-git` flags.

## Commands

```bash
# Install (in dev mode)
uv pip install -e .[dev]

# Run the tool (regulation files are Python modules with @regulation decorators)
uv run nopz regulations.py
uv run nopz regulations1.py regulations2.py  # multiple files
uv run nopz backend.py --output ./runs/my_run --clerk-model gemini-2.5-pro

# Run with MiMo (requires a running MiMo API server)
uv run nopz regulations.py --clerk-model mimo-v2-flash --mimo-server http://localhost:9001/v1

# Run tests
uv run pytest
uv run pytest tests/test_cli.py
uv run pytest -v

# List available models
uv run nopz --list-models
```

## Environment Variables

- `GOOGLE_API_KEY` or `GEMINI_API_KEY` — required for Gemini models
- `MIMO_API_KEY` — optional, for MiMo servers that require authentication
- `OPENAI_API_KEY` — set automatically from `MIMO_API_KEY` when using MiMo models

## Key Design Decisions

- **Separated validation and action:** The Clerk (makes changes) and Beaurocrat (validates) are independent agents with different responsibilities. This prevents the agent from self-validating.
- **Deterministic regulation checks:** Regulations define Python `check()` functions that run deterministically, not relying on LLM judgment for pass/fail.
- **Failure context carries forward:** Failed regulation results are passed to the next Clerk iteration so it knows exactly what to fix.
- **Git branch management:** Each iteration works on a branch (`nopz/N`). On success, changes are merged back. Disabled with `--no-git`.
- **Stuck detection:** Aborts if the same regulations fail for `--stuck-limit` consecutive iterations (default 2).
- **Output directory:** `--output` changes CWD, so all agent file operations happen within that directory.

## Conventions

- Follow PEP 8 style.
- Use type hints for all function signatures.
- Use `logging` module (not `print`) in library code; `print` only in test/demo scripts.
- Demo run outputs go in `demos/*/runs/` (gitignored).

## CI/CD

GitHub Actions workflow (`.github/workflows/test.yml`):
- Triggers on push to `main` and all PRs.
- Uses `uv` for dependency management, Python 3.13.
- Runs `uv run pytest`.

## Current Status

Early-stage (v0.1.0). Core clerk/beaurocrat loop and CLI are functional. Two demo apps exist (power_tracker, modal).
