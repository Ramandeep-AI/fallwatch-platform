"""Thin client for the FallWatch API used by the dashboard."""
import os

import requests

API_URL = os.environ.get("FALLWATCH_API_URL", "http://localhost:8000")
TIMEOUT = 5


def _get(path: str, **params):
    resp = requests.get(f"{API_URL}{path}", params=params or None,
                        timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def health_ok() -> bool:
    try:
        return _get("/api/v1/health")["status"] == "ok"
    except requests.RequestException:
        return False


def get_summary():
    return _get("/api/v1/stats/summary")


def get_daily(days: int = 30):
    return _get("/api/v1/stats/daily", days=days)


def get_hourly(days: int = 30):
    return _get("/api/v1/stats/hourly", days=days)


def get_events(**filters):
    return _get("/api/v1/events", **filters)


def get_devices():
    return _get("/api/v1/devices")


def get_alerts(acknowledged: bool | None = None):
    params = {}
    if acknowledged is not None:
        params["acknowledged"] = acknowledged
    return _get("/api/v1/alerts", **params)


def acknowledge_alert(alert_id: int):
    resp = requests.post(f"{API_URL}/api/v1/alerts/{alert_id}/acknowledge",
                         timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def create_demo_event():
    """Post a demonstration fall event through the real ingestion pipeline."""
    resp = requests.post(f"{API_URL}/api/v1/events", timeout=TIMEOUT,
                         json={"device_id": 1, "person_id": 1,
                               "event_type": "fall", "confidence": 0.9,
                               "notes": "demo alert"})
    resp.raise_for_status()
    return resp.json()
