# NOPZ Data Source Conditions: Power Tracker

The following conditions apply to the data ingestion, mock generation, and storage mechanisms for the `power_tracker` application.

## 1. Initial Data Seeding
- The data source must immediately seed exactly 10 profiles representing the "10 most powerful people in the world".
- Each seeded profile must contain a unique identifier, name, title, organization/country, and a unique power rank strictly between 1 and 10 inclusive.

## 2. Storage Mechanism
- Data must be stored in a lightweight, resettable layer (e.g., Python in-memory dictionaries/lists, or an in-memory SQLite database).
- The data store must be thread-safe or concurrency-safe to handle simultaneous reads from the API and writes from the activity generator.

## 3. Mock Activity Generation
- An autonomous background routine or task must generate new `Activity` events to simulate real-time tracking.
- Generated activities must accurately reference a valid, existing `person_id` from the pre-populated top 10 list.
- Activities must include a current ISO-8601 timestamp, a randomized plausible location (e.g., "Washington D.C.", "Geneva", "Beijing"), and a short descriptive string of the action (e.g., "Boarded a flight", "Signed a bilateral agreement").
- The generator must emit new activities at random intervals between 2 and 8 seconds.

## 4. Data Access Interfaces
- The data source must expose clean, decoupled interfaces (e.g., a Repository class) for the backend to query.
- The data store must support a mechanism to limit historical activities (e.g., retaining only the last 100 activities overall) to prevent unbounded memory growth.