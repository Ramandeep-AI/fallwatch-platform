"""FallWatch analytics dashboard.

Run with: streamlit run dashboard/app.py
Requires the API (uvicorn backend.main:app) and database to be running.
"""
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

import api

st.set_page_config(page_title="FallWatch", page_icon="🛟", layout="wide")

if not api.health_ok():
    st.error(f"Cannot reach the FallWatch API at {api.API_URL}. "
             "Start it with: uvicorn backend.main:app")
    st.stop()

page = st.sidebar.radio("FallWatch",
                        ["Overview", "Events", "Analytics", "Devices", "Alerts"])
st.sidebar.caption(f"API: {api.API_URL}")


def events_dataframe(items):
    if not items:
        return pd.DataFrame()
    df = pd.json_normalize(items)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df[["id", "timestamp", "event_type", "confidence",
               "device.name", "device.location", "person.name"]].rename(
        columns={"device.name": "device", "device.location": "location",
                 "person.name": "person"})


# ---------------- Overview ----------------
if page == "Overview":
    st.title("Overview")
    summary = api.get_summary()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total events", summary["total_events"])
    c2.metric("Events today", summary["events_today"])
    c3.metric("Falls today", summary["falls_today"],
              delta_color="inverse")
    c4.metric("Avg confidence", summary["avg_confidence"] or "—")

    st.subheader("Recent events")
    df = events_dataframe(api.get_events(limit=10)["items"])
    if df.empty:
        st.info("No events yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("Refresh"):
        st.rerun()

# ---------------- Events ----------------
elif page == "Events":
    st.title("Events")

    devices = {d["name"]: d["id"] for d in api.get_devices()}
    f1, f2, f3 = st.columns(3)
    device_name = f1.selectbox("Device", ["All"] + list(devices))
    event_type = f2.selectbox("Type", ["All", "fall", "activity"])
    min_conf = f3.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)

    filters = {"limit": 200}
    if device_name != "All":
        filters["device_id"] = devices[device_name]
    if event_type != "All":
        filters["event_type"] = event_type

    data = api.get_events(**filters)
    df = events_dataframe(data["items"])
    if not df.empty:
        df = df[df["confidence"] >= min_conf]

    st.caption(f"{len(df)} of {data['total']} events shown")
    st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------- Analytics ----------------
elif page == "Analytics":
    st.title("Analytics")
    days = st.slider("Time range (days)", 7, 90, 30)

    daily = pd.DataFrame(api.get_daily(days))
    hourly = pd.DataFrame(api.get_hourly(days))

    if daily.empty:
        st.info("No events in the selected range.")
    else:
        left, right = st.columns(2)
        with left:
            fig = px.line(daily, x="date", y=["count", "falls"],
                          title="Events per day",
                          labels={"value": "events", "variable": ""})
            st.plotly_chart(fig, use_container_width=True)
        with right:
            fig = px.bar(hourly, x="hour", y="count",
                         title="Events by hour of day")
            st.plotly_chart(fig, use_container_width=True)

        df = events_dataframe(api.get_events(limit=500)["items"])
        left2, right2 = st.columns(2)
        with left2:
            fig = px.histogram(df, x="confidence", nbins=20,
                               title="Confidence distribution")
            st.plotly_chart(fig, use_container_width=True)
        with right2:
            fig = px.pie(df, names="location", title="Events by location")
            st.plotly_chart(fig, use_container_width=True)

# ---------------- Alerts ----------------
elif page == "Alerts":
    st.title("Alerts")

    open_alerts = api.get_alerts(acknowledged=False)
    st.subheader(f"Open alerts ({len(open_alerts)})")
    if not open_alerts:
        st.success("No unacknowledged alerts.")
    for a in open_alerts:
        ev = a["event"]
        col1, col2 = st.columns([5, 1])
        col1.error(
            f"**Fall** at {ev['device']['location']} — "
            f"{ev['timestamp'][:19].replace('T', ' ')} · "
            f"confidence {ev['confidence']:.2f} · via {a['alert_type']}"
            + (f" · {ev['person']['name']}" if ev.get("person") else ""))
        if col2.button("Acknowledge", key=f"ack-{a['id']}"):
            api.acknowledge_alert(a["id"])
            st.rerun()

    st.subheader("History")
    done = api.get_alerts(acknowledged=True)
    if done:
        df = pd.json_normalize(done)[
            ["id", "sent_at", "alert_type", "acknowledged_at",
             "event.device.location", "event.confidence"]].rename(
            columns={"event.device.location": "location",
                     "event.confidence": "confidence"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("No acknowledged alerts yet.")

# ---------------- Devices ----------------
elif page == "Devices":
    st.title("Devices")
    events = api.get_events(limit=500)["items"]
    last_seen = {}
    for e in events:  # newest first
        last_seen.setdefault(e["device"]["id"], e["timestamp"])

    rows = []
    now = datetime.now(timezone.utc)
    for d in api.get_devices():
        seen = last_seen.get(d["id"])
        if seen:
            # Python 3.10's fromisoformat cannot parse a trailing 'Z'
            seen_dt = datetime.fromisoformat(seen.replace("Z", "+00:00"))
            age = now - seen_dt
            hours = age.total_seconds() / 3600
            seen_text = f"{hours:.1f} h ago"
            health = "🟢 active" if hours < 24 else "🟠 quiet"
        else:
            seen_text, health = "never", "🔴 no data"
        rows.append({"device": d["name"], "location": d["location"],
                     "status": d["status"], "last event": seen_text,
                     "health": health})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
