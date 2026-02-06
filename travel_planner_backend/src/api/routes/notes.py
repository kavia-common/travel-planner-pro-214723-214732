from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import Note, Trip
from src.db.session import get_db
from src.schemas.travel import NoteCreate, NoteRead

router = APIRouter(
    prefix="/api/trips/{trip_id}/notes",
    tags=["Notes"],
)


def _get_trip_or_404(db: Session, trip_id: uuid.UUID) -> Trip:
    """Fetch a trip by id or raise 404."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip


def _get_note_or_404(db: Session, trip_id: uuid.UUID, note_id: uuid.UUID) -> Note:
    """Fetch a note by id scoped to a trip or raise 404."""
    stmt = select(Note).where(Note.id == note_id, Note.trip_id == trip_id)
    note = db.execute(stmt).scalars().first()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


class NoteUpdate(BaseModel):
    """Schema for updating a note.

    Notes:
        We keep this schema local to the router to avoid changing shared schemas in this step.
        Only `content` is editable; `trip_id` is intentionally controlled by the URL path.
    """

    content: Optional[str] = Field(None, description="Note content")


class NoteListResponse(BaseModel):
    """Paginated list response for notes."""

    total: int = Field(..., description="Total number of notes available for the trip (ignores pagination)")
    limit: int = Field(..., description="Page size limit used for this response", ge=1, le=100)
    offset: int = Field(..., description="Offset used for this response", ge=0)
    items: list[NoteRead] = Field(..., description="Notes in the current page")


@router.get(
    "",
    response_model=NoteListResponse,
    summary="List notes",
    description="List notes for a trip with limit/offset pagination.",
    operation_id="list_trip_notes",
)
def list_notes(
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of notes to return"),
    offset: int = Query(0, ge=0, description="Number of notes to skip"),
) -> NoteListResponse:
    """List notes for a trip with pagination.

    Args:
        trip_id: Trip UUID.
        db: SQLAlchemy Session (FastAPI dependency).
        limit: Page size (1..100).
        offset: Offset into result set.

    Returns:
        NoteListResponse: Paginated list including total count.

    Raises:
        HTTPException: 404 if the trip does not exist.
    """
    _get_trip_or_404(db, trip_id)

    total_stmt = select(func.count()).select_from(Note).where(Note.trip_id == trip_id)
    total = db.execute(total_stmt).scalar_one()

    items_stmt = (
        select(Note)
        .where(Note.trip_id == trip_id)
        .order_by(Note.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = db.execute(items_stmt).scalars().all()

    return NoteListResponse(total=total, limit=limit, offset=offset, items=items)


@router.post(
    "",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create note",
    description="Create a new note under a trip.",
    operation_id="create_trip_note",
)
def create_note(
    trip_id: uuid.UUID,
    payload: NoteCreate,
    db: Session = Depends(get_db),
) -> NoteRead:
    """Create a note under a trip.

    Notes:
        The request schema includes `trip_id`, but this route is nested under a trip.
        We enforce trip ownership from the path parameter and reject mismatches.

    Args:
        trip_id: Trip UUID (path).
        payload: NoteCreate payload.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        NoteRead: Created note.

    Raises:
        HTTPException: 404 if trip not found; 422 if `payload.trip_id` mismatches `trip_id` or content blank.
    """
    _get_trip_or_404(db, trip_id)

    if payload.trip_id != trip_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="payload.trip_id must match trip_id path parameter",
        )

    if payload.content.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="content must not be blank",
        )

    now = datetime.now(timezone.utc)
    note = Note(
        trip_id=trip_id,
        content=payload.content,
        created_at=now,
    )

    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get(
    "/{note_id}",
    response_model=NoteRead,
    summary="Get note",
    description="Get a single note by UUID scoped to a trip.",
    operation_id="get_trip_note",
)
def get_note(
    trip_id: uuid.UUID,
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> NoteRead:
    """Get a note by id (scoped to trip).

    Args:
        trip_id: Trip UUID.
        note_id: Note UUID.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        NoteRead: Note record.

    Raises:
        HTTPException: 404 if the trip or note is not found.
    """
    _get_trip_or_404(db, trip_id)
    return _get_note_or_404(db, trip_id, note_id)


@router.put(
    "/{note_id}",
    response_model=NoteRead,
    summary="Update note",
    description="Update a note by UUID scoped to a trip. Only provided fields are updated.",
    operation_id="update_trip_note",
)
def update_note(
    trip_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
) -> NoteRead:
    """Update a note (scoped to trip).

    Args:
        trip_id: Trip UUID.
        note_id: Note UUID.
        payload: NoteUpdate payload.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        NoteRead: Updated note.

    Raises:
        HTTPException: 404 if trip or note not found; 422 if content blank.
    """
    _get_trip_or_404(db, trip_id)
    note = _get_note_or_404(db, trip_id, note_id)

    if payload.content is not None:
        if payload.content.strip() == "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="content must not be blank",
            )
        note.content = payload.content

    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete note",
    description="Delete a note by UUID scoped to a trip.",
    operation_id="delete_trip_note",
)
def delete_note(
    trip_id: uuid.UUID,
    note_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a note (scoped to trip).

    Args:
        trip_id: Trip UUID.
        note_id: Note UUID.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        Response: 204 No Content.

    Raises:
        HTTPException: 404 if trip or note not found.
    """
    _get_trip_or_404(db, trip_id)
    note = _get_note_or_404(db, trip_id, note_id)

    db.delete(note)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
