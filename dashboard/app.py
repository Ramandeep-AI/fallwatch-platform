"""FallWatch analytics dashboard.

Run from the repository root: streamlit run dashboard/app.py
Requires the API (uvicorn backend.main:app) and database to be running.
"""
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import api

st.set_page_config(page_title="FallWatch", page_icon="🛟", layout="wide")

ACCENT = "#36d7b7"
DANGER = "#f87171"
AMBER = "#fbbf24"
INDIGO = "#818cf8"
MONO = "ui-monospace, 'SF Mono', Menlo, monospace"
# px bakes colors into traces at creation time, so the palette must be set
# here rather than via layout.colorway
px.defaults.color_discrete_sequence = [ACCENT, DANGER, INDIGO, AMBER]

st.markdown(f"""
<style>
.block-container {{ padding-top: 3.8rem; padding-bottom: 3rem; }}

.stButton > button {{
    border: 1px solid #1d3a34; background: rgba(54,215,183,0.05);
    color: #9fb8b2; font-family: {MONO}; font-size: 0.8rem;
}}
.stButton > button:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
div.stButton {{ margin-top: 10px; }}

/* breathing room between sections */
h3, h4 {{ margin-top: 1.5rem !important; }}

/* tables scroll inside their own container, never the page */
.fw-tablewrap {{ overflow-x: auto; }}
.fw-tablewrap table.fw-table {{ min-width: 660px; }}

.fw-foot {{ display: flex; flex-wrap: wrap; gap: 10px; row-gap: 8px;
            align-items: center; justify-content: space-between;
            margin-top: 10px; }}
.fw-foot .note {{ font-family: {MONO}; font-size: 0.75rem; color: #5c6f6b; }}

.fw-kicker {{
    font-family: {MONO}; font-size: 0.72rem; letter-spacing: 0.22em;
    text-transform: uppercase; color: {ACCENT}; margin-bottom: 2px;
}}
.fw-title {{ font-size: 2.1rem; font-weight: 700; color: #f0f6f4;
             line-height: 1.15; margin-bottom: 2px; }}
.fw-sub {{ color: #5c6f6b; font-size: 0.95rem; margin-bottom: 10px; }}

.fw-live {{
    display: inline-flex; align-items: center; gap: 8px;
    font-family: {MONO}; font-size: 0.78rem; color: {ACCENT};
    border: 1px solid #1d3a34; border-radius: 999px; padding: 5px 14px;
    background: rgba(54,215,183,0.06);
}}
.fw-live .clock {{ color: #9fb8b2; }}

.fw-brand {{ display: flex; gap: 10px; align-items: center; }}
.fw-brand .name {{ font-size: 1.35rem; font-weight: 700; color: #f0f6f4; }}
.fw-brand .name span {{ color: {ACCENT}; }}
.fw-brand .tag {{ font-family: {MONO}; font-size: 0.62rem;
                  letter-spacing: 0.22em; color: #5c6f6b; }}

.fw-sysnormal {{
    display: inline-block; font-family: {MONO}; font-size: 0.7rem;
    letter-spacing: 0.12em; border-radius: 999px; padding: 6px 14px;
    color: {ACCENT}; border: 1px solid #1d3a34; background: rgba(54,215,183,0.06);
}}
.fw-sysalert {{
    display: inline-block; font-family: {MONO}; font-size: 0.7rem;
    letter-spacing: 0.12em; border-radius: 999px; padding: 6px 14px;
    color: {DANGER}; border: 1px solid #4c2430; background: rgba(248,113,113,0.08);
}}
.fw-sidecaption {{ font-family: {MONO}; font-size: 0.7rem; color: #5c6f6b;
                   margin-top: 8px; }}

.fw-panel {{
    background: linear-gradient(165deg, #0f1a1a 0%, #0b1213 100%);
    border: 1px solid #17282a; border-radius: 16px; padding: 18px 20px;
}}

.fw-stat {{
    display: flex; align-items: center; gap: 14px;
    background: linear-gradient(165deg, #0f1a1a 0%, #0b1213 100%);
    border: 1px solid #17282a; border-radius: 14px;
    padding: 14px 16px; margin-bottom: 10px;
}}
.fw-stat .ico {{
    width: 42px; height: 42px; border-radius: 11px; flex: none;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.15rem; background: rgba(54,215,183,0.08);
    border: 1px solid #1d3a34;
}}
.fw-stat .ico.red {{ background: rgba(248,113,113,0.08); border-color: #4c2430; }}
.fw-stat .lbl {{ font-family: {MONO}; font-size: 0.66rem;
                 letter-spacing: 0.18em; color: #5c6f6b; }}
.fw-stat .val {{ font-family: {MONO}; font-size: 1.65rem; font-weight: 700;
                 color: #f0f6f4; line-height: 1.2; }}
.fw-stat .chip {{
    margin-left: auto; font-family: {MONO}; font-size: 0.72rem;
    border-radius: 999px; padding: 3px 10px; color: #9fb8b2;
    border: 1px solid #213436; background: #101c1d;
}}

table.fw-table {{ width: 100%; border-collapse: collapse; }}
table.fw-table th {{
    font-family: {MONO}; font-size: 0.66rem; letter-spacing: 0.18em;
    text-transform: uppercase; color: #5c6f6b; text-align: left;
    padding: 8px 12px; border-bottom: 1px solid #17282a;
}}
table.fw-table td {{
    padding: 10px 12px; border-bottom: 1px solid #121e20;
    color: #c8d8d4; font-size: 0.88rem;
}}
table.fw-table td.mono {{ font-family: {MONO}; font-size: 0.8rem; }}
.fw-dot {{ display: inline-block; width: 8px; height: 8px;
           border-radius: 50%; margin-right: 7px; }}
.fw-bar {{ display: inline-block; width: 110px; height: 5px;
           background: #17282a; border-radius: 3px; vertical-align: middle;
           margin-right: 10px; }}
.fw-bar i {{ display: block; height: 5px; border-radius: 3px;
             background: {ACCENT}; }}

.fw-alert {{
    background: #170f13; border: 1px solid #43202e;
    border-left: 5px solid {DANGER}; border-radius: 12px;
    padding: 14px 18px; margin-bottom: 6px; color: #cbd5d1;
}}
.fw-alert b {{ color: #fda4af; }}
.fw-allclear {{
    display: flex; gap: 16px; align-items: center;
    background: #0d1a17; border: 1px solid #1d4038; border-radius: 14px;
    padding: 18px 22px;
}}
.fw-allclear .tick {{
    width: 44px; height: 44px; border-radius: 12px; flex: none;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.3rem; background: rgba(54,215,183,0.1);
    border: 1px solid #1d3a34;
}}
.fw-allclear .t1 {{ font-weight: 700; color: #f0f6f4; }}
.fw-allclear .t2 {{ color: #5c6f6b; font-size: 0.9rem; }}

.fw-cam {{
    background: linear-gradient(165deg, #0f1a1a 0%, #0b1213 100%);
    border: 1px solid #17282a; border-radius: 16px; overflow: hidden;
    margin-bottom: 14px;
}}
.fw-cam .view {{
    height: 84px; position: relative;
    background: radial-gradient(ellipse at 60% 0%, #122224 0%, #0b1213 70%);
    background-image: linear-gradient(#122022 1px, transparent 1px),
                      linear-gradient(90deg, #122022 1px, transparent 1px);
    background-size: 22px 22px;
    border-bottom: 1px solid #17282a;
}}
.fw-cam .view .rec {{
    position: absolute; top: 10px; left: 14px;
    font-family: {MONO}; font-size: 0.72rem; color: #9fb8b2;
}}
.fw-cam .view .rec i {{ display: inline-block; width: 8px; height: 8px;
    border-radius: 50%; margin-right: 7px; }}
.fw-cam .body {{ padding: 14px 18px; }}
.fw-cam .name {{ font-family: {MONO}; font-weight: 700; color: #f0f6f4; }}
.fw-cam .loc {{ color: #5c6f6b; font-size: 0.85rem; margin-bottom: 8px; }}
.fw-cam .foot {{ display: flex; justify-content: space-between;
                 align-items: center; margin-top: 8px; }}
.fw-pill {{ font-family: {MONO}; font-size: 0.68rem; letter-spacing: 0.1em;
    border-radius: 999px; padding: 4px 12px; }}
.fw-pill.ok {{ color: {ACCENT}; border: 1px solid #1d3a34; }}
.fw-pill.warn {{ color: {AMBER}; border: 1px solid #4d3d1a; }}
.fw-pill.bad {{ color: {DANGER}; border: 1px solid #4c2430; }}
.fw-cam .ago {{ font-family: {MONO}; font-size: 0.75rem; color: #5c6f6b; }}
</style>
""", unsafe_allow_html=True)

