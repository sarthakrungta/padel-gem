"""
db.py — SQLite database layer (no external DB needed)
======================================================
Stores all slot state in a local SQLite file on Railway's persistent disk.
After each poll the tracker calls export_gist() to push a JSON summary to a
secret GitHub Gist, which the Streamlit dashboard fetches over HTTPS.

Environment variables required:
  GITHUB_TOKEN   — Personal Access Token with "gist" scope
  GIST_ID        — ID of the secret gist to update (create once, reuse forever)

Optional:
  DB_PATH        — path to SQLite file (default: ./tracker_data/padel.db)

One-time setup on your laptop:
  1. Create a GitHub PAT at https://github.com/settings/tokens
     -> "Generate new token (classic)" -> tick only "gist" scope
  2. Run:  python db.py --create-gist
     This creates the secret gist and prints its ID.
  3. Set GITHUB_TOKEN and GIST_ID as env vars in Railway.
"""

import os
import json
import sqlite3
import argparse
import requests
from datetime import date, datetime
from zoneinfo import ZoneInfo
from contextlib import contextmanager

AEST    = ZoneInfo("Australia/Sydney")
DB_PATH = os.environ.get("DB_PATH", "./tracker_data/padel.db")

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GIST_ID       = os.environ.get("GIST_ID", "")
GIST_FILENAME = "padel_tracker_data.json"


def ensure_db_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_conn():
    ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS polls (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                polled_at  TEXT NOT NULL,
                query_date TEXT NOT NULL,
                success    INTEGER NOT NULL,
                error_msg  TEXT
            );

            CREATE TABLE IF NOT EXISTS slot_states (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                query_date           TEXT NOT NULL,
                court_id             TEXT NOT NULL,
                block_time           TEXT NOT NULL,
                status               TEXT NOT NULL,
                first_seen_available TEXT,
                last_seen_available  TEXT,
                finalised            INTEGER NOT NULL DEFAULT 0,
                updated_at           TEXT NOT NULL,
                UNIQUE (query_date, court_id, block_time)
            );

            CREATE INDEX IF NOT EXISTS idx_ss_date  ON slot_states (query_date);
            CREATE INDEX IF NOT EXISTS idx_ss_court ON slot_states (court_id);
        """)
    print(f"Schema ready at {DB_PATH}")


def record_poll(query_date: date, success: bool, error_msg: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO polls (polled_at, query_date, success, error_msg) VALUES (?,?,?,?)",
            (datetime.now(tz=AEST).isoformat(), str(query_date), int(success), error_msg)
        )


def upsert_slot_states(slot_history_for_date: dict, query_date: date):
    now = datetime.now(tz=AEST).isoformat()
    rows = []
    for court_id, blocks in slot_history_for_date.items():
        for block_time_str, h in blocks.items():
            rows.append((
                str(query_date),
                court_id,
                block_time_str,
                h.get("status", "unknown"),
                h.get("first_seen_available"),
                h.get("last_seen_available"),
                int(h.get("finalised", False)),
                now,
            ))
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO slot_states
                (query_date, court_id, block_time, status,
                 first_seen_available, last_seen_available, finalised, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT (query_date, court_id, block_time) DO UPDATE SET
                status               = excluded.status,
                first_seen_available = COALESCE(slot_states.first_seen_available,
                                                excluded.first_seen_available),
                last_seen_available  = excluded.last_seen_available,
                finalised            = excluded.finalised,
                updated_at           = excluded.updated_at
        """, rows)


def get_slot_states_for_date(query_date: date) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM slot_states WHERE query_date=? ORDER BY court_id, block_time",
            (str(query_date),)
        ).fetchall()
    return [dict(r) for r in rows]


def get_available_dates() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT query_date FROM slot_states ORDER BY query_date DESC"
        ).fetchall()
    return [r["query_date"] for r in rows]


def get_utilisation_by_date() -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                query_date,
                SUM(status = 'booked')        AS booked_blocks,
                SUM(status = 'went_unbooked') AS unbooked_blocks,
                SUM(finalised = 1)             AS finalised_blocks,
                COUNT(DISTINCT court_id)       AS num_courts
            FROM slot_states
            GROUP BY query_date
            ORDER BY query_date DESC
        """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        f = d["finalised_blocks"] or 0
        d["utilisation_pct"] = round(d["booked_blocks"] / f * 100, 1) if f > 0 else None
        result.append(d)
    return result


def get_recent_polls(limit: int = 10) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM polls ORDER BY polled_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def build_export_payload() -> dict:
    """Build the JSON payload the Streamlit dashboard will fetch."""
    dates = get_available_dates()[:30]
    slots_by_date = {}
    for d in dates:
        slots_by_date[d] = get_slot_states_for_date(date.fromisoformat(d))
    return {
        "exported_at":       datetime.now(tz=AEST).isoformat(),
        "available_dates":   dates,
        "utilisation_trend": get_utilisation_by_date()[:30],
        "recent_polls":      get_recent_polls(10),
        "slots_by_date":     slots_by_date,
    }


def export_gist():
    """Push the latest data to the GitHub Gist. Skips if env vars not set."""
    if not GITHUB_TOKEN or not GIST_ID:
        print("  [Gist] GITHUB_TOKEN or GIST_ID not set — skipping export.")
        return
    content = json.dumps(build_export_payload(), indent=2, default=str)
    resp = requests.patch(
        f"https://api.github.com/gists/{GIST_ID}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={"files": {GIST_FILENAME: {"content": content}}},
        timeout=20,
    )
    resp.raise_for_status()
    print(f"  [Gist] Exported {len(content)//1024}KB to gist/{GIST_ID}")


def create_gist() -> str:
    """Create a new secret GitHub Gist. Run once: python db.py --create-gist"""
    if not GITHUB_TOKEN:
        raise EnvironmentError("Set GITHUB_TOKEN env var first.")
    resp = requests.post(
        "https://api.github.com/gists",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "description": "Padel court tracker data (auto-updated)",
            "public": False,
            "files": {GIST_FILENAME: {"content": json.dumps({"status": "initialised"})}},
        },
        timeout=15,
    )
    resp.raise_for_status()
    data     = resp.json()
    gist_id  = data["id"]
    username = data["owner"]["login"]
    raw_url  = f"https://gist.githubusercontent.com/{username}/{gist_id}/raw/{GIST_FILENAME}"

    print(f"\nGist created!")
    print(f"  GIST_ID      = {gist_id}")
    print(f"  View URL     = {data['html_url']}")
    print(f"\nSet these in Railway env vars:")
    print(f"  GIST_ID      = {gist_id}")
    print(f"  GITHUB_TOKEN = <your token>")
    print(f"\nSet this in Streamlit secrets:")
    print(f"  GIST_RAW_URL = \"{raw_url}\"")
    return gist_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--init",        action="store_true", help="Create SQLite tables")
    parser.add_argument("--create-gist", action="store_true", help="Create GitHub Gist (run once)")
    parser.add_argument("--export-gist", action="store_true", help="Push current data to Gist now")
    args = parser.parse_args()

    if args.init:
        init_schema()
    elif args.create_gist:
        create_gist()
    elif args.export_gist:
        export_gist()
    else:
        parser.print_help()
