"""Data source regulations for Power Tracker."""

import os

from nopz.regulations import RegulationResult, regulation


@regulation(
    "seeds_10_people",
    description="Data source seeds exactly 10 profiles of the most powerful people.",
)
def seeds_10_people():
    for path in ["repository.py", "data_store.py", "backend/repository.py", "backend/data_store.py", "app/data.py", "app/store.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                # Check for seeding of 10 people
                if ("seed" in content.lower() or "populate" in content.lower() or "init" in content.lower()) and ("10" in content or "len" in content):
                    return RegulationResult(passed=True, name="seeds_10_people", message="Seeds 10 people found")
    return RegulationResult(passed=False, name="seeds_10_people", message="No seed logic for 10 people found")


@regulation(
    "thread_safe_storage",
    description="Data store must be thread-safe or concurrency-safe.",
)
def thread_safe_storage():
    for path in ["repository.py", "data_store.py", "backend/repository.py", "backend/data_store.py", "app/data.py", "app/store.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "Lock" in content or "lock" in content or "threading" in content or "asyncio" in content:
                    return RegulationResult(passed=True, name="thread_safe_storage", message="Thread-safe storage found")
    return RegulationResult(passed=False, name="thread_safe_storage", message="No thread-safety mechanism found")


@regulation(
    "activity_generator",
    description="Background routine generates Activity events at random intervals (2-8 seconds).",
)
def activity_generator():
    for path in ["generator.py", "backend/generator.py", "app/activity_generator.py", "app/generator.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                has_loop = "while" in content or "async def" in content
                has_interval = "sleep" in content or "interval" in content or "random" in content
                if has_loop and has_interval:
                    return RegulationResult(passed=True, name="activity_generator", message="Activity generator found")
    return RegulationResult(passed=False, name="activity_generator", message="No activity generator found")


@regulation(
    "activity_references_valid_person",
    description="Generated activities must reference valid person_ids.",
)
def activity_references_valid_person():
    for path in ["generator.py", "backend/generator.py", "app/activity_generator.py", "app/generator.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "person" in content.lower() and ("random" in content or "choice" in content or "select" in content):
                    return RegulationResult(passed=True, name="activity_references_valid_person", message="Activities reference valid persons")
    return RegulationResult(passed=False, name="activity_references_valid_person", message="Person reference logic not found")


@regulation(
    "activity_capped_at_100",
    description="Data store caps activity history at 100 entries.",
)
def activity_capped_at_100():
    for path in ["repository.py", "data_store.py", "backend/repository.py", "backend/data_store.py", "app/data.py", "app/store.py"]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "100" in content and ("cap" in content.lower() or "limit" in content.lower() or "max" in content.lower() or "len" in content):
                    return RegulationResult(passed=True, name="activity_capped_at_100", message="Activity cap at 100 found")
    return RegulationResult(passed=False, name="activity_capped_at_100", message="No activity cap logic found")
