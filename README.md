# Number One Point Zero (NOPZ)

> *"You are technically correct, the BEST kind of correct."* – Number 1.0, Futurama

**NOPZ** is a CLI tool that enforces regulations on a codebase using a two-agent system. A **Clerk** makes changes to satisfy regulations, and a **Beaurocrat** validates them. The loop repeats until all regulations pass or the iteration limit is reached.

## How it Works

1. **Define Regulations:** Write Python functions decorated with `@regulation` that define conditions a codebase must satisfy.
2. **Clerk Modifies:** NOPZ feeds the regulations to an AI Clerk (powered by the `llm` library, defaulting to Gemini) which uses tools to inspect and modify the codebase.
3. **Beaurocrat Validates:** A Beaurocrat runs deterministic checks on each regulation against the current state.
4. **Loop or Merge:** If all regulations pass, changes are merged (in git mode). If not, failure context is passed to the next Clerk iteration. The loop repeats until success or the iteration limit is reached.

## Current Status

- **Language:** Python
- **Models:** Supports any model available via Simon Willison's `llm` library plugins (defaults to `gemini-2.5-pro`)
- **Interface:** CLI

## Setup

NOPZ uses the `llm` library and defaults to `gemini-2.5-pro`. You must set your API key as an environment variable before running the tool:

    $ export GOOGLE_API_KEY="your_api_key_here"

## Usage

    $ uv run nopz regulations.py

See `CLAUDE.md` for full CLI options and architecture details.

## Roadmap

- Basic CLI scaffold to read a conditions file.
- Iterative agent loop.
- Support for multiple LLMs via the `llm` library ecosystem.
