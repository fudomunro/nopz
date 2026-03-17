# Power Tracker - NOPZ Demo

Welcome to the **Power Tracker** demo application. This project serves as a trial and demonstration of **NOPZ** (Number One Point Zero), showcasing how an AI agent can be constrained and guided by a strict set of predefined conditions to build a functional application.

## What is Power Tracker?

Power Tracker is a web application designed to:
1. List the 10 most powerful people in the world, ranked by their influence.
2. Track and stream their activities in real-time via a live feed.

## NOPZ Conditions

The development of this application is governed by NOPZ condition files. These files act as the ultimate source of truth and strict requirements for the AI agent building the system. By running NOPZ against these files, the agent is continuously prompted until all conditions are unequivocally met.

The conditions for this project are modularized into the following domains:

*   [`agents.nopz.md`](./agents.nopz.md): General development rules, code quality (PEP 8), testing, and architectural standards.
*   [`backend.nopz.md`](./backend.nopz.md): API framework (FastAPI) requirements, core endpoints, data models, and error handling.
*   [`frontend.nopz.md`](./frontend.nopz.md): UI/UX guidelines, technology stack (SPA), data integration, and real-time live feed constraints.
*   [`data_source.nopz.md`](./data_source.nopz.md): Initial data seeding, in-memory storage, thread-safe data access, and autonomous mock activity generation.

## Next Steps

To build this application, a NOPZ runner should be executed against the `.nopz.md` files in this directory. The agent will iteratively construct the backend, frontend, and data layers until all specified conditions report as `True`.

*(Instructions for running the final application will be populated here once the NOPZ agent completes the implementation.)*