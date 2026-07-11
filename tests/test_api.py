"""API tests running against an in-memory SQLite database (no Docker needed)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.models import Device, Person

engine = create_engine("sqlite://",
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def client():
    Base.metadata.create_all(engine)
    session = TestingSession()
    session.add_all([Device(name="cam-1", location="Living room"),
                     Person(name="Resident A", risk_level="medium")])
    session.commit()
    session.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def make_event(client, **overrides):
    payload = {"device_id": 1, "person_id": 1, "event_type": "fall",
               "confidence": 0.91} | overrides
    return client.post("/api/v1/events", json=payload)


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_create_event_returns_nested_device_and_person(client):
    resp = make_event(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["event_type"] == "fall"
    assert body["device"]["name"] == "cam-1"
    assert body["person"]["name"] == "Resident A"


def test_create_event_unknown_device_returns_404(client):
    resp = make_event(client, device_id=999)
    assert resp.status_code == 404


def test_create_event_invalid_confidence_returns_422(client):
    resp = make_event(client, confidence=1.5)
    assert resp.status_code == 422


def test_list_events_pagination_and_total(client):
    for _ in range(5):
        make_event(client)
    resp = client.get("/api/v1/events?limit=2&offset=0")
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_events_filter_by_type(client):
    make_event(client, event_type="fall")
    make_event(client, event_type="activity")
    body = client.get("/api/v1/events?event_type=fall").json()
    assert body["total"] == 1
    assert body["items"][0]["event_type"] == "fall"


def test_get_single_event_and_404(client):
    event_id = make_event(client).json()["id"]
    assert client.get(f"/api/v1/events/{event_id}").status_code == 200
    assert client.get("/api/v1/events/9999").status_code == 404


def test_delete_event(client):
    event_id = make_event(client).json()["id"]
    assert client.delete(f"/api/v1/events/{event_id}").status_code == 204
    assert client.get(f"/api/v1/events/{event_id}").status_code == 404


def test_list_devices(client):
    body = client.get("/api/v1/devices").json()
    assert len(body) == 1
    assert body[0]["name"] == "cam-1"


def test_stats_summary(client):
    make_event(client, event_type="fall", confidence=0.9)
    make_event(client, event_type="activity", confidence=0.7)
    body = client.get("/api/v1/stats/summary").json()
    assert body["total_events"] == 2
    assert body["events_today"] == 2
    assert body["falls_today"] == 1
    assert body["avg_confidence"] == 0.9  # falls only
    assert body["active_devices_24h"] == 1


def test_stats_daily(client):
    make_event(client, event_type="fall")
    make_event(client, event_type="activity")
    body = client.get("/api/v1/stats/daily").json()
    assert len(body) == 1  # all events created today
    assert body[0]["count"] == 2
    assert body[0]["falls"] == 1


def test_stats_hourly_covers_all_24_hours(client):
    make_event(client)
    body = client.get("/api/v1/stats/hourly").json()
    assert len(body) == 24
    assert sum(row["count"] for row in body) == 1


def test_high_confidence_fall_creates_alert(client):
    event_id = make_event(client, event_type="fall", confidence=0.92).json()["id"]
    alerts = client.get("/api/v1/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["event_id"] == event_id
    assert alerts[0]["alert_type"] == "console"
    assert alerts[0]["acknowledged_at"] is None
    assert alerts[0]["event"]["device"]["name"] == "cam-1"


def test_low_confidence_fall_creates_no_alert(client):
    make_event(client, event_type="fall", confidence=0.55)
    assert client.get("/api/v1/alerts").json() == []


def test_activity_event_creates_no_alert(client):
    make_event(client, event_type="activity", confidence=0.99)
    assert client.get("/api/v1/alerts").json() == []


def test_acknowledge_alert_is_idempotent(client):
    make_event(client, event_type="fall", confidence=0.9)
    alert_id = client.get("/api/v1/alerts").json()[0]["id"]

    first = client.post(f"/api/v1/alerts/{alert_id}/acknowledge").json()
    assert first["acknowledged_at"] is not None
    second = client.post(f"/api/v1/alerts/{alert_id}/acknowledge").json()
    assert second["acknowledged_at"] == first["acknowledged_at"]

    assert client.get("/api/v1/alerts?acknowledged=false").json() == []
    assert len(client.get("/api/v1/alerts?acknowledged=true").json()) == 1


def test_acknowledge_unknown_alert_returns_404(client):
    assert client.post("/api/v1/alerts/999/acknowledge").status_code == 404


def test_event_type_is_normalized_on_ingest(client):
    make_event(client, event_type="  Fall ")
    body = client.get("/api/v1/events").json()
    assert body["items"][0]["event_type"] == "fall"
    # normalization means the alert pipeline fires despite the odd casing
    assert len(client.get("/api/v1/alerts").json()) == 1


def test_write_endpoints_require_api_key_when_configured(client, monkeypatch):
    monkeypatch.setenv("FALLWATCH_API_KEY", "test-secret")

    assert make_event(client).status_code == 401
    assert client.post("/api/v1/alerts/1/acknowledge").status_code == 401
    assert client.delete("/api/v1/events/1").status_code == 401
    assert client.post("/api/v1/push-tokens",
                       json={"token": "ExponentPushToken[x]"}).status_code == 401

    ok = client.post("/api/v1/events", headers={"X-API-Key": "test-secret"},
                     json={"device_id": 1, "person_id": 1,
                           "event_type": "fall", "confidence": 0.9})
    assert ok.status_code == 201
    # reads stay public
    assert client.get("/api/v1/events").status_code == 200


def test_register_push_token_is_idempotent(client):
    payload = {"token": "ExponentPushToken[abc]", "device_name": "Pixel 8"}
    first = client.post("/api/v1/push-tokens", json=payload).json()
    second = client.post("/api/v1/push-tokens",
                         json=payload | {"device_name": "Pixel 8 Pro"}).json()
    assert second["id"] == first["id"]  # same token row, refreshed
    assert second["device_name"] == "Pixel 8 Pro"


def test_register_push_token_rejects_empty(client):
    assert client.post("/api/v1/push-tokens", json={"token": ""}).status_code == 422


def test_fall_alert_uses_push_channel_when_token_registered(client, monkeypatch):
    from backend import notifications

    sent = []

    def fake_post(url, json, timeout):
        sent.append((url, json))
        class FakeResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return {"data": [{"status": "ok"} for _ in json]}
        return FakeResponse()

    monkeypatch.setattr(notifications.requests, "post", fake_post)

    client.post("/api/v1/push-tokens", json={"token": "ExponentPushToken[abc]"})
    make_event(client, event_type="fall", confidence=0.92)

    channels = {a["alert_type"] for a in client.get("/api/v1/alerts").json()}
    assert channels == {"console", "push"}

    # TestClient runs background tasks before returning, so delivery happened
    assert len(sent) == 1
    url, messages = sent[0]
    assert url == notifications.EXPO_PUSH_URL
    assert messages[0]["to"] == "ExponentPushToken[abc]"
    assert messages[0]["title"].startswith("Fall detected")


def test_fall_without_tokens_keeps_console_only(client):
    make_event(client, event_type="fall", confidence=0.92)
    channels = {a["alert_type"] for a in client.get("/api/v1/alerts").json()}
    assert channels == {"console"}
