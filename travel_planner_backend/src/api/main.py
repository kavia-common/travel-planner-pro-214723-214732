from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.routes.trips import router as trips_router
from src.db.session import get_db

openapi_tags = [
    {"name": "System", "description": "Health checks and system endpoints."},
    {"name": "Trips", "description": "Create, view, update, delete, and list trips."},
]

app = FastAPI(
    title="Travel Planner Backend API",
    description="Backend APIs for trip planning, destinations, itineraries, notes, and reminders.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(trips_router)


@app.get("/", tags=["System"], summary="Health check", description="Basic service liveness check.")
def health_check():
    """Health check endpoint.

    Returns:
        dict: A simple message indicating the service is running.
    """
    return {"message": "Healthy"}


@app.get(
    "/health/db",
    tags=["System"],
    summary="Database connectivity check",
    description="Runs a trivial SELECT 1 against the PostgreSQL database to verify connectivity.",
)
def db_health_check(db: Session = Depends(get_db)):
    """Database connectivity check.

    Args:
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        dict: Connection status.
    """
    db.execute(text("SELECT 1"))
    return {"database": "ok"}