if not api.health_ok():
    st.error(f"Cannot reach the FallWatch API at {api.API_URL}. "
             "Start it with: uvicorn backend.main:app")
    st.stop()

SHIELD = f"""<svg width="34" height="34" viewBox="0 0 24 24" fill="none">
<path d="M12 2l8 3v6c0 5-3.4 9.2-8 11-4.6-1.8-8-6-8-11V5l8-3z"
 stroke="{ACCENT}" stroke-width="1.4" fill="rgba(54,215,183,0.06)"/>
<polyline points="6.5,12.5 9.5,12.5 11,9.5 13,15 14.5,12.5 17.5,12.5"
 stroke="{ACCENT}" stroke-width="1.3" fill="none" stroke-linecap="round"/>
</svg>"""

with st.sidebar:
    st.markdown(f"""<div class="fw-brand">{SHIELD}<div>
<div class="name">Fall<span>Watch</span></div>
<div class="tag">FALL MONITORING</div></div></div>""", unsafe_allow_html=True)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    page = st.radio("Monitor",
                    ["Overview", "Events", "Analytics", "Devices", "Alerts"],
                    label_visibility="collapsed")
    st.divider()

    @st.fragment(run_every="5s")
    def system_status():
        n_open = len(api.get_alerts(acknowledged=False))
        n_devices = len(api.get_devices())
        if n_open == 0:
            st.markdown('<span class="fw-sysnormal">● ALL SYSTEMS NORMAL</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="fw-sysalert">● {n_open} OPEN '
                        f'ALERT{"S" if n_open > 1 else ""}</span>',
                        unsafe_allow_html=True)
        st.markdown(f'<div class="fw-sidecaption">{n_devices} cameras · '
                    f'{n_open} open alerts</div>', unsafe_allow_html=True)

    system_status()


