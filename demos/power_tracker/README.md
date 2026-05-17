# Power Tracker - NOPZ Demo

A real-time web application that tracks the 10 most powerful people in the world and streams their simulated activities live.

## What is Power Tracker?

Power Tracker is a web application that:
1. Lists the 10 most powerful people in the world, ranked by influence.
2. Generates simulated activities for them at random intervals.
3. Streams those activities in real-time via Server-Sent Events.

**Backend:** FastAPI + SSE | **Frontend:** Vanilla SPA | **Storage:** In-memory

## NOPZ Regulations

This application is governed by NOPZ regulations — Python functions that validate whether the codebase meets specific requirements. The NOPZ clerk makes changes, and the bureaucrat checks regulations. On success, changes merge automatically. On failure, the clerk retries with failure context.

### Regulation Files

| File | Domain | Regulations |
|------|--------|-------------|
| [`dev_standards.py`](./dev_standards.py) | Development | PEP 8, type hints, test coverage, dependencies |
| [`backend.py`](./backend.py) | Backend | FastAPI, CORS, models, endpoints, SSE, error handling |
| [`data_source.py`](./data_source.py) | Data | Seeding, thread safety, generator, activity cap |
| [`frontend.py`](./frontend.py) | Frontend | SPA, people display, live feed, reconnection |

### Running NOPZ

```bash
# Run all regulations against a target directory
uv run nopz dev_standards.py backend.py data_source.py frontend.py --output ./runs/my_run

# Run a single domain
uv run nopz backend.py --output ./runs/my_run --clerk-model gemini-2.5-pro
```

## Running the Application

After running NOPZ, the generated app will be in your output directory. To run it:

```bash
cd <your-output-dir>/power_tracker
pip install -r requirements.txt
./run.sh
```

The backend starts on port 8000. Open `http://localhost:8000` in your browser.
