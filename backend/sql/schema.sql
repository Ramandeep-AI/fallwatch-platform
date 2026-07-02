-- FallWatch relational schema (reference copy; Alembic manages migrations).

CREATE TABLE devices (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    location    VARCHAR(200) NOT NULL,
    status      VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE persons (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    risk_level  VARCHAR(20)  NOT NULL DEFAULT 'unknown',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id               SERIAL PRIMARY KEY,
    device_id        INTEGER NOT NULL REFERENCES devices(id),
    person_id        INTEGER REFERENCES persons(id),
    event_type       VARCHAR(50) NOT NULL,
    confidence       DOUBLE PRECISION NOT NULL,
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT now(),
    video_frame_path VARCHAR(500),
    notes            TEXT
);

CREATE INDEX ix_events_timestamp ON events (timestamp);
CREATE INDEX ix_events_device_id ON events (device_id);

CREATE TABLE alerts (
    id              SERIAL PRIMARY KEY,
    event_id        INTEGER NOT NULL REFERENCES events(id),
    alert_type      VARCHAR(50) NOT NULL,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ
);
