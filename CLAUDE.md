# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NOPZ** (Number One Point Zero) is a Python CLI tool that repeatedly runs an AI agent against a predefined set of conditions until the agent determines all conditions are satisfied without further action. It uses Simon Willison's `llm` library as an abstraction layer, defaulting to Google Gemini models.

> *"You are technically correct, the BEST kind of correct."* – Number 1.0, Futurama

## Tech Stack

- **Language:** Python 3.13+
- **Package manager:** `uv` (with `uv.lock` for reproducible installs)
- **Build system:** `setuptools` via `pyproject.toml`
- **LLM abstraction:** `llm` library + `llm-gemini` plugin + built-in OpenAI plugin (supports Gemini, MiMo, OpenAI, Claude via plugins)
- **CLI framework:** `click` (declared in deps) / `argparse` (used in cli.py)
- **Config:** `pyyaml` for YAML condition files
- **Tests:** `pytest`
- **CI:** GitHub Actions (`.github/workflows/test.yml`)

## Project Structure

```
nopz/
├── pyproject.toml          # Project metadata, dependencies, scripts
├── README.md               # User-facing docs
├── uv.lock                 # Lockfile for uv
├── example_conditions.yaml # Sample conditions file
├── nopz/                   # Main package
│   ├── __init__.py         # Version (0.1.0)
│   ├── cli.py              # Entry point: argparse CLI, condition loading, adapter
│   ├── runner.py           # Core loop: runs agent repeatedly until no actions needed
│   ├── agent.py            # LLMAgent class, tool definitions (read/write/exec), system prompt
│   ├── test_llm_chain.py   # LLM chain integration test script
│   └── test_llm_tools.py   # LLM tools integration test script
├── tests/
│   └── test_cli.py         # Unit tests for CLI and condition loading
├── demos/
│   └── power_tracker/      # Demo app built by NOPZ agent (FastAPI backend + SPA frontend)
│       ├── README.md
│       ├── *.nopz.md       # Condition files for the demo
│       └── runs/           # Agent run output
└── .github/workflows/
    └── test.yml            # CI: runs pytest on push to main / PRs
```

## Architecture

### Core Loop (`runner.py`)
- `Runner` class implements a simple iterative loop: call agent, check if actions were taken, repeat.
- The agent returns `(action_taken: bool, summary: str, usage: dict)`.
- Loop terminates when `action_taken=False` (all conditions met) or max iterations reached.

### Agent (`agent.py`)
- `LLMAgent` uses `llm` library's `conversation().chain()` for multi-turn tool calling.
- Agent has access to tools: `read_file`, `write_file`, `list_directory`, `execute_shell_command`, `finish_run`.
- `finish_run` raises `RunFinishedException` (inherits `BaseException`) to break out of llm's internal exception handling.
- Agent receives a system prompt instructing it to independently inspect/modify the environment.

### CLI (`cli.py`)
- Entry point: `nopz.cli:main` (registered as `nopz` script in pyproject.toml)
- Loads conditions from YAML (dict with `conditions` key, or plain list) or plain text files.
- `AgentAdapter` bridges `LLMAgent.enforce_conditions()` to `Runner`'s `Agent` protocol (`evaluate_and_act()`).
- Supports `--model`, `--output`, `--max-iterations`, `--debug`, `--list-models`, `--mimo-server` flags.

## Commands

```bash
# Install (in dev mode)
uv pip install -e .[dev]

# Run the tool
uv run nopz conditions.txt
uv run nopz example_conditions.yaml
uv run nopz conditions1.txt conditions2.yaml  # multiple files
uv run nopz demo.nopz.md --output ./runs/my_run --model gemini-2.5-pro

# Run with MiMo (requires a running MiMo API server)
uv run nopz conditions.txt --model mimo-v2-flash --mimo-server http://localhost:9001/v1

# Run tests
uv run pytest
uv run pytest tests/test_cli.py
uv run pytest -v

# List available models
uv run nopz --list-models
```

## Environment Variables

- `GOOGLE_API_KEY` or `GEMINI_API_KEY` — required for Gemini models (injected automatically by `LLMAgent`)
- `MIMO_API_KEY` — optional, for MiMo servers that require authentication

## Key Design Decisions

- **Stateless agent runs:** Each agent invocation is independent — no context is carried between iterations. The agent must re-inspect the environment each time.
- **Agent self-reporting:** No external verification — the agent self-reports whether actions were taken. Trust-based convergence.
- **RunFinishedException as control flow:** Inherits `BaseException` (not `Exception`) to bypass `llm`'s internal exception catching in the chain loop.
- **Output directory:** `--output` changes CWD, so all agent file operations happen within that directory.

## Conventions

- Follow PEP 8 style.
- Use type hints for all function signatures.
- Use `logging` module (not `print`) in library code; `print` only in test/demo scripts.
- All conditions for a NOPZ project go in `.nopz.md` files (markdown with numbered lists).
- Demo run outputs go in `demos/*/runs/` (gitignored).

## CI/CD

GitHub Actions workflow (`.github/workflows/test.yml`):
- Triggers on push to `main` and all PRs.
- Uses `uv` for dependency management, Python 3.13.
- Runs `uv run pytest`.

## Current Status

Early-stage (v0.1.0). Core loop and CLI are functional. One demo app (power_tracker) exists showing NOPZ-driven development of a FastAPI + SPA web app.
