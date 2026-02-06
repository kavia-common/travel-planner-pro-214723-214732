from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.orm import Session

from src.db.models import Trip
from src.db.session import get_db
from src.schemas.travel import TripCreate, TripRead

router = APIRouter(prefix="/api/trips", tags=["Trips"])


class TripUpdate(BaseModel):
    """Schema for updating a trip.

    Notes:
        We keep this schema local to the router to avoid changing shared schemas in this step.
        All fields are optional; validation mirrors TripCreate/TripBase constraints.
    """

    name: str | None = Field(None, description="Trip name", max_length=200)
    start_date: date | None = Field(None, description="Trip start date")
    end_date: date | None = Field(None, description="Trip end date")

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            raise ValueError("name must not be blank")
        return v


class TripListResponse(BaseModel):
    """Paginated list response for trips."""

    total: int = Field(..., description="Total number of trips available (ignores pagination)")
    limit: int = Field(..., description="Page size limit used for this response", ge=1, le=100)
    offset: int = Field(..., description="Offset used for this response", ge=0)
    items: list[TripRead] = Field(..., description="Trips in the current page")


def _apply_trip_sorting(
    stmt: Select[tuple[Trip]],
    *,
    sort_by: Literal["created_at", "name"] = "created_at",
    sort_dir: Literal["asc", "desc"] = "desc",
) -> Select[tuple[Trip]]:
    """Apply sorting to a Trip select statement."""
    if sort_by == "name":
        col = Trip.name
    else:
        col = Trip.created_at

    order = asc(col) if sort_dir == "asc" else desc(col)
    return stmt.order_by(order)


def _get_trip_or_404(db: Session, trip_id: uuid.UUID) -> Trip:
    """Fetch a trip by id or raise 404."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip


@router.get(
    "",
    response_model=TripListResponse,
    summary="List trips",
    description="List trips with limit/offset pagination and basic sorting (created_at desc by default).",
    operation_id="list_trips",
)
def list_trips(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of trips to return"),
    offset: int = Query(0, ge=0, description="Number of trips to skip"),
    sort_by: Literal["created_at", "name"] = Query(
        "created_at",
        description="Sort field",
    ),
    sort_dir: Literal["asc", "desc"] = Query(
        "desc",
        description="Sort direction",
    ),
):
    """List trips with pagination.

    Args:
        db: SQLAlchemy Session (FastAPI dependency).
        limit: Page size (1..100).
        offset: Offset into result set.
        sort_by: Field to sort by.
        sort_dir: Sort direction.

    Returns:
        TripListResponse: Paginated list including total count.
    """
    base_stmt = select(Trip)
    base_stmt = _apply_trip_sorting(base_stmt, sort_by=sort_by, sort_dir=sort_dir)

    total = db.execute(select(func.count()).select_from(Trip)).scalar_one()
    trips = db.execute(base_stmt.limit(limit).offset(offset)).scalars().all()

    return TripListResponse(total=total, limit=limit, offset=offset, items=trips)


@router.post(
    "",
    response_model=TripRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create trip",
    description="Create a new trip.",
    operation_id="create_trip",
)
def create_trip(payload: TripCreate, db: Session = Depends(get_db)) -> TripRead:
    """Create a trip.

    Args:
        payload: TripCreate payload.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        TripRead: Created trip.
    """
    now = datetime.now(timezone.utc)
    trip = Trip(
        name=payload.name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        created_at=now,
    )

    # Basic cross-field validation
    if trip.start_date and trip.end_date and trip.end_date < trip.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )

    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get(
    "/{trip_id}",
    response_model=TripRead,
    summary="Get trip",
    description="Get a single trip by UUID.",
    operation_id="get_trip",
)
def get_trip(trip_id: uuid.UUID, db: Session = Depends(get_db)) -> TripRead:
    """Get trip by id.

    Args:
        trip_id: Trip UUID.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        TripRead: Trip record.

    Raises:
        HTTPException: 404 if not found.
    """
    return _get_trip_or_404(db, trip_id)


@router.put(
    "/{trip_id}",
    response_model=TripRead,
    summary="Update trip",
    description="Update a trip by UUID. Only provided fields are updated.",
    operation_id="update_trip",
)
def update_trip(trip_id: uuid.UUID, payload: TripUpdate, db: Session = Depends(get_db)) -> TripRead:
    """Update a trip.

    Args:
        trip_id: Trip UUID.
        payload: TripUpdate payload.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        TripRead: Updated trip.

    Raises:
        HTTPException: 404 if not found; 422 if dates invalid.
    """
    trip = _get_trip_or_404(db, trip_id)

    if payload.name is not None:
        trip.name = payload.name.strip()

    if payload.start_date is not None:
        trip.start_date = payload.start_date

    if payload.end_date is not None:
        trip.end_date = payload.end_date

    if trip.start_date and trip.end_date and trip.end_date < trip.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )

    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.delete(
    "/{trip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete trip",
    description="Delete a trip by UUID.",
    operation_id="delete_trip",
)
def delete_trip(trip_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Delete a trip.

    Args:
        trip_id: Trip UUID.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        Response: 204 No Content.

    Raises:
        HTTPException: 404 if not found.
    """
    trip = _get_trip_or_404(db, trip_id)
    db.delete(trip)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
