"""
dashboard.py — Padel Court Utilisation Dashboard
==================================================
Streamlit app. Deploy to Streamlit Community Cloud for a free public URL.

Run locally:
  streamlit run dashboard.py

Deploy:
  Push to GitHub → connect repo at https://share.streamlit.io

Environment variable required (set in Streamlit Cloud secrets):
  DATABASE_URL = "postgresql://..."
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import db

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Padel Court Analytics",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded",
)

AEST = ZoneInfo("Australia/Sydney")

# Court ID → friendly short name mapping
# Update these to match your actual court IDs
COURT_LABELS = {
    "4a5fb5fe-139f-40b0-85e7-634c705d7284": "Court 1",
    "6a01f11b-3f57-4e81-bf0d-c1359d82caef": "Court 2",
    "e60b3a03-4c04-4021-a531-626d7d973135": "Court 3",
}

def court_name(court_id: str) -> str:
    return COURT_LABELS.get(court_id, court_id[:8] + "…")

# ─────────────────────────────────────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Mono', monospace;
}
h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
    letter-spacing: -0.02em;
}
.metric-card {
    background: #0f1117;
    border: 1px solid #2a2d3a;
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 2.4rem;
    font-weight: 800;
    color: #00ff9d;
    line-height: 1;
}
.metric-label {
    font-size: 0.72rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.4rem;
}
.status-ok  { color: #00ff9d; }
.status-err { color: #ff4d6d; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CACHED DATA LOADERS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)  # refresh cache every 2 minutes
def load_utilisation_trend():
    rows = db.get_utilisation_by_date()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["query_date"] = pd.to_datetime(df["query_date"])
    df["booked_hours"]   = df["booked_blocks"]   * 30 / 60
    df["unbooked_hours"] = df["unbooked_blocks"]  * 30 / 60
    return df.sort_values("query_date")


@st.cache_data(ttl=120)
def load_slots_for_date(selected_date: date):
    rows = db.get_slot_states_for_date(selected_date)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["block_time"] = df["block_time"].astype(str).str[:5]  # "HH:MM"
    df["court_name"] = df["court_id"].apply(court_name)
    return df


@st.cache_data(ttl=300)
def load_available_dates():
    return db.get_available_dates()


@st.cache_data(ttl=300)
def load_recent_polls():
    return db.get_recent_polls(limit=10)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎾 Padel Tracker")
    st.markdown("---")

    available_dates = load_available_dates()
    if not available_dates:
        st.warning("No data yet. Run the poller first.")
        st.stop()

    selected_date = st.selectbox(
        "Select date",
        options=available_dates,
        format_func=lambda d: d.strftime("%a %d %b %Y"),
    )

    st.markdown("---")
    st.markdown("##### Recent polls")
    polls = load_recent_polls()
    for p in polls[:5]:
        icon = "✅" if p["success"] else "❌"
        ts = p["polled_at"].strftime("%d/%m %H:%M") if p["polled_at"] else "?"
        st.markdown(f"{icon} `{ts}`")

    st.markdown("---")
    st.caption("Auto-refreshes every 2 min · Data in AEST")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("# Padel Court Utilisation")
st.markdown(f"Showing data for **{selected_date.strftime('%A, %d %B %Y')}**")

# ── Load data for selected date
slots_df = load_slots_for_date(selected_date)
trend_df = load_utilisation_trend()

# ─────────────────────────────────────────────────────────────────────────────
# TOP METRICS
# ─────────────────────────────────────────────────────────────────────────────

if not slots_df.empty:
    finalised = slots_df[slots_df["finalised"] == True]
    total_booked   = (finalised["status"] == "booked").sum()
    total_unbooked = (finalised["status"] == "went_unbooked").sum()
    total_finalised = total_booked + total_unbooked
    util_pct = round(total_booked / total_finalised * 100, 1) if total_finalised > 0 else 0
    n_courts = slots_df["court_id"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{util_pct}%</div>
            <div class="metric-label">Overall utilisation</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{round(total_booked * 30 / 60, 1)}h</div>
            <div class="metric-label">Total booked hours</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{round(total_unbooked * 30 / 60, 1)}h</div>
            <div class="metric-label">Total unbooked hours</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{n_courts}</div>
            <div class="metric-label">Courts tracked</div>
        </div>""", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# HEATMAP — court × time block, coloured by status
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("### Court Timeline")
st.caption("Each cell = one 30-min block. Green = available/unbooked, Red = booked, Grey = pending/unknown.")

