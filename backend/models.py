"""SQLAlchemy ORM models mirroring backend/sql/schema.sql."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Device(Base):
    """A camera or sensor source posting detection events."""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    location: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    events: Mapped[list["Event"]] = relationship(back_populates="device")


class Person(Base):
    """A monitored individual."""
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    events: Mapped[list["Event"]] = relationship(back_populates="person")


class Event(Base):
    """A detection event (fall or other classified activity)."""
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50))  # e.g. "fall", "test"
    confidence: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    video_frame_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    device: Mapped["Device"] = relationship(back_populates="events")
    person: Mapped["Person | None"] = relationship(back_populates="events")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="event",
                                                 cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_events_timestamp", "timestamp"),
        Index("ix_events_device_id", "device_id"),
    )


class PushToken(Base):
    """A mobile device registered to receive push alerts (Expo push tokens)."""
    __tablename__ = "push_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(200), unique=True)
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    """A notification sent in response to an event."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    alert_type: Mapped[str] = mapped_column(String(50))  # e.g. "sms", "email"
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    event: Mapped["Event"] = relationship(back_populates="alerts")
