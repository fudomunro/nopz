# Power Tracker - NOPZ Demo

A real-time web application that tracks the 10 most powerful people in the world and streams their simulated activities live.

## What is Power Tracker?

Power Tracker is a web application designed to:
1. List the 10 most powerful people in the world, ranked by their influence.
2. Track and stream their activities in real-time via a live feed.

## NOPZ Regulations

This application is built using NOPZ's regulation-based architecture. Regulations are Python functions that validate whether the codebase meets specific requirements.

### Regulation Files

*   [`dev_standards.py`](./dev_standards.py) — General development standards: PEP 8, type hints, test coverage, dependencies.
*   [`backend.py`](./backend.py) — Backend regulations: FastAPI framework, data models, API endpoints, error handling.
*   [`data_source.py`](./data_source.py) — Data regulations: seeding, storage, mock generation, activity capping.
*   [`frontend.py`](./frontend.py) — Frontend regulations: SPA structure, real-time feed, reconnection handling.

### Running NOPZ

```bash
# Run all regulations
uv run nopz dev_standards.py --output ./runs/my_run

# Run specific domain
uv run nopz backend.py --output ./runs/my_run --clerk-model gemini-2.5-pro
```

The NOPZ clerk will make changes on a branch, and the beaurocrat will validate regulations. On success, changes merge automatically. On failure, the clerk retries with failure context.

## Running the Application

```bash
cd runs/power_tracker_12/power_tracker
pip install -r requirements.txt
./run.sh
```

The backend starts on port 8000. Open `http://localhost:8000` in your browser.
