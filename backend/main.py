"""FallWatch REST API."""
import logging
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("fallwatch")

app = FastAPI(
    title="FallWatch API",
    description="Event ingestion and analytics API for the FallWatch "
                "fall-detection monitoring platform.",
    version="0.1.0",
)


@app.get("/api/v1/health", tags=["system"])
def health():
    return {"status": "ok"}


# ---------------- events ----------------
@app.post("/api/v1/events", response_model=schemas.EventResponse,
          status_code=201, tags=["events"])
def create_event(payload: schemas.EventCreate, db: Session = Depends(get_db)):
    if db.get(models.Device, payload.device_id) is None:
        raise HTTPException(404, f"Device {payload.device_id} not found")
    if payload.person_id is not None and db.get(models.Person, payload.person_id) is None:
        raise HTTPException(404, f"Person {payload.person_id} not found")

    event = models.Event(**payload.model_dump(exclude_none=True))
    db.add(event)
    db.commit()
    db.refresh(event)
    logger.info("event created: id=%s type=%s device=%s confidence=%.2f",
                event.id, event.event_type, event.device_id, event.confidence)
    return event


@app.get("/api/v1/events", response_model=schemas.EventListResponse, tags=["events"])
def list_events(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    device_id: int | None = None,
    person_id: int | None = None,
    event_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
):
    query = select(models.Event)
    if device_id is not None:
        query = query.where(models.Event.device_id == device_id)
    if person_id is not None:
        query = query.where(models.Event.person_id == person_id)
    if event_type is not None:
        query = query.where(models.Event.event_type == event_type)
    if start is not None:
        query = query.where(models.Event.timestamp >= start)
    if end is not None:
        query = query.where(models.Event.timestamp <= end)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(models.Event.timestamp.desc()).limit(limit).offset(offset)
    ).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@app.get("/api/v1/events/{event_id}", response_model=schemas.EventResponse,
         tags=["events"])
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(models.Event, event_id)
    if event is None:
        raise HTTPException(404, f"Event {event_id} not found")
    return event


@app.delete("/api/v1/events/{event_id}", status_code=204, tags=["events"])
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(models.Event, event_id)
    if event is None:
        raise HTTPException(404, f"Event {event_id} not found")
    db.delete(event)
    db.commit()


# ---------------- devices ----------------
@app.get("/api/v1/devices", response_model=list[schemas.DeviceResponse],
         tags=["devices"])
def list_devices(db: Session = Depends(get_db)):
    return db.scalars(select(models.Device).order_by(models.Device.id)).all()
