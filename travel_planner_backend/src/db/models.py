from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class Trip(Base):
    """ORM model for `trips`."""

    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    itinerary_items: Mapped[list["ItineraryItem"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


Index("idx_trips_name", Trip.name)


class Destination(Base):
    """ORM model for `destinations`."""

    __tablename__ = "destinations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    itinerary_items: Mapped[list["ItineraryItem"]] = relationship(
        back_populates="destination",
        passive_deletes=True,
    )


# Basic btree indexes (useful for equality filtering and some planner strategies)
Index("idx_destinations_name", Destination.name)
Index("idx_destinations_country", Destination.country)
Index("idx_destinations_city", Destination.city)
Index("idx_destinations_popularity", Destination.popularity)

# Trigram-based indexes for fast ILIKE/partial match searches.
# NOTE: Requires PostgreSQL extension `pg_trgm` to be enabled.
Index(
    "idx_destinations_name_trgm",
    Destination.name,
    postgresql_using="gin",
    postgresql_ops={"name": "gin_trgm_ops"},
)
Index(
    "idx_destinations_country_trgm",
    Destination.country,
    postgresql_using="gin",
    postgresql_ops={"country": "gin_trgm_ops"},
)
Index(
    "idx_destinations_city_trgm",
    Destination.city,
    postgresql_using="gin",
    postgresql_ops={"city": "gin_trgm_ops"},
)


class ItineraryItem(Base):
    """ORM model for `itinerary_items`."""

    __tablename__ = "itinerary_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    destination_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("destinations.id", ondelete="SET NULL"),
        nullable=True,
    )

    trip: Mapped["Trip"] = relationship(back_populates="itinerary_items")
    destination: Mapped["Destination"] = relationship(back_populates="itinerary_items")


Index("idx_itinerary_trip_day", ItineraryItem.trip_id, ItineraryItem.day)
Index("idx_itinerary_destination", ItineraryItem.destination_id)


class Note(Base):
    """ORM model for `notes`."""

    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="notes")


Index("idx_notes_trip_created_at", Note.trip_id, Note.created_at.desc())


class Reminder(Base):
    """ORM model for `reminders`."""

    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="reminders")


Index("idx_reminders_trip_remind_at", Reminder.trip_id, Reminder.remind_at.desc())
