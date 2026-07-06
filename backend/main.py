"""FallWatch REST API."""
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import (BackgroundTasks, Depends, FastAPI, Header, HTTPException,
                     Query)
from fastapi.responses import RedirectResponse
from sqlalchemy import case, extract, func, select
from sqlalchemy.orm import Session, selectinload

from . import models, notifications, schemas
from .database import get_db

ALERT_MIN_CONFIDENCE = float(os.environ.get("ALERT_MIN_CONFIDENCE", "0.7"))


def require_api_key(x_api_key: str | None = Header(None)):
    """Write-endpoint guard. When FALLWATCH_API_KEY is set, mutating requests
    must present it in the X-API-Key header; read endpoints stay public so
    the demo dashboard and API docs remain browsable."""
    expected = os.environ.get("FALLWATCH_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(401, "Missing or invalid API key")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("fallwatch")

app = FastAPI(
    title="FallWatch API",
    description="Event ingestion and analytics API for the FallWatch "
                "fall-detection monitoring platform.",
    version="0.1.0",
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health", tags=["system"])
def health():
    return {"status": "ok"}


# ---------------- events ----------------
@app.post("/api/v1/events", response_model=schemas.EventResponse,
          status_code=201, tags=["events"],
          dependencies=[Depends(require_api_key)])
def create_event(payload: schemas.EventCreate,
                 background_tasks: BackgroundTasks,
                 db: Session = Depends(get_db)):
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

    if event.event_type == "fall" and event.confidence >= ALERT_MIN_CONFIDENCE:
        for channel in notifications.configured_channels():
            db.add(models.Alert(event_id=event.id, alert_type=channel))
        db.commit()
        subject = f"Fall detected: {event.device.location}"
        body = (f"Device '{event.device.name}' reported a fall at "
                f"{event.timestamp:%Y-%m-%d %H:%M:%S %Z} "
                f"(confidence {event.confidence:.2f})"
                + (f" involving {event.person.name}." if event.person else "."))
        # delivered after the response returns; the detection client never waits
        background_tasks.add_task(notifications.dispatch, subject, body)

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
    # selectinload avoids one lazy device/person query per returned row
    query = select(models.Event).options(
        selectinload(models.Event.device), selectinload(models.Event.person))
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


@app.delete("/api/v1/events/{event_id}", status_code=204, tags=["events"],
            dependencies=[Depends(require_api_key)])
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


# ---------------- alerts ----------------
@app.get("/api/v1/alerts", response_model=list[schemas.AlertResponse],
         tags=["alerts"])
def list_alerts(db: Session = Depends(get_db),
                acknowledged: bool | None = None,
                limit: int = Query(50, ge=1, le=500)):
    query = select(models.Alert).options(
        selectinload(models.Alert.event).selectinload(models.Event.device),
        selectinload(models.Alert.event).selectinload(models.Event.person))
    if acknowledged is True:
        query = query.where(models.Alert.acknowledged_at.is_not(None))
    elif acknowledged is False:
        query = query.where(models.Alert.acknowledged_at.is_(None))
    return db.scalars(
        query.order_by(models.Alert.sent_at.desc()).limit(limit)).all()


@app.post("/api/v1/alerts/{alert_id}/acknowledge",
          response_model=schemas.AlertResponse, tags=["alerts"],
          dependencies=[Depends(require_api_key)])
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(models.Alert, alert_id)
    if alert is None:
        raise HTTPException(404, f"Alert {alert_id} not found")
    if alert.acknowledged_at is None:  # idempotent
        alert.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)
    return alert


# ---------------- statistics ----------------
@app.get("/api/v1/stats/summary", tags=["statistics"])
def stats_summary(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total = db.scalar(select(func.count(models.Event.id)))
    today = db.scalar(select(func.count(models.Event.id))
                      .where(models.Event.timestamp >= today_start))
    falls_today = db.scalar(
        select(func.count(models.Event.id))
        .where(models.Event.timestamp >= today_start,
               models.Event.event_type == "fall"))
    avg_conf = db.scalar(select(func.avg(models.Event.confidence))
                         .where(models.Event.event_type == "fall"))
    active_devices = db.scalar(
        select(func.count(func.distinct(models.Event.device_id)))
        .where(models.Event.timestamp >= now - timedelta(hours=24)))

    return {
        "total_events": total,
        "events_today": today,
        "falls_today": falls_today,
        "avg_confidence": round(avg_conf, 3) if avg_conf is not None else None,
        "active_devices_24h": active_devices,
    }


@app.get("/api/v1/stats/daily", tags=["statistics"])
def stats_daily(days: int = Query(30, ge=1, le=365),
                db: Session = Depends(get_db)):
    """Event counts per calendar day for the last `days` days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day = func.date(models.Event.timestamp)
    falls = func.sum(case((models.Event.event_type == "fall", 1), else_=0))
    rows = db.execute(
        select(day.label("date"),
               func.count(models.Event.id).label("count"),
               falls.label("falls"))
        .where(models.Event.timestamp >= since)
        .group_by(day).order_by(day)
    ).all()
    return [{"date": str(r.date), "count": r.count, "falls": int(r.falls or 0)}
            for r in rows]


@app.get("/api/v1/stats/hourly", tags=["statistics"])
def stats_hourly(days: int = Query(30, ge=1, le=365),
                 db: Session = Depends(get_db)):
    """Event counts by hour of day over the last `days` days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    hour = extract("hour", models.Event.timestamp)
    rows = db.execute(
        select(hour.label("hour"), func.count(models.Event.id).label("count"))
        .where(models.Event.timestamp >= since)
        .group_by(hour).order_by(hour)
    ).all()
    counts = {int(r.hour): r.count for r in rows}
    return [{"hour": h, "count": counts.get(h, 0)} for h in range(24)]
