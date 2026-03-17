# NOPZ Backend Conditions: Power Tracker Backend

The following conditions apply specifically to the backend development of the `power_tracker` application.

## 1. API Framework
- The backend must be built using `FastAPI`.
- The application instance must be initialized in a `main.py` file.
- CORS middleware must be configured to allow requests from the frontend (e.g., `localhost` or `127.0.0.1`).

## 2. Data Models
- Must define Pydantic models for data validation.
- Model `Person`: Must include `id`, `name`, `title` (e.g., "President", "CEO"), `country_or_organization`, and `power_rank` (1-10).
- Model `Activity`: Must include `id`, `person_id`, `timestamp`, `location`, and `description`.

## 3. Core Endpoints
- `GET /people`: Returns the list of the 10 most powerful people, ordered by `power_rank`.
- `GET /people/{person_id}/activities`: Returns a list of recent activities for a specific person.
- `GET /activities/stream`: Provide a Server-Sent Events (SSE) or WebSocket endpoint for real-time activity updates.

## 4. Data Management & Real-Time Tracking
- The system must pre-populate a data store (in-memory list or SQLite) with exactly 10 initial profiles representing the most powerful people.
- The system must include a background task or mock generator that periodically (e.g., every 5-10 seconds) creates new `Activity` records for random individuals in the top 10 list to simulate real-time tracking.

## 5. Error Handling
- Standard HTTP status codes must be used (e.g., 404 if a `person_id` is not found).
- Error responses must include a clear, human-readable message.