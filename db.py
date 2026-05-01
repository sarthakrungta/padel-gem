"""
db.py — Database layer using Supabase (PostgreSQL)
====================================================
Replaces the local JSON snapshot files with a proper database.
All reads/writes go through this module.

Setup:
  1. Create a free project at https://supabase.com
  2. Go to Project Settings → Database → Connection string (URI mode)
  3. Set the DATABASE_URL environment variable to that URI
  4. Run: python db.py --init   to create the tables on first use

Tables:
  polls          — one row per API poll attempt
  slot_states    — one row per (date, court_id, block_time), updated each poll
"""

import os
import argparse
import psycopg2
import psycopg2.extras
from datetime import date, datetime
from zoneinfo import ZoneInfo

AEST = ZoneInfo("Australia/Sydney")

# ── Read connection string from environment variable
# Set this in Railway as an environment variable (Railway auto-sets it if you
# attach a Postgres plugin, OR paste your Supabase URI manually).
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL environment variable not set.\n"
        "Get it from: Supabase → Project Settings → Database → URI"
    )


def get_conn():
    """Return a new psycopg2 connection. Call .close() when done."""
    return psycopg2.connect(DATABASE_URL, sslmode="require")


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA INITIALISATION
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- One row per poll execution
CREATE TABLE IF NOT EXISTS polls (
    id          SERIAL PRIMARY KEY,
    polled_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query_date  DATE        NOT NULL,   -- AEST date we queried
    success     BOOLEAN     NOT NULL,
    error_msg   TEXT
);

-- One row per (query_date, court_id, block_time).
-- Updated (upserted) on every poll.
CREATE TABLE IF NOT EXISTS slot_states (
    id                    SERIAL PRIMARY KEY,
    query_date            DATE        NOT NULL,
    court_id              TEXT        NOT NULL,
    block_time            TIME        NOT NULL,   -- AEST 30-min block start e.g. 06:00
    status                TEXT        NOT NULL,   -- available | booked | went_unbooked
    first_seen_available  TIMESTAMPTZ,
    last_seen_available   TIMESTAMPTZ,
    finalised             BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (query_date, court_id, block_time)
);

-- Index for fast dashboard queries
CREATE INDEX IF NOT EXISTS idx_slot_states_date  ON slot_states (query_date);
CREATE INDEX IF NOT EXISTS idx_slot_states_court ON slot_states (court_id);
"""


def init_schema():
    """Create tables if they don't exist. Safe to run multiple times."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
    print("Schema initialised (or already exists).")


# ─────────────────────────────────────────────────────────────────────────────
# WRITE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def record_poll(query_date: date, success: bool, error_msg: str = None):
    """Insert a row into the polls audit table."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO polls (query_date, success, error_msg) VALUES (%s, %s, %s)",
                (query_date, success, error_msg)
            )
        conn.commit()


def upsert_slot_states(slot_history_for_date: dict, query_date: date):
    """
    Upsert all slot state rows for a given date.

    slot_history_for_date shape (same as the inner dict from tracker logic):
    {
      "court_id_1": {
        "06:00": {
          "status": "available",
          "first_seen_available": "2026-05-01T06:05:00+10:00",
          "last_seen_available":  "2026-05-01T07:05:00+10:00",
          "finalised": False
        },
        ...
      }
    }
    """
    rows = []
    now = datetime.now(tz=AEST)

    for court_id, blocks in slot_history_for_date.items():
        for block_time_str, h in blocks.items():
            rows.append((
                query_date,
                court_id,
                block_time_str,          # e.g. "06:00"
                h.get("status", "unknown"),
                h.get("first_seen_available"),
                h.get("last_seen_available"),
                h.get("finalised", False),
                now,
            ))

    if not rows:
        return

    upsert_sql = """
        INSERT INTO slot_states
            (query_date, court_id, block_time, status,
             first_seen_available, last_seen_available, finalised, updated_at)
        VALUES %s
        ON CONFLICT (query_date, court_id, block_time)
        DO UPDATE SET
            status               = EXCLUDED.status,
            first_seen_available = COALESCE(slot_states.first_seen_available, EXCLUDED.first_seen_available),
            last_seen_available  = EXCLUDED.last_seen_available,
            finalised            = EXCLUDED.finalised,
            updated_at           = EXCLUDED.updated_at
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, upsert_sql, rows)
        conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# READ OPERATIONS  (used by dashboard.py)
# ─────────────────────────────────────────────────────────────────────────────

def get_slot_states_for_date(query_date: date) -> list[dict]:
    """
    Return all slot state rows for a given date.
    Each row is a dict with keys matching the slot_states columns.
    """
    sql = """
        SELECT query_date, court_id, block_time, status,
               first_seen_available, last_seen_available, finalised, updated_at
        FROM slot_states
        WHERE query_date = %s
        ORDER BY court_id, block_time
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (query_date,))
            return [dict(r) for r in cur.fetchall()]


def get_available_dates() -> list[date]:
    """Return all dates that have slot data, newest first."""
    sql = "SELECT DISTINCT query_date FROM slot_states ORDER BY query_date DESC"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [row[0] for row in cur.fetchall()]


def get_utilisation_by_date() -> list[dict]:
    """
    Aggregate utilisation stats per date across all courts.
    Only counts finalised slots (booked + went_unbooked).
    Returns newest-first list of dicts.
    """
    sql = """
        SELECT
            query_date,
            COUNT(*) FILTER (WHERE status = 'booked')        AS booked_blocks,
            COUNT(*) FILTER (WHERE status = 'went_unbooked') AS unbooked_blocks,
            COUNT(*) FILTER (WHERE finalised = TRUE)          AS finalised_blocks,
            COUNT(DISTINCT court_id)                          AS num_courts
        FROM slot_states
        GROUP BY query_date
        ORDER BY query_date DESC
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]

    for row in rows:
        f = row["finalised_blocks"]
        row["utilisation_pct"] = round(
            row["booked_blocks"] / f * 100, 1
        ) if f > 0 else None

    return rows


def get_court_ids() -> list[str]:
    """Return all known court IDs."""
    sql = "SELECT DISTINCT court_id FROM slot_states ORDER BY court_id"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]


def get_recent_polls(limit: int = 20) -> list[dict]:
    """Return the most recent poll records."""
    sql = """
        SELECT polled_at, query_date, success, error_msg
        FROM polls ORDER BY polled_at DESC LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# CLI helper
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="Create DB tables")
    args = parser.parse_args()
    if args.init:
        init_schema()
