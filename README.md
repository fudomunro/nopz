# Number One Point Zero (NOPZ)

> *"You are technically correct, the BEST kind of correct."* – Number 1.0, Futurama

**NOPZ** is a CLI tool that repeatedly runs an AI agent against a predefined set of conditions. It enforces strict compliance by continuously prompting the agent to take action until the agent determines that **no further actions are required** for the conditions to be true.

## How it Works

1. **Define Conditions:** You provide a file containing a list of conditions or rules.
2. **Agent Evaluation:** NOPZ feeds these conditions to an AI agent (defaulting to Gemini) along with the current state or context.
3. **Action & Loop:** The agent attempts to satisfy the conditions. NOPZ then re-evaluates the state.
4. **Termination:** The tool only exits successfully when a run of the agent requires zero actions to ensure all conditions are met.

## Current Status

- **Language:** Python
- **Default Agent:** Google Gemini (with plans to support others)
- **Interface:** CLI

## Usage

    $ nopz conditions.txt

## Roadmap

- Basic CLI scaffold to read a conditions file.
- Gemini API integration and iterative agent loop.
- Abstraction layer for supporting other LLM agents.