if not slots_df.empty:
    # Pivot: rows = courts, columns = time blocks, values = status
    status_order = ["booked", "went_unbooked", "available", "unknown"]
    color_map = {
        "booked":        "#ff4d6d",
        "went_unbooked": "#00ff9d",
        "available":     "#38bdf8",
        "unknown":       "#374151",
    }

    pivot = slots_df.pivot_table(
        index="court_name",
        columns="block_time",
        values="status",
        aggfunc="first",
    )

    # Encode status as numeric for heatmap
    status_to_num = {"booked": 1, "went_unbooked": 2, "available": 3, "unknown": 0}
    pivot_num = pivot.applymap(lambda x: status_to_num.get(x, 0) if pd.notna(x) else 0)

    fig_heat = go.Figure(data=go.Heatmap(
        z=pivot_num.values,
        x=pivot_num.columns.tolist(),
        y=pivot_num.index.tolist(),
        colorscale=[
            [0,    "#374151"],   # unknown / grey
            [0.33, "#ff4d6d"],   # booked / red
            [0.66, "#00ff9d"],   # went_unbooked / green
            [1.0,  "#38bdf8"],   # available (future) / blue
        ],
        showscale=False,
        hovertemplate="<b>%{y}</b><br>%{x}<br>Status: %{text}<extra></extra>",
        text=pivot.values,
        xgap=2,
        ygap=4,
    ))
    fig_heat.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono", color="#9ca3af"),
        height=max(180, 80 * len(pivot_num.index)),
        margin=dict(l=10, r=10, t=20, b=40),
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=11)),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # Legend
    st.markdown(
        "🔴 **Booked** &nbsp;|&nbsp; 🟢 **Went unbooked** &nbsp;|&nbsp; 🔵 **Still available (future)** &nbsp;|&nbsp; ⬛ **Unknown**",
        unsafe_allow_html=True,
    )
else:
    st.info("No slot data for this date yet.")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# PER-COURT BAR CHART
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("### Per-Court Breakdown")

if not slots_df.empty:
    finalised_df = slots_df[slots_df["finalised"] == True].copy()
    if not finalised_df.empty:
        court_summary = finalised_df.groupby(["court_name", "status"]).size().reset_index(name="blocks")
        court_summary["hours"] = court_summary["blocks"] * 30 / 60

        fig_bar = px.bar(
            court_summary,
            x="court_name",
            y="hours",
            color="status",
            color_discrete_map={
                "booked":        "#ff4d6d",
                "went_unbooked": "#00ff9d",
            },
            labels={"court_name": "", "hours": "Hours", "status": "Status"},
            barmode="stack",
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Mono", color="#9ca3af"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=320,
            margin=dict(l=10, r=10, t=40, b=20),
        )
        fig_bar.update_xaxes(showgrid=False)
        fig_bar.update_yaxes(gridcolor="#1f2937")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No finalised slots yet for this date (data will appear as time slots pass).")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# UTILISATION TREND
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("### Utilisation Trend")

if not trend_df.empty and len(trend_df) > 1:
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend_df["query_date"],
        y=trend_df["utilisation_pct"],
        mode="lines+markers",
        name="Utilisation %",
        line=dict(color="#00ff9d", width=2),
        marker=dict(size=6, color="#00ff9d"),
        fill="tozeroy",
        fillcolor="rgba(0,255,157,0.08)",
    ))
    fig_trend.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono", color="#9ca3af"),
        yaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#1f2937"),
        xaxis=dict(showgrid=False),
        height=280,
        margin=dict(l=10, r=10, t=20, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("Trend will appear once data has been collected across multiple days.")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# RAW DATA TABLE
# ─────────────────────────────────────────────────────────────────────────────

with st.expander("📋 Raw slot data", expanded=False):
    if not slots_df.empty:
        display_df = slots_df[[
            "court_name", "block_time", "status", "finalised",
            "first_seen_available", "last_seen_available"
        ]].copy()
        display_df.columns = [
            "Court", "Block (AEST)", "Status", "Finalised",
            "First seen available", "Last seen available"
        ]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇ Download CSV",
            data=display_df.to_csv(index=False),
            file_name=f"padel_slots_{selected_date}.csv",
            mime="text/csv",
        )
    else:
        st.info("No data for this date.")
