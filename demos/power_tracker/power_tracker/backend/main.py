
import asyncio
import datetime
import logging
import random
import uuid
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Data Models ---

class Person(BaseModel):
    """Represents a powerful individual."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    title: str
    country_or_organization: str
    power_rank: int = Field(..., ge=1, le=10)

class Activity(BaseModel):
    """Represents an activity performed by a person."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    person_id: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    location: str
    description: str
    person_name: str  # Denormalized for frontend convenience

# --- In-Memory Data Store ---

class DataStore:
    """
    A thread-safe in-memory data store for people and activities.
    """
    def __init__(self):
        self._people: Dict[str, Person] = {}
        self._activities: List[Activity] = []
        self._lock = asyncio.Lock()

    async def seed_data(self):
        """Seeds the data store with the 10 most powerful people."""
        async with self._lock:
            if not self._people:  # Seed only if empty
                initial_people = [
                    Person(name="Xi Jinping", title="President", country_or_organization="China", power_rank=1),
                    Person(name="Joe Biden", title="President", country_or_organization="United States", power_rank=2),
                    Person(name="Vladimir Putin", title="President", country_or_organization="Russia", power_rank=3),
                    Person(name="Ursula von der Leyen", title="President", country_or_organization="European Commission", power_rank=4),
                    Person(name="Narendra Modi", title="Prime Minister", country_or_organization="India", power_rank=5),
                    Person(name="Jerome Powell", title="Chair", country_or_organization="U.S. Federal Reserve", power_rank=6),
                    Person(name="Satya Nadella", title="CEO", country_or_organization="Microsoft", power_rank=7),
                    Person(name="Mohammed bin Salman", title="Crown Prince", country_or_organization="Saudi Arabia", power_rank=8),
                    Person(name="Larry Fink", title="CEO", country_or_organization="BlackRock", power_rank=9),
                    Person(name="Jensen Huang", title="CEO", country_or_organization="NVIDIA", power_rank=10),
                ]
                self._people = {p.id: p for p in initial_people}
                logger.info("Data store seeded with initial 10 profiles.")

    async def get_people(self) -> List[Person]:
        """Returns all people, sorted by power rank."""
        async with self._lock:
            return sorted(self._people.values(), key=lambda p: p.power_rank)

    async def get_person_by_id(self, person_id: str) -> Person | None:
        """Retrieves a person by their ID."""
        async with self._lock:
            return self._people.get(person_id)

    async def get_activities_for_person(self, person_id: str) -> List[Activity]:
        """Returns all activities for a specific person."""
        async with self._lock:
            return [act for act in self._activities if act.person_id == person_id]

    async def add_activity(self, activity: Activity):
        """Adds a new activity and keeps the list trimmed."""
        async with self._lock:
            self._activities.insert(0, activity)
            # Keep only the last 100 activities
            self._activities = self._activities[:100]

    async def get_all_activities(self) -> List[Activity]:
        """Returns all activities, most recent first."""
        async with self._lock:
            return self._activities

db = DataStore()
app = FastAPI(title="Power Tracker API")

# --- CORS Middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Background Task: Mock Activity Generator ---

STREAM_DELAY = 1  # seconds
RETRY_TIMEOUT = 15000  # milliseconds
activity_queue = asyncio.Queue()

async def activity_generator():
    """
    An autonomous background routine that generates new Activity events.
    """
    locations = ["Washington D.C.", "Geneva", "Beijing", "Brussels", "Moscow", "New Delhi", "Riyadh", "Taipei"]
    actions = ["Boarded a flight", "Signed a bilateral agreement", "Met with a foreign dignitary", "Gave a public address", "Hosted a state dinner"]

    while True:
        try:
            people = await db.get_people()
            if people:
                random_person = random.choice(people)
                new_activity = Activity(
                    person_id=random_person.id,
                    location=random.choice(locations),
                    description=random.choice(actions),
                    person_name=random_person.name
                )
                await db.add_activity(new_activity)
                await activity_queue.put(new_activity) # Put into queue for SSE
                logger.info(f"Generated activity for {random_person.name}")

            # Generate activities at random intervals between 2 and 8 seconds
            await asyncio.sleep(random.uniform(2, 8))
        except Exception:
            logger.exception("Error in activity generator")
            await asyncio.sleep(10) # Wait before retrying

# --- API Endpoints ---

@app.get("/people", response_model=List[Person])
async def get_most_powerful_people() -> List[Person]:
    """
    Returns the list of the 10 most powerful people, ordered by power_rank.
    """
    return await db.get_people()

@app.get("/people/{person_id}/activities", response_model=List[Activity])
async def get_person_activities(person_id: str) -> List[Activity]:
    """
    Returns a list of recent activities for a specific person.
    """
    person = await db.get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return await db.get_activities_for_person(person_id)

async def activity_stream_generator(request: Request):
    """
    Yields server-sent events for real-time activity updates.
    """
    while True:
        if await request.is_disconnected():
            logger.info("SSE client disconnected.")
            break
        try:
            activity = await activity_queue.get()
            # The SSE spec requires data to be a string
            yield {
                "event": "new_activity",
                "data": activity.model_dump_json()
            }
        except asyncio.CancelledError:
            # This happens when the client disconnects
            break
        except Exception:
            logger.exception("Error in SSE stream")
            # You might want to send an error event to the client
            yield {
                "event": "error",
                "data": "An internal error occurred."
            }
            break


@app.get("/activities/stream")
async def stream_activities(request: Request):
    """
    Provides a Server-Sent Events (SSE) endpoint for real-time activity updates.
    """
    return EventSourceResponse(activity_stream_generator(request))

# --- Lifecycle Events ---

@app.on_event("startup")
async def startup_event():
    """
    On application startup, seed the database and start the background task.
    """
    logger.info("Application starting up...")
    await db.seed_data()
    asyncio.create_task(activity_generator())
    logger.info("Background activity generator started.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
