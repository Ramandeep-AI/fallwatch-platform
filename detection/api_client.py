"""Client for posting fall detection events to the FallWatch API.

Integration point in the detection project (fall-detection-prototype,
src/run_realtime.py): call report_fall() at the moment the alarm latches,
i.e. where `alarm_until` is set.
"""
import logging
import os
import time

import requests

API_URL = os.environ.get("FALLWATCH_API_URL", "http://localhost:8000")
DEVICE_ID = int(os.environ.get("FALLWATCH_DEVICE_ID", "1"))

MAX_RETRIES = 3
logger = logging.getLogger("fallwatch.client")


def report_fall(confidence: float, person_id: int | None = None,
                notes: str | None = None) -> bool:
    """POST a fall event. Retries with exponential backoff; returns success."""
    payload = {
        "device_id": DEVICE_ID,
        "event_type": "fall",
        "confidence": round(confidence, 3),
    }
    if person_id is not None:
        payload["person_id"] = person_id
    if notes:
        payload["notes"] = notes

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(f"{API_URL}/api/v1/events", json=payload,
                                 timeout=5)
            resp.raise_for_status()
            logger.info("fall event reported: id=%s", resp.json()["id"])
            return True
        except requests.RequestException as exc:
            wait = 2 ** attempt
            logger.warning("event POST failed (%s), retry in %ss", exc, wait)
            time.sleep(wait)
    logger.error("event POST failed after %s attempts", MAX_RETRIES)
    return False
