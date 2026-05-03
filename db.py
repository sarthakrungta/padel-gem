"""
db.py — PostgreSQL database layer for the Padel Court Tracker
==============================================================
Reads DATABASE_URL from environment (set automatically by Railway Postgres).
This is a library module — import it, don't run it directly.
"""

import os
from datetime import datetime, date
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras

AEST = ZoneInfo("Australia/Sydney")


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTION
# ─────────────────────────────────────────────────────────────────────────────

def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set.")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn





# ─────────────────────────────────────────────────────────────────────────────
# POLLS
# ─────────────────────────────────────────────────────────────────────────────

def record_poll(query_date: date, club_id: str, success: bool, error_msg: str = None):
    now_iso = datetime.now(tz=AEST).isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO polls (polled_at, query_date, club_id, success, error_msg)
                   VALUES (%s, %s, %s, %s, %s)""",
                (now_iso, query_date.isoformat(), club_id, 1 if success else 0, error_msg)
            )
        conn.commit()


def get_recent_polls(n: int = 10) -> list:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM polls ORDER BY id DESC LIMIT %s", (n,))
            return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# SLOT STATES — write
# ─────────────────────────────────────────────────────────────────────────────

def upsert_slot_states(history: dict, query_date: date, club_id: str):
    """
    history: { court_id: { block_time: { status, first_seen_available,
                                          last_seen_available, finalised } } }
    """
    now_iso  = datetime.now(tz=AEST).isoformat()
    date_str = query_date.isoformat()
    rows = []
    for court_id, blocks in history.items():
        for block_time, h in blocks.items():
            rows.append((
                date_str,
                club_id,
                court_id,
                block_time,
                h.get("status", "booked"),
                h.get("first_seen_available"),
                h.get("last_seen_available"),
                1 if h.get("finalised") else 0,
                now_iso,
            ))

    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO slot_states
                    (query_date, club_id, court_id, block_time, status,
                     first_seen_available, last_seen_available, finalised, updated_at)
                VALUES %s
                ON CONFLICT (query_date, club_id, court_id, block_time) DO UPDATE SET
                    status               = EXCLUDED.status,
                    first_seen_available = EXCLUDED.first_seen_available,
                    last_seen_available  = EXCLUDED.last_seen_available,
                    finalised            = EXCLUDED.finalised,
                    updated_at           = EXCLUDED.updated_at
            """, rows)
        conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# SLOT STATES — read
# ─────────────────────────────────────────────────────────────────────────────

def get_slot_history_for_date(query_date: date, club_id: str) -> dict:
    """
    Returns { court_id: { block_time: { status, first_seen_available,
                                         last_seen_available, finalised } } }
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT court_id, block_time, status,
                          first_seen_available, last_seen_available, finalised
                   FROM slot_states
                   WHERE query_date = %s AND club_id = %s""",
                (query_date.isoformat(), club_id)
            )
            rows = cur.fetchall()

    history = {}
    for r in rows:
        court = r["court_id"]
        history.setdefault(court, {})[r["block_time"]] = {
            "status":               r["status"],
            "first_seen_available": r["first_seen_available"],
            "last_seen_available":  r["last_seen_available"],
            "finalised":            bool(r["finalised"]),
        }
    return history


def get_slot_states_for_date(query_date: date, club_id: str) -> list:
    """Returns list of row dicts for dashboard display."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, query_date, club_id, court_id, block_time, status,
                          first_seen_available, last_seen_available, finalised, updated_at
                   FROM slot_states
                   WHERE query_date = %s AND club_id = %s
                   ORDER BY court_id, block_time""",
                (query_date.isoformat(), club_id)
            )
            return [dict(r) for r in cur.fetchall()]


def get_available_dates(club_id: str) -> list:
    """Returns list of date strings (newest first) that have any slot data."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT query_date FROM slot_states
                   WHERE club_id = %s ORDER BY query_date DESC""",
                (club_id,)
            )
            return [r[0] for r in cur.fetchall()]


def get_utilisation_by_date(club_id: str) -> list:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT
                       query_date,
                       SUM(CASE WHEN status = 'booked'        AND finalised = 1 THEN 1 ELSE 0 END) AS booked_blocks,
                       SUM(CASE WHEN status = 'went_unbooked' AND finalised = 1 THEN 1 ELSE 0 END) AS unbooked_blocks,
                       SUM(CASE WHEN finalised = 1 THEN 1 ELSE 0 END)                              AS finalised_blocks,
                       COUNT(DISTINCT court_id)                                                     AS num_courts
                   FROM slot_states
                   WHERE club_id = %s
                   GROUP BY query_date
                   ORDER BY query_date DESC""",
                (club_id,)
            )
            rows = cur.fetchall()

    result = []
    for r in rows:
        finalised = r["finalised_blocks"]
        booked    = r["booked_blocks"]
        util_pct  = round(booked / finalised * 100, 1) if finalised > 0 else None
        result.append({
            "query_date":       r["query_date"],
            "booked_blocks":    booked,
            "unbooked_blocks":  r["unbooked_blocks"],
            "finalised_blocks": finalised,
            "num_courts":       r["num_courts"],
            "utilisation_pct":  util_pct,
        })
    return result


def get_all_club_ids() -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT club_id FROM slot_states ORDER BY club_id")
            return [r[0] for r in cur.fetchall()]