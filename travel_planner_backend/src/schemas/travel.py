from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class _BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TripBase(_BaseSchema):
    name: str = Field(..., description="Trip name", max_length=200)
    start_date: Optional[date] = Field(None, description="Trip start date")
    end_date: Optional[date] = Field(None, description="Trip end date")


class TripCreate(TripBase):
    pass


class TripRead(TripBase):
    id: uuid.UUID = Field(..., description="Trip UUID")
    created_at: datetime = Field(..., description="Timestamp when the trip was created")


class DestinationBase(_BaseSchema):
    name: str = Field(..., description="Destination name", max_length=200)
    country: Optional[str] = Field(None, description="Country", max_length=100)
    description: Optional[str] = Field(None, description="Free-form description")


class DestinationCreate(DestinationBase):
    pass


class DestinationRead(DestinationBase):
    id: uuid.UUID = Field(..., description="Destination UUID")


class DestinationSearchResult(_BaseSchema):
    """Destination search result item.

    Note:
        This schema is intentionally narrow and optimized for search/list UIs.
    """

    id: uuid.UUID = Field(..., description="Destination UUID")
    name: str = Field(..., description="Destination name", max_length=200)
    country: Optional[str] = Field(None, description="Country", max_length=100)
    city: Optional[str] = Field(None, description="City", max_length=100)
    popularity: Optional[int] = Field(None, description="Popularity score (higher means more popular)")
    score: Optional[float] = Field(None, description="Optional search relevance score (if available)")


class DestinationSearchResponse(_BaseSchema):
    """Paginated response for destination search."""

    total: int = Field(..., description="Total number of matching destinations (ignores pagination)")
    limit: int = Field(..., description="Page size limit used for this response", ge=1, le=100)
    offset: int = Field(..., description="Offset used for this response", ge=0)
    items: list[DestinationSearchResult] = Field(..., description="Matching destinations in the current page")


class ItineraryItemBase(_BaseSchema):
    trip_id: uuid.UUID = Field(..., description="Trip UUID")
    day: int = Field(..., description="Day number within trip (1..N)", ge=1)
    title: str = Field(..., description="Itinerary item title", max_length=200)
    description: Optional[str] = Field(None, description="Details")
    start_time: Optional[datetime] = Field(None, description="Start datetime (optional)")
    end_time: Optional[datetime] = Field(None, description="End datetime (optional)")
    destination_id: Optional[uuid.UUID] = Field(None, description="Optional destination UUID")


class ItineraryItemCreate(ItineraryItemBase):
    pass


class ItineraryItemRead(ItineraryItemBase):
    id: uuid.UUID = Field(..., description="Itinerary item UUID")


class NoteBase(_BaseSchema):
    trip_id: uuid.UUID = Field(..., description="Trip UUID")
    content: str = Field(..., description="Note content")


class NoteCreate(NoteBase):
    pass


class NoteRead(NoteBase):
    id: uuid.UUID = Field(..., description="Note UUID")
    created_at: datetime = Field(..., description="Timestamp when the note was created")


class ReminderBase(_BaseSchema):
    trip_id: uuid.UUID = Field(..., description="Trip UUID")
    message: str = Field(..., description="Reminder message", max_length=255)
    remind_at: datetime = Field(..., description="When to remind (datetime)")


class ReminderCreate(ReminderBase):
    pass


class ReminderRead(ReminderBase):
    id: uuid.UUID = Field(..., description="Reminder UUID")
    created_at: datetime = Field(..., description="Timestamp when reminder was created")
