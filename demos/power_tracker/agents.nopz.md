# NOPZ Development Conditions: Power Tracker

The following conditions apply to all development tasks within the `power_tracker` application.

## 1. Code Quality
- All Python code must comply with PEP 8 standards.
- All functions and classes must have descriptive docstrings.
- Ensure type hints are used for all function arguments and return values.

## 2. Dependencies
- Any external dependencies must be recorded in `requirements.txt`.
- Pin dependency versions to ensure reproducible builds.

## 3. Architecture
- The application must be structured modularly (e.g., separating data fetching, processing, and display).
- Use proper logging (`logging` module) instead of plain `print` statements.

## 4. Testing
- Provide basic tests for all business logic and data processing modules.