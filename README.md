# Number One Point Zero (NOPZ)

> *"You are technically correct, the BEST kind of correct."* – Number 1.0, Futurama

**NOPZ** is a CLI tool that enforces regulations on a codebase using a two-agent system. A **Clerk** makes changes to satisfy regulations, and a **Bureaucrat** validates them. The loop repeats until all regulations pass or the iteration limit is reached.

## How it Works

1. **Define Regulations:** Write Python functions decorated with `@regulation` that define conditions a codebase must satisfy.
2. **Number One Reviews:** Before the loop starts, an LLM reviews your regulations against quality guidelines to catch vague or unenforceable specs early.
3. **Clerk Modifies:** NOPZ feeds the regulations to an AI Clerk which uses tools (read/write files, run commands) to inspect and modify the codebase.
4. **Bureaucrat Validates:** A Bureaucrat runs deterministic `check()` functions on each regulation against the current state.
5. **Loop or Merge:** If all regulations pass, changes are merged (in git mode). If not, failure context is passed to the next Clerk iteration. The loop repeats until success or the iteration limit is reached.

## Installation

Requires Python 3.13+.

```bash
# Install with uv (recommended)
uv pip install -e .

# Or install with pip
pip install -e .

# For development (includes pytest)
uv pip install -e .[dev]
```

## Quick Start

```bash
# Set your API key
export GOOGLE_API_KEY="your_api_key_here"

# Run regulations against the current directory
uv run nopz regulations.py

# Run against a specific output directory
uv run nopz regulations.py --output ./my_project

# Run multiple regulation files
uv run nopz regulations.py backend_rules.py frontend_rules.py
```

## Writing Regulations

Regulations are Python functions decorated with `@regulation`. Each function must return a `RegulationResult`.

```python
from nopz.regulations import regulation, RegulationResult

@regulation(
    "has_readme",
    description="Project must contain a README file with at least 10 lines of content."
)
def has_readme():
    import os
    if not os.path.exists("README.md"):
        return RegulationResult(passed=False, name="has_readme", message="README.md not found")
    with open("README.md") as f:
        lines = f.readlines()
    if len(lines) < 10:
        return RegulationResult(passed=False, name="has_readme", message="README.md has fewer than 10 lines")
    return RegulationResult(passed=True, name="has_readme", message="README.md exists with sufficient content")
```

Key points:
- The `description` field is important — it tells the Clerk what to build and Number One what to review.
- Checks should be **deterministic** (no LLM calls inside `check()`). Use Python's `ast`, `os`, `subprocess`, etc.
- Scope your checks clearly (e.g., "non-test Python files only") so the Clerk doesn't over-apply changes.

See `demos/power_tracker/` for real-world regulation examples covering backend, frontend, data, and dev standards.

## Models

NOPZ supports any model available through Simon Willison's [`llm`](https://github.com/simonw/llm) library. The default is `gemini-2.5-pro`.

### Gemini (default)

```bash
export GOOGLE_API_KEY="your_api_key_here"
uv run nopz regulations.py
```

### Xiaomi MiMo

MiMo models run as OpenAI-compatible API servers. NOPZ connects to them via the `llm` library's OpenAI plugin.

```bash
# If your MiMo server requires authentication
export MIMO_API_KEY="your_api_key_here"

# Run with a MiMo model — pass the server URL via --mimo-server
uv run nopz regulations.py \
    --clerk-model mimo-v2-flash \
    --mimo-server http://localhost:9001/v1

# Use MiMo for both the clerk and bureaucrat
uv run nopz regulations.py \
    --clerk-model mimo-v2-flash \
    --bureaucrat-model mimo-v2-flash \
    --mimo-server http://localhost:9001/v1

# Use MiMo for the clerk, Gemini for the bureaucrat
uv run nopz regulations.py \
    --clerk-model mimo-v2-flash \
    --mimo-server http://localhost:9001/v1
```

NOPZ automatically registers MiMo as an OpenAI-compatible model with tool support and handles the `OPENAI_API_KEY` injection from `MIMO_API_KEY`. MiMo's reasoning (thinking) content is preserved across conversation turns via a compatibility patch.

### Other Models

Any `llm` plugin model works. Install the plugin and pass the model name:

```bash
# Claude via the llm-anthropic plugin
pip install llm-anthropic
uv run nopz regulations.py --clerk-model claude-sonnet-4-20250514

# List all available models
uv run nopz --list-models
```

## Environment Variables

| Variable | Used by | Required |
|----------|---------|----------|
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | Gemini models | Yes, for Gemini |
| `MIMO_API_KEY` | MiMo models | Only if your MiMo server requires auth |
| `OPENAI_API_KEY` | OpenAI models | Set automatically from `MIMO_API_KEY` when using MiMo |

## CLI Reference

```
uv run nopz REGULATIONS_FILE [REGULATIONS_FILE ...] [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--clerk-model` | `gemini-2.5-pro` | Model for the Clerk agent |
| `--bureaucrat-model` | `gemini-2.5-pro` | Model for the Bureaucrat (used for Number One review and optional LLM validation) |
| `--clerk-turns` | `30` | Max tool-call turns per Clerk invocation |
| `--max-iterations` | `10` | Max Clerk/Bureaucrat loop iterations |
| `--stuck-limit` | `2` | Abort after N consecutive iterations with identical failures |
| `--output` | current directory | Working directory for the run (CWD changes to this) |
| `--no-git` | off | Disable git branch management; files are modified directly |
| `--mimo-server` | none | Base URL for a MiMo API server (e.g., `http://localhost:9001/v1`) |
| `--nopz-model` | same as `--bureaucrat-model` | Model for Number One regulation review |
| `--guidelines` | built-in | Path to a custom YAML guidelines file for regulation review |
| `--skip-review` | off | Skip the Number One regulation review step |
| `--no-review-cache` | off | Disable caching of Number One review results |
| `--log-file` | `{output}/nopz.log` (when `--output` set) | Path to log file |
| `--debug` | off | Enable debug logging |
| `--list-models` | — | List available models and exit |

## Number One Point Zero (Regulation Review)

Before the Clerk/Bureaucrat loop runs, NOPZ reviews your regulations against quality guidelines using an LLM. This catches issues like:
- Vague or subjective pass/fail criteria
- Missing scope definitions
- Ambiguous descriptions the Clerk can't reliably satisfy

The review is cached in `.nopz/review_cache.json` so re-runs with unchanged regulations skip the LLM call. Use `--skip-review` to bypass it, or `--no-review-cache` to disable caching.

## Git Mode

By default, NOPZ manages git branches for each iteration (`nopz/1`, `nopz/2`, ...). On success, changes merge back to your original branch. Use `--no-git` to disable this and modify files directly in the output directory.

## Demos

The `demos/` directory contains example regulation sets and NOPZ run outputs:

- **`demos/power_tracker/`** — A FastAPI + SPA app with regulations covering backend architecture, frontend patterns, data handling, and development standards. Includes multiple run outputs showing iterative progress.
- **`demos/modal/`** — Modal deployment demo.

## Roadmap

- Support for multiple LLMs via the `llm` library ecosystem.
- Regulation composition and dependency ordering.
- Streaming progress output.
