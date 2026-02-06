from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import ItineraryItem, Trip
from src.db.session import get_db
from src.schemas.travel import ItineraryItemCreate, ItineraryItemRead


router = APIRouter(
    prefix="/api/trips/{trip_id}/itinerary",
    tags=["Itinerary"],
)


def _get_trip_or_404(db: Session, trip_id: uuid.UUID) -> Trip:
    """Fetch a trip by id or raise 404."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip


def _get_itinerary_item_or_404(db: Session, trip_id: uuid.UUID, item_id: uuid.UUID) -> ItineraryItem:
    """Fetch an itinerary item by id scoped to a trip or raise 404."""
    stmt = select(ItineraryItem).where(ItineraryItem.id == item_id, ItineraryItem.trip_id == trip_id)
    item = db.execute(stmt).scalars().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Itinerary item not found")
    return item


class ItineraryItemUpdate(BaseModel):
    """Schema for updating an itinerary item.

    Notes:
        We keep this schema local to the router to avoid changing shared schemas in this step.
        Fields are optional; constraints match ItineraryItemBase/ItineraryItemCreate where relevant.
        `trip_id` is intentionally not updatable; trip ownership is controlled by the URL path.
    """

    day: Optional[int] = Field(None, description="Day number within trip (1..N)", ge=1)
    title: Optional[str] = Field(None, description="Itinerary item title", max_length=200)
    description: Optional[str] = Field(None, description="Details")
    start_time: Optional["datetime"] = Field(None, description="Start datetime (optional)")  # type: ignore[name-defined]
    end_time: Optional["datetime"] = Field(None, description="End datetime (optional)")  # type: ignore[name-defined]
    destination_id: Optional[uuid.UUID] = Field(None, description="Optional destination UUID")


class ItineraryItemListResponse(BaseModel):
    """Paginated list response for itinerary items."""

    total: int = Field(..., description="Total number of itinerary items available for the trip (ignores pagination)")
    limit: int = Field(..., description="Page size limit used for this response", ge=1, le=100)
    offset: int = Field(..., description="Offset used for this response", ge=0)
    items: list[ItineraryItemRead] = Field(..., description="Itinerary items in the current page")


@router.get(
    "",
    response_model=ItineraryItemListResponse,
    summary="List itinerary items",
    description="List itinerary items for a trip with limit/offset pagination.",
    operation_id="list_itinerary_items",
)
def list_itinerary_items(
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of itinerary items to return"),
    offset: int = Query(0, ge=0, description="Number of itinerary items to skip"),
) -> ItineraryItemListResponse:
    """List itinerary items for a trip with pagination.

    Args:
        trip_id: Trip UUID.
        db: SQLAlchemy Session (FastAPI dependency).
        limit: Page size (1..100).
        offset: Offset into result set.

    Returns:
        ItineraryItemListResponse: Paginated list including total count.

    Raises:
        HTTPException: 404 if the trip does not exist.
    """
    _get_trip_or_404(db, trip_id)

    total_stmt = select(func.count()).select_from(ItineraryItem).where(ItineraryItem.trip_id == trip_id)
    total = db.execute(total_stmt).scalar_one()

    items_stmt = (
        select(ItineraryItem)
        .where(ItineraryItem.trip_id == trip_id)
        .order_by(ItineraryItem.day.asc(), ItineraryItem.start_time.asc().nulls_last(), ItineraryItem.title.asc())
        .limit(limit)
        .offset(offset)
    )
    items = db.execute(items_stmt).scalars().all()

    return ItineraryItemListResponse(total=total, limit=limit, offset=offset, items=items)


@router.post(
    "",
    response_model=ItineraryItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create itinerary item",
    description="Create a new itinerary item under a trip.",
    operation_id="create_itinerary_item",
)
def create_itinerary_item(
    trip_id: uuid.UUID,
    payload: ItineraryItemCreate,
    db: Session = Depends(get_db),
) -> ItineraryItemRead:
    """Create an itinerary item under a trip.

    Notes:
        The request schema includes `trip_id`, but this route is nested under a trip.
        We enforce trip ownership from the path parameter and reject mismatches.

    Args:
        trip_id: Trip UUID (path).
        payload: ItineraryItemCreate payload.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        ItineraryItemRead: Created itinerary item.

    Raises:
        HTTPException: 404 if trip not found; 422 if `payload.trip_id` mismatches `trip_id` or times invalid.
    """
    _get_trip_or_404(db, trip_id)

    if payload.trip_id != trip_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="payload.trip_id must match trip_id path parameter",
        )

    if payload.start_time and payload.end_time and payload.end_time < payload.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be on or after start_time",
        )

    item = ItineraryItem(
        trip_id=trip_id,
        day=payload.day,
        title=payload.title.strip(),
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        destination_id=payload.destination_id,
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/{item_id}",
    response_model=ItineraryItemRead,
    summary="Get itinerary item",
    description="Get a single itinerary item by UUID scoped to a trip.",
    operation_id="get_itinerary_item",
)
def get_itinerary_item(
    trip_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ItineraryItemRead:
    """Get an itinerary item by id (scoped to trip).

    Args:
        trip_id: Trip UUID.
        item_id: Itinerary item UUID.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        ItineraryItemRead: Itinerary item record.

    Raises:
        HTTPException: 404 if the trip or item is not found.
    """
    _get_trip_or_404(db, trip_id)
    return _get_itinerary_item_or_404(db, trip_id, item_id)


@router.put(
    "/{item_id}",
    response_model=ItineraryItemRead,
    summary="Update itinerary item",
    description="Update an itinerary item by UUID scoped to a trip. Only provided fields are updated.",
    operation_id="update_itinerary_item",
)
def update_itinerary_item(
    trip_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ItineraryItemUpdate,
    db: Session = Depends(get_db),
) -> ItineraryItemRead:
    """Update an itinerary item (scoped to trip).

    Args:
        trip_id: Trip UUID.
        item_id: Itinerary item UUID.
        payload: ItineraryItemUpdate payload.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        ItineraryItemRead: Updated itinerary item.

    Raises:
        HTTPException: 404 if trip or item not found; 422 if times invalid.
    """
    _get_trip_or_404(db, trip_id)
    item = _get_itinerary_item_or_404(db, trip_id, item_id)

    if payload.day is not None:
        item.day = payload.day

    if payload.title is not None:
        if payload.title.strip() == "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="title must not be blank",
            )
        item.title = payload.title.strip()

    if payload.description is not None:
        item.description = payload.description

    if payload.start_time is not None:
        item.start_time = payload.start_time

    if payload.end_time is not None:
        item.end_time = payload.end_time

    if payload.destination_id is not None:
        item.destination_id = payload.destination_id

    if item.start_time and item.end_time and item.end_time < item.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be on or after start_time",
        )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete itinerary item",
    description="Delete an itinerary item by UUID scoped to a trip.",
    operation_id="delete_itinerary_item",
)
def delete_itinerary_item(
    trip_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an itinerary item (scoped to trip).

    Args:
        trip_id: Trip UUID.
        item_id: Itinerary item UUID.
        db: SQLAlchemy Session (FastAPI dependency).

    Returns:
        Response: 204 No Content.

    Raises:
        HTTPException: 404 if trip or item not found.
    """
    _get_trip_or_404(db, trip_id)
    item = _get_itinerary_item_or_404(db, trip_id, item_id)

    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
