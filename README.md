# Number One Point Zero (NOPZ)

> *"You are technically correct, the BEST kind of correct."* – Number 1.0, Futurama

**NOPZ** is a CLI tool that repeatedly runs an AI agent against a predefined set of conditions. It enforces strict compliance by continuously prompting the agent to take action until the agent determines that **no further actions are required** for the conditions to be true.

## How it Works

1. **Define Conditions:** You provide a file containing a list of conditions or rules.
2. **Agent Evaluation:** NOPZ feeds these conditions to an AI agent (powered by the `llm` library, defaulting to Gemini) along with the current state or context.
3. **Action & Loop:** The agent attempts to satisfy the conditions. NOPZ then re-evaluates the state.
4. **Termination:** The tool only exits successfully when a run of the agent requires zero actions to ensure all conditions are met.

## Current Status

- **Language:** Python
- **Models:** Supports any model available via Simon Willison's `llm` library plugins (defaults to `gemini-2.5-pro`)
- **Interface:** CLI

## Setup

NOPZ uses the `llm` library and defaults to `gemini-2.5-pro`. You must set your API key as an environment variable before running the tool:

    $ export GOOGLE_API_KEY="your_api_key_here"

## Usage

    $ uv run nopz conditions.txt

## Roadmap

- Basic CLI scaffold to read a conditions file.
- Iterative agent loop.
- Support for multiple LLMs via the `llm` library ecosystem.