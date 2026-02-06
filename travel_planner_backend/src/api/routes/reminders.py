from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import Reminder, Trip
from src.db.session import get_db
from src.schemas.travel import ReminderCreate, ReminderRead

router = APIRouter(
    prefix="/api/trips/{trip_id}/reminders",
    tags=["Reminders"],
)


def _get_trip_or_404(db: Session, trip_id: uuid.UUID) -> Trip:
    """Fetch a trip by id or raise 404."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip


def _get_reminder_or_404(db: Session, trip_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
    """Fetch a reminder by id scoped to a trip or raise 404."""
    stmt = select(Reminder).where(Reminder.id == reminder_id, Reminder.trip_id == trip_id)
    reminder = db.execute(stmt).scalars().first()
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


class ReminderUpdate(BaseModel):
    """Schema for updating a reminder.

    Notes:
        We keep this schema local to the router to avoid changing shared schemas in this step.
        Editable fields: `message`, `remind_at`. `trip_id` is controlled by the URL path.
    """

    message: Optional[str] = Field(None, description="Reminder message", max_length=255)
    remind_at: Optional["datetime"] = Field(None, description="When to remind (datetime)")  # type: ignore[name-defined]


class ReminderListResponse(BaseModel):
    """Paginated list response for reminders."""

    total: int = Field(..., description="Total number of reminders available for the trip (ignores pagination)")
    limit: int = Field(..., description="Page size limit used for this response", ge=1, le=100)
    offset: int = Field(..., description="Offset used for this response", ge=0)
    items: list[ReminderRead] = Field(..., description="Reminders in the current page")


@router.get(
    "",
    response_model=ReminderListResponse,
    summary="List reminders",
    description="List reminders for a trip with limit/offset pagination.",
    operation_id="list_trip_reminders",
)
def list_reminders(
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of reminders to return"),
    offset: int = Query(0, ge=0, description="Number of reminders to skip"),
) -> ReminderListResponse:
    """List reminders for a trip with pagination.

    Args:
        trip_id: Trip UUID.
        db: SQLAlchemy Session (FastAPI dependency).
        limit: Page size (1..100).
        offset: Offset into result set.

    Returns:
        ReminderListResponse: Paginated list including total count.

    Raises:
        HTTPException: 404 if the trip does not exist.
    """
    _get_trip_or_404(db, trip_id)

    total_stmt = select(func.count()).select_from(Reminder).where(Reminder.trip_id == trip_id)
    total = db.execute(total_stmt).scalar_one()

    items_stmt = (
        select(Reminder)
        .where(Reminder.trip_id == trip_id)
        .order_by(Reminder.remind_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = db.execute(items_stmt).scalars().all()

    return ReminderListResponse(total=total, limit=limit, offset=offset, items=items)


@router.post(
    "",
    response_model=ReminderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create reminder",
    description="Create a new reminder under a trip.",
    operation_id="create_trip_reminder",
)
def create_reminder(
    trip_id: uuid.UUID,
    payload: ReminderCreate,
    db: Session = Depends(get_db),
) -> ReminderRead:
    """Create a reminder under a trip.

    Notes:
        The request schema includes `trip_id`, but this route is nested under a trip.
        We enforce trip ownership from the path parameter and reject mismatches.

    Args:
        trip_id: Trip UUID (path).
        payload: ReminderCreate payload.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        ReminderRead: Created reminder.

    Raises:
        HTTPException: 404 if trip not found; 422 if `payload.trip_id` mismatches `trip_id` or message blank.
    """
    _get_trip_or_404(db, trip_id)

    if payload.trip_id != trip_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="payload.trip_id must match trip_id path parameter",
        )

    if payload.message.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="message must not be blank",
        )

    now = datetime.now(timezone.utc)
    reminder = Reminder(
        trip_id=trip_id,
        message=payload.message.strip(),
        remind_at=payload.remind_at,
        created_at=now,
    )

    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get(
    "/{reminder_id}",
    response_model=ReminderRead,
    summary="Get reminder",
    description="Get a single reminder by UUID scoped to a trip.",
    operation_id="get_trip_reminder",
)
def get_reminder(
    trip_id: uuid.UUID,
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ReminderRead:
    """Get a reminder by id (scoped to trip).

    Args:
        trip_id: Trip UUID.
        reminder_id: Reminder UUID.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        ReminderRead: Reminder record.

    Raises:
        HTTPException: 404 if the trip or reminder is not found.
    """
    _get_trip_or_404(db, trip_id)
    return _get_reminder_or_404(db, trip_id, reminder_id)


@router.put(
    "/{reminder_id}",
    response_model=ReminderRead,
    summary="Update reminder",
    description="Update a reminder by UUID scoped to a trip. Only provided fields are updated.",
    operation_id="update_trip_reminder",
)
def update_reminder(
    trip_id: uuid.UUID,
    reminder_id: uuid.UUID,
    payload: ReminderUpdate,
    db: Session = Depends(get_db),
) -> ReminderRead:
    """Update a reminder (scoped to trip).

    Args:
        trip_id: Trip UUID.
        reminder_id: Reminder UUID.
        payload: ReminderUpdate payload.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        ReminderRead: Updated reminder.

    Raises:
        HTTPException: 404 if trip or reminder not found; 422 if message blank.
    """
    _get_trip_or_404(db, trip_id)
    reminder = _get_reminder_or_404(db, trip_id, reminder_id)

    if payload.message is not None:
        if payload.message.strip() == "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="message must not be blank",
            )
        reminder.message = payload.message.strip()

    if payload.remind_at is not None:
        reminder.remind_at = payload.remind_at

    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete(
    "/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete reminder",
    description="Delete a reminder by UUID scoped to a trip.",
    operation_id="delete_trip_reminder",
)
def delete_reminder(
    trip_id: uuid.UUID,
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a reminder (scoped to trip).

    Args:
        trip_id: Trip UUID.
        reminder_id: Reminder UUID.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        Response: 204 No Content.

    Raises:
        HTTPException: 404 if trip or reminder not found.
    """
    _get_trip_or_404(db, trip_id)
    reminder = _get_reminder_or_404(db, trip_id, reminder_id)

    db.delete(reminder)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
