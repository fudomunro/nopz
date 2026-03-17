# NOPZ Frontend Conditions: Power Tracker Frontend

The following conditions apply specifically to the frontend development of the `power_tracker` application.

## 1. Technology Stack
- The frontend should be a simple Single Page Application (SPA).
- It can be built using plain HTML, CSS, and Vanilla JavaScript to minimize dependencies, or a lightweight framework.
- The main entry point must be an `index.html` file.

## 2. UI/UX Requirements
- The application must feature a clear, responsive layout.
- There must be a section displaying the list of the 10 most powerful people, ordered by their `power_rank`.
- Each person's display entry must show their `name`, `title`, and `country_or_organization`.
- There must be a distinct "Live Activity Feed" section that displays the most recent activities across all tracked individuals.

## 3. Data Integration
- On initial load, the frontend must fetch the top 10 people from the backend's `GET /people` endpoint.
- The frontend must establish a connection to the backend's real-time endpoint (Server-Sent Events or WebSockets) to receive live activity updates.
- When a new activity is received from the real-time stream, it must dynamically appear at the top of the "Live Activity Feed" without requiring a full page refresh.

## 4. State Management & Resilience
- The UI must gracefully handle connection drops to the real-time stream by attempting to reconnect.
- If the backend is unreachable, the frontend must display a user-friendly error message or status indicator (e.g., "Disconnected" or "Attempting to reconnect...").