from __future__ import annotations

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.routes.destinations import router as destinations_router
from src.api.routes.itinerary import router as itinerary_router
from src.api.routes.notes import router as notes_router
from src.api.routes.reminders import router as reminders_router
from src.api.routes.trips import router as trips_router
from src.db.session import get_db

openapi_tags = [
    {"name": "System", "description": "Health checks and system endpoints."},
    {"name": "Trips", "description": "Create, view, update, delete, and list trips."},
    {"name": "Destinations", "description": "Search and browse destinations."},
    {"name": "Itinerary", "description": "Manage itinerary items linked to trips."},
    {"name": "Notes", "description": "Manage notes linked to trips."},
    {"name": "Reminders", "description": "Manage reminders linked to trips."},
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
app.include_router(destinations_router)
app.include_router(itinerary_router)
app.include_router(notes_router)
app.include_router(reminders_router)


@app.get("/", tags=["System"], summary="Health check", description="Basic service liveness check.")
def health_check():
    """Health check endpoint.

    Returns:
        dict: A simple message indicating the service is running.
    """
    return {"message": "Healthy"}


@app.get(
    "/api/health",
    tags=["System"],
    summary="API health check",
    description="Health endpoint used by the platform readiness probe.",
    operation_id="api_health_check",
)
def api_health_check():
    """API health check endpoint.

    Returns:
        dict: A simple message indicating the API is ready to accept traffic.
    """
    return {"status": "ok"}


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

    Raises:
        fastapi.HTTPException: 503 if database is unreachable.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"database": "ok"}
    except SQLAlchemyError as exc:
        # Important: do not crash the app; report DB as unavailable.
        return {"database": "unavailable", "detail": str(exc)}, status.HTTP_503_SERVICE_UNAVAILABLE
