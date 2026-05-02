"""
dashboard.py — Multi-club Padel Court Utilisation Dashboard
============================================================
Reads from GitHub Gist. Club selector in sidebar filters all views.
"""

import os
import json
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo

AEST = ZoneInfo("Australia/Sydney")

GIST_RAW_URL = os.environ.get("GIST_RAW_URL", "") or st.secrets.get("GIST_RAW_URL", "")

# Club display names — must match keys in CLUBS dict in the tracker
CLUB_DISPLAY_NAMES = {
    "south_east_padel":    "South East Padel",
    "game4padel_richmond": "Game4Padel Richmond",
}

# Court short names per club
COURT_LABELS = {
    "south_east_padel": {
        "4a5fb5fe-139f-40b0-85e7-634c705d7284": "Court 1",
        "6a01f11b-3f57-4e81-bf0d-c1359d82caef": "Court 2",
        "e60b3a03-4c04-4021-a531-626d7d973135": "Court 3",
    },
    "game4padel_richmond": {},  # will fall back to truncated UUID until courts are observed
}

def court_name(club_id: str, court_id: str) -> str:
    label = COURT_LABELS.get(club_id, {}).get(court_id)
    return label if label else court_id[:8] + "…"

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG + STYLING
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Padel Court Analytics",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
html, body, [class*="css"] { font-family: 'DM Mono', monospace; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; letter-spacing: -0.02em; }
.metric-card {
    background: #0f1117; border: 1px solid #2a2d3a;
    border-radius: 8px; padding: 1.2rem 1.5rem; text-align: center;
}
.metric-value { font-family: 'Syne', sans-serif; font-size: 2.4rem; font-weight: 800; color: #00ff9d; line-height: 1; }
.metric-label { font-size: 0.72rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 0.4rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def load_data() -> dict:
    if not GIST_RAW_URL:
        return {}
    resp = requests.get(
        GIST_RAW_URL,
        headers={
            "Accept": "text/plain, application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "padel-tracker-dashboard/1.0",
        },
        timeout=15,
    )
    resp.raise_for_status()
    if "html" in resp.headers.get("Content-Type", ""):
        st.error("GitHub returned HTML instead of JSON. Check GIST_RAW_URL.")
        return {}
    try:
        return resp.json()
    except json.JSONDecodeError:
        st.info("Gist found but no tracking data yet — poller may not have run.")
        return {}

def slots_to_df(slots: list, club_id: str) -> pd.DataFrame:
    if not slots:
        return pd.DataFrame()
    df = pd.DataFrame(slots)
    df["court_name"] = df["court_id"].apply(lambda cid: court_name(club_id, cid))
    return df

# ─────────────────────────────────────────────────────────────────────────────
# LOAD + GUARD
# ─────────────────────────────────────────────────────────────────────────────

data = load_data()

if not data or not data.get("clubs"):
    st.title("🎾 Padel Court Analytics")
    if not GIST_RAW_URL:
        st.error("GIST_RAW_URL not configured. Set it in Streamlit secrets.")
    else:
        st.info("No data yet — poller hasn't run or Gist is empty.")
    st.stop()

exported_at = data.get("exported_at", "")
clubs_data  = data.get("clubs", {})

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎾 Padel Tracker")
    if exported_at:
        try:
            dt = datetime.fromisoformat(exported_at)
            st.caption(f"Last updated: {dt.strftime('%d %b %Y %H:%M')} AEST")
        except Exception:
            st.caption(f"Last updated: {exported_at}")

    st.markdown("---")

    # ── Club selector
    available_clubs = list(clubs_data.keys())
    selected_club = st.selectbox(
        "Select club",
        options=available_clubs,
        format_func=lambda c: CLUB_DISPLAY_NAMES.get(c, c),
    )

    club_data = clubs_data.get(selected_club, {})
    available_dates = club_data.get("available_dates", [])

    if not available_dates:
        st.warning("No data for this club yet.")
        st.stop()

    # ── Date selector
    selected_date = st.selectbox(
        "Select date",
        options=available_dates,
        format_func=lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%a %d %b %Y"),
    )

    st.markdown("---")
    st.markdown("##### Recent polls")
    for p in data.get("recent_polls", [])[:6]:
        icon = "✅" if p.get("success") else "❌"
        club = CLUB_DISPLAY_NAMES.get(p.get("club_id", ""), p.get("club_id", ""))
        ts   = p.get("polled_at", "")[:16].replace("T", " ")
        st.markdown(f"{icon} `{ts}` {club}")

    st.markdown("---")
    st.caption("Auto-refreshes every 2 min · Times in AEST")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

club_display = CLUB_DISPLAY_NAMES.get(selected_club, selected_club)
st.markdown(f"# {club_display}")
date_label = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%A, %d %B %Y")
st.markdown(f"Showing data for **{date_label}**")

raw_slots = club_data.get("slots_by_date", {}).get(selected_date, [])
slots_df  = slots_to_df(raw_slots, selected_club)

trend_rows = club_data.get("utilisation_trend", [])
trend_df   = pd.DataFrame(trend_rows) if trend_rows else pd.DataFrame()

# ── Top metrics ──────────────────────────────────────────────────────────────

if not slots_df.empty:
    finalised       = slots_df[slots_df["finalised"].astype(bool)]
    still_open      = slots_df[slots_df["status"] == "available"]
    total_booked    = (finalised["status"] == "booked").sum()
    total_unbooked  = (finalised["status"] == "went_unbooked").sum()
    total_finalised = total_booked + total_unbooked
    total_available = len(still_open)
    n_courts        = slots_df["court_id"].nunique()
    util_pct        = round(total_booked / total_finalised * 100, 1) if total_finalised > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, val, label in [
        (c1, f"{util_pct}%",                          "Utilisation (finalised)"),
        (c2, f"{round(total_booked*30/60,1)}h",       "Booked hours"),
        (c3, f"{round(total_unbooked*30/60,1)}h",     "Went unbooked"),
        (c4, f"{round(total_available*30/60,1)}h",    "Still available"),
        (c5, str(n_courts),                            "Courts tracked"),
    ]:
        with col:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Court timeline heatmap ────────────────────────────────────────────────────

st.markdown("### Court Timeline")
st.caption("Each cell = one 30-min block  ·  🔴 Booked  🟢 Went unbooked  🔵 Still available  ")

if not slots_df.empty:
    status_to_num = {"booked": 0, "went_unbooked": 1, "available": 2}
    pivot = slots_df.pivot_table(
        index="court_name", columns="block_time", values="status", aggfunc="first"
    )
    pivot_num = pivot.map(lambda x: status_to_num.get(x, 0) if pd.notna(x) else 0)

    fig = go.Figure(data=go.Heatmap(
        z=pivot_num.values,
        x=pivot_num.columns.tolist(),
        y=pivot_num.index.tolist(),
        colorscale=[
            [0,   "#ff4d6d"],
            [0.5, "#00ff9d"],
            [1.0, "#38bdf8"],
        ],
        showscale=False,
        hovertemplate="<b>%{y}</b><br>%{x}<br>%{text}<extra></extra>",
        text=pivot.values,
        xgap=2, ygap=4,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono", color="#9ca3af"),
        height=max(180, 90 * len(pivot_num.index)),
        margin=dict(l=10, r=10, t=20, b=40),
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No slot data for this date yet.")

st.markdown("---")

# ── Per-court bar chart ───────────────────────────────────────────────────────

st.markdown("### Per-Court Breakdown")

if not slots_df.empty:
    fin = slots_df[slots_df["finalised"].astype(bool)].copy()
    if not fin.empty:
        summary = fin.groupby(["court_name", "status"]).size().reset_index(name="blocks")
        summary["hours"] = summary["blocks"] * 30 / 60
        fig2 = px.bar(
            summary, x="court_name", y="hours", color="status",
            color_discrete_map={"booked": "#ff4d6d", "went_unbooked": "#00ff9d"},
            labels={"court_name": "", "hours": "Hours", "status": "Status"},
            barmode="stack",
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Mono", color="#9ca3af"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=320, margin=dict(l=10, r=10, t=40, b=20),
        )
        fig2.update_xaxes(showgrid=False)
        fig2.update_yaxes(gridcolor="#1f2937")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No finalised slots yet for this date.")

st.markdown("---")

# ── Utilisation trend ─────────────────────────────────────────────────────────

st.markdown("### Utilisation Trend")

if not trend_df.empty and len(trend_df) > 1:
    trend_df["query_date"] = pd.to_datetime(trend_df["query_date"])
    trend_df = trend_df.sort_values("query_date")
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=trend_df["query_date"], y=trend_df["utilisation_pct"],
        mode="lines+markers", line=dict(color="#00ff9d", width=2),
        marker=dict(size=6), fill="tozeroy", fillcolor="rgba(0,255,157,0.08)",
    ))
    fig3.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono", color="#9ca3af"),
        yaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#1f2937"),
        xaxis=dict(showgrid=False),
        height=280, margin=dict(l=10, r=10, t=20, b=20), showlegend=False,
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Trend appears once data spans multiple days.")

st.markdown("---")

# ── Raw data ──────────────────────────────────────────────────────────────────

with st.expander("📋 Raw slot data", expanded=False):
    if not slots_df.empty:
        display = slots_df[[
            "court_name", "block_time", "status", "finalised",
            "first_seen_available", "last_seen_available"
        ]].copy()
        display.columns = ["Court", "Block (AEST)", "Status", "Finalised",
                           "First seen available", "Last seen available"]
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV", data=display.to_csv(index=False),
            file_name=f"padel_slots_{selected_club}_{selected_date}.csv",
            mime="text/csv",
        )