def header(kicker, title, sub=""):
    st.markdown(f'<div class="fw-kicker">{kicker}</div>'
                f'<div class="fw-title">{title}</div>'
                + (f'<div class="fw-sub">{sub}</div>' if sub else ""),
                unsafe_allow_html=True)


def style_fig(fig, height=330):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9fb8b2"), height=height,
        margin=dict(l=10, r=10, t=64, b=10),
        title_font=dict(size=15, color="#f0f6f4"),
        legend=dict(orientation="h", y=1.18, x=1, xanchor="right", title=None),
    )
    fig.update_xaxes(gridcolor="#152225", zeroline=False)
    fig.update_yaxes(gridcolor="#152225", zeroline=False)
    return fig


def chart_title(title, sub):
    return dict(text=f"{title}<br><sup style='color:#5c6f6b'>{sub}</sup>")


def parse_ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def time_ago(iso: str) -> str:
    minutes = (datetime.now(timezone.utc) - parse_ts(iso)).total_seconds() / 60
    if minutes < 1:
        return "just now"
    if minutes < 90:
        return f"{minutes:.0f} min ago"
    return f"{minutes / 60:.1f} h ago"


def duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds // 60:.0f}m {seconds % 60:.0f}s"
    return f"{seconds / 3600:.1f} h"


