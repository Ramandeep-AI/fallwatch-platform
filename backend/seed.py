"""Populate the database with sample devices, persons, and events.

Usage: python -m backend.seed
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from .database import SessionLocal
from .models import Device, Event, Person

DEVICES = [
    ("living-room-cam", "Living room"),
    ("bedroom-cam", "Bedroom"),
    ("kitchen-cam", "Kitchen"),
]
PERSONS = [("Resident A", "medium"), ("Resident B", "high")]


def main():
    random.seed(42)
    db = SessionLocal()
    try:
        if db.scalar(select(func.count(Device.id))) > 0:
            print("[INFO] Database already seeded, nothing to do.")
            return

        devices = [Device(name=n, location=l) for n, l in DEVICES]
        persons = [Person(name=n, risk_level=r) for n, r in PERSONS]
        db.add_all(devices + persons)
        db.flush()  # assigns ids

        now = datetime.now(timezone.utc)
        events = []
        for i in range(30):
            is_fall = random.random() < 0.3
            events.append(Event(
                device_id=random.choice(devices).id,
                person_id=random.choice(persons).id,
                event_type="fall" if is_fall else "activity",
                confidence=round(random.uniform(0.55, 0.98), 2),
                timestamp=now - timedelta(hours=random.uniform(0, 72)),
            ))
        db.add_all(events)
        db.commit()
        print(f"[OK] Seeded {len(devices)} devices, {len(persons)} persons, "
              f"{len(events)} events.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
