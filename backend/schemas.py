"""Pydantic request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- devices ----
class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    status: str
    created_at: datetime


# ---- persons ----
class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    risk_level: str
    created_at: datetime


# ---- events ----
class EventCreate(BaseModel):
    device_id: int
    person_id: int | None = None
    event_type: str = Field(min_length=1, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime | None = None  # server time used when omitted
    video_frame_path: str | None = None
    notes: str | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    person_id: int | None
    event_type: str
    confidence: float
    timestamp: datetime
    video_frame_path: str | None
    notes: str | None
    device: DeviceResponse
    person: PersonResponse | None


class EventListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[EventResponse]


# ---- alerts ----
class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    alert_type: str
    sent_at: datetime
    acknowledged_at: datetime | None
    event: EventResponse