def events_table_html(items):
    rows = []
    for e in items:
        color = DANGER if e["event_type"] == "fall" else ACCENT
        person = e["person"]["name"] if e.get("person") else "—"
        ts = parse_ts(e["timestamp"]).strftime("%d %b · %H:%M:%S")
        rows.append(
            f'<tr><td class="mono">{ts}</td>'
            f'<td><span class="fw-dot" style="background:{color}"></span>'
            f'<span style="color:{color}">{e["event_type"]}</span></td>'
            f'<td><span class="fw-bar"><i style="width:{e["confidence"]*100:.0f}%">'
            f'</i></span><span class="mono" style="font-family:monospace">'
            f'{e["confidence"]:.2f}</span></td>'
            f'<td class="mono">{e["device"]["name"]}</td>'
            f'<td>{e["device"]["location"]}</td><td>{person}</td></tr>')
    return ('<div class="fw-tablewrap"><table class="fw-table"><thead><tr>'
            '<th>Time</th><th>Type</th><th>Confidence</th><th>Camera</th>'
            '<th>Location</th><th>Resident</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")


def stat_card(icon, label, value, chip, red=False):
    return (f'<div class="fw-stat"><div class="ico{" red" if red else ""}">'
            f'{icon}</div><div><div class="lbl">{label}</div>'
            f'<div class="val">{value}</div></div>'
            f'<div class="chip">{chip}</div></div>')


def monitor_panel(alarm: bool):
    color = DANGER if alarm else ACCENT
    label = "FALL DETECTED · check resident" if alarm else "Monitoring · all clear"
    figure_color = DANGER if alarm else ACCENT
    # stick figure: standing when clear, horizontal when a fall alert is open
    if alarm:
        person = f"""<g stroke="{figure_color}" stroke-width="2.4"
          stroke-linecap="round" transform="translate(215,96) rotate(90)">
          <circle cx="0" cy="-26" r="9" fill="none"/>
          <line x1="0" y1="-17" x2="0" y2="12"/>
          <line x1="0" y1="-8" x2="-16" y2="4"/><line x1="0" y1="-8" x2="16" y2="4"/>
          <line x1="0" y1="12" x2="-13" y2="34"/><line x1="0" y1="12" x2="13" y2="34"/>
          </g>"""
    else:
        person = f"""<g stroke="{figure_color}" stroke-width="2.4"
          stroke-linecap="round" transform="translate(215,88)">
          <circle cx="0" cy="-30" r="10" fill="none"/>
          <line x1="0" y1="-20" x2="0" y2="14"/>
          <line x1="0" y1="-9" x2="-19" y2="5"/><line x1="0" y1="-9" x2="19" y2="5"/>
          <line x1="0" y1="14" x2="-15" y2="42"/><line x1="0" y1="14" x2="15" y2="42"/>
          </g>"""
    return f"""<div class="fw-panel" style="border-color:{'#4c2430' if alarm else '#17282a'}">
<svg viewBox="0 0 430 160" width="100%" height="222" preserveAspectRatio="xMidYMid meet">
  <polyline points="0,16 60,16 74,4 86,28 98,16 150,16 330,16 344,6 356,22 368,16 430,16"
    stroke="{color}" stroke-width="1.6" fill="none" opacity="0.85"/>
  <rect x="176" y="42" width="78" height="106" rx="10"
    stroke="{figure_color}" stroke-width="1.6" fill="rgba(0,0,0,0.15)"/>
  <rect x="177" y="26" width="76" height="15" rx="7" fill="#0b1213"
    stroke="#17282a" stroke-width="1"/>
  <text x="215" y="37" text-anchor="middle" font-family="{MONO}"
    font-size="10" fill="{color}">resident status</text>
  {person}
</svg>
<div class="fw-foot">
  <span class="fw-pill {'bad' if alarm else 'ok'}">● {label}</span>
  <span class="note">edge inference · no video leaves the device</span>
</div></div>"""


EVENT_BADGES = {"fall": "🔴 fall", "activity": "🟢 activity"}
TABLE_CONFIG = {
    "confidence": st.column_config.ProgressColumn(
        "confidence", min_value=0.0, max_value=1.0, format="%.2f"),
    "timestamp": st.column_config.DatetimeColumn(
        "time", format="DD MMM · HH:mm:ss"),
}


def events_dataframe(items):
    if not items:
        return pd.DataFrame()
    df = pd.json_normalize(items)
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
    df["event_type"] = df["event_type"].map(lambda t: EVENT_BADGES.get(t, t))
    return df[["timestamp", "event_type", "confidence",
               "device.name", "device.location", "person.name"]].rename(
        columns={"device.name": "device", "device.location": "location",
                 "person.name": "person"})


# ---------------- Overview ----------------
if page == "Overview":

    @st.fragment(run_every="5s")
    def live_overview():
        summary = api.get_summary()
        open_alerts = api.get_alerts(acknowledged=False)
        daily = {d["date"]: d for d in api.get_daily(2)}
        today = datetime.now(timezone.utc).date()
        yest = daily.get(str(today - pd.Timedelta(days=1)), {})

        k1, k2 = st.columns([3, 1], vertical_alignment="center")
        with k1:
            header("LIVE · REFRESHES EVERY 5S", "Overview")
        with k2:
            st.markdown(f'<div style="text-align:right"><span class="fw-live">'
                        f'● LIVE <span class="clock">'
                        f'{datetime.now(timezone.utc):%H:%M:%S} UTC</span>'
                        f'</span></div>', unsafe_allow_html=True)

        hero, rail = st.columns([1.7, 1], gap="medium")
        with hero:
            st.markdown(monitor_panel(alarm=len(open_alerts) > 0),
                        unsafe_allow_html=True)
            if st.button("▶ Trigger demo fall", use_container_width=True,
                         help="Posts a demonstration fall event through the "
                         "real ingestion pipeline — watch the monitor react, "
                         "then acknowledge it on the Alerts page"):
                api.create_demo_event()
        with rail:
            d_falls = summary["falls_today"] - yest.get("falls", 0)
            d_events = summary["events_today"] - yest.get("count", 0)
            falls_chip = ("→ 0" if d_falls == 0
                          else f"{'↑' if d_falls > 0 else '↓'} {abs(d_falls)}")
            events_chip = ("→ 0" if d_events == 0
                           else f"{'↑' if d_events > 0 else '↓'} {abs(d_events)}")
            st.markdown(
                stat_card("🚨", "FALLS TODAY", summary["falls_today"],
                          falls_chip, red=True)
                + stat_card("〰️", "EVENTS TODAY", summary["events_today"],
                            events_chip)
                + stat_card("✅", "AVG CONFIDENCE",
                            summary["avg_confidence"] or "—", "all time")
                + stat_card("🗂", "TOTAL EVENTS", summary["total_events"],
                            "all time"),
                unsafe_allow_html=True)

        st.markdown("#### Recent events")
        items = api.get_events(limit=8)["items"]
        if items:
            st.markdown(events_table_html(items), unsafe_allow_html=True)
        else:
            st.info("No events yet.")
        st.markdown(f'<div class="fw-sidecaption">last updated '
                    f'{datetime.now(timezone.utc):%H:%M:%S} UTC · '
                    f'deltas vs yesterday · times in UTC</div>',
                    unsafe_allow_html=True)

    live_overview()

# ---------------- Events ----------------
elif page == "Events":
    header("FULL HISTORY", "Events", "search and filter every detection")

    devices = {d["name"]: d["id"] for d in api.get_devices()}
    f1, f2, f3 = st.columns(3)
    device_name = f1.selectbox("Camera", ["All"] + list(devices))
    event_type = f2.selectbox("Type", ["All", "fall", "activity"])
    min_conf = f3.slider("Minimum confidence", 0.0, 1.0, 0.0, 0.05)

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
    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config=TABLE_CONFIG, height=520)

# ---------------- Analytics ----------------
elif page == "Analytics":
    header("TRENDS & PATTERNS", "Analytics")
    days = st.slider("Time range (days)", 7, 90, 30)

    daily = pd.DataFrame(api.get_daily(days))
    hourly = pd.DataFrame(api.get_hourly(days))

    if daily.empty:
        st.info("No events in the selected range.")
    else:
        left, right = st.columns(2, gap="large")
        with left:
            fig = go.Figure()
            fig.add_scatter(x=daily["date"], y=daily["count"], name="events",
                            mode="lines+markers", line_shape="spline",
                            line=dict(color=ACCENT, width=2.5),
                            fill="tozeroy", fillcolor="rgba(54,215,183,0.12)")
            fig.add_scatter(x=daily["date"], y=daily["falls"], name="falls",
                            mode="lines+markers", line_shape="spline",
                            line=dict(color=DANGER, width=2.5))
            fig.update_layout(title=chart_title("Events per day", "total vs falls"))
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with right:
            fig = px.bar(hourly, x="hour", y="count")
            fig.update_layout(title=chart_title("Events by hour of day",
                                                "when incidents cluster"))
            st.plotly_chart(style_fig(fig), use_container_width=True)

        st.markdown('<div style="height:26px"></div>', unsafe_allow_html=True)
        df = pd.json_normalize(api.get_events(limit=500)["items"])
        left2, right2 = st.columns(2, gap="large")
        with left2:
            fig = px.histogram(df, x="confidence", nbins=20,
                               color_discrete_sequence=[INDIGO])
            fig.update_layout(title=chart_title("Confidence distribution",
                                                "model certainty across events"))
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with right2:
            fig = px.pie(df, names="device.location", hole=0.6)
            fig.update_layout(title=chart_title("Events by location",
                                                "share by room"))
            st.plotly_chart(style_fig(fig), use_container_width=True)

# ---------------- Devices ----------------
elif page == "Devices":
    header("CAMERA FLEET HEALTH", "Devices")
    events = api.get_events(limit=500)["items"]
    last_seen = {}
    per_device_daily = {}
    for e in events:  # newest first
        last_seen.setdefault(e["device"]["id"], e["timestamp"])
        day = e["timestamp"][:10]
        per_device_daily.setdefault(e["device"]["id"], {})
        per_device_daily[e["device"]["id"]][day] = \
            per_device_daily[e["device"]["id"]].get(day, 0) + 1

    def sparkline(counts_by_day):
        """Tiny SVG polyline of the last 10 days of real event counts."""
        today = datetime.now(timezone.utc).date()
        days = [str(today - pd.Timedelta(days=i)) for i in range(9, -1, -1)]
        vals = [counts_by_day.get(d, 0) for d in days]
        peak = max(max(vals), 1)
        pts = " ".join(f"{i * 24},{34 - v / peak * 28}"
                       for i, v in enumerate(vals))
        return (f'<svg viewBox="0 0 216 38" width="100%" height="34">'
                f'<polyline points="{pts}" stroke="{ACCENT}" stroke-width="1.6"'
                f' fill="none" opacity="0.9"/></svg>')

    cols = st.columns(3)
    for col, d in zip(cols * 3, api.get_devices()):
        seen = last_seen.get(d["id"])
        if seen:
            hours = (datetime.now(timezone.utc) - parse_ts(seen)).total_seconds() / 3600
            pill = ('<span class="fw-pill ok">● ACTIVE</span>' if hours < 24
                    else '<span class="fw-pill warn">● QUIET</span>')
            ago = f"last event {time_ago(seen)}"
            strip = (f'<i style="background:{ACCENT}"></i>reporting'
                     if hours < 24 else '<i style="background:#5c6f6b"></i>idle')
        else:
            pill = '<span class="fw-pill bad">● NO DATA</span>'
            ago = "no events"
            strip = '<i style="background:#5c6f6b"></i>no events'
        col.markdown(f"""
<div class="fw-cam">
  <div class="view"><span class="rec">{strip}</span></div>
  <div class="body">
    <div class="name">{d["name"]}</div>
    <div class="loc">{d["location"]}</div>
    {sparkline(per_device_daily.get(d["id"], {}))}
    <div class="foot">{pill}<span class="ago">{ago}</span></div>
  </div>
</div>""", unsafe_allow_html=True)

# ---------------- Alerts ----------------
elif page == "Alerts":
    header("CAREGIVER ACKNOWLEDGEMENT", "Alerts")

    open_alerts = api.get_alerts(acknowledged=False)
    st.markdown(f"#### Open · {len(open_alerts)}")
    if not open_alerts:
        st.markdown("""<div class="fw-allclear"><div class="tick">✓</div><div>
<div class="t1">All clear</div>
<div class="t2">No unacknowledged alerts. Every resident is accounted for.</div>
</div></div>""", unsafe_allow_html=True)
    for a in open_alerts:
        ev = a["event"]
        who = f" · {ev['person']['name']}" if ev.get("person") else ""
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        c1.markdown(f"""
<div class="fw-alert">🚨 <b>Fall — {ev["device"]["location"]}</b><br>
{time_ago(a["sent_at"])} · device {ev["device"]["name"]} ·
confidence {ev["confidence"]:.2f} · via {a["alert_type"]}{who}</div>""",
                    unsafe_allow_html=True)
        if c2.button("Acknowledge", key=f"ack-{a['id']}", type="primary"):
            api.acknowledge_alert(a["id"])
            st.rerun()

    st.markdown("#### History")
    done = api.get_alerts(acknowledged=True)
    if done:
        rows = []
        for a in done:
            response = (parse_ts(a["acknowledged_at"])
                        - parse_ts(a["sent_at"])).total_seconds()
            conf = a["event"]["confidence"]
            rows.append(
                f'<tr><td class="mono">{parse_ts(a["sent_at"]):%d %b · %H:%M:%S}</td>'
                f'<td class="mono">{a["alert_type"]}</td>'
                f'<td class="mono">{parse_ts(a["acknowledged_at"]):%d %b · %H:%M:%S}</td>'
                f'<td class="mono" style="color:{ACCENT}">✓ {duration(response)}</td>'
                f'<td>{a["event"]["device"]["location"]}</td>'
                f'<td><span class="fw-bar"><i style="width:{conf*100:.0f}%"></i>'
                f'</span><span class="mono">{conf:.2f}</span></td></tr>')
        st.markdown('<div class="fw-tablewrap"><table class="fw-table">'
                    '<thead><tr><th>Sent</th>'
                    '<th>Channel</th><th>Acknowledged</th><th>Response</th>'
                    '<th>Location</th><th>Confidence</th></tr></thead><tbody>'
                    + "".join(rows) + "</tbody></table></div>",
                    unsafe_allow_html=True)
        st.markdown('<div class="fw-sidecaption">times shown in UTC</div>',
                    unsafe_allow_html=True)
    else:
        st.caption("No acknowledged alerts yet.")
