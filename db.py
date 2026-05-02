"""
db.py — SQLite database layer (multi-club)
==========================================
Schema is club-aware: every row in slot_states and polls carries a club_id.
Existing data is preserved via migrate_add_club_id() which safely adds the
column and backfills old rows as "south_east_padel".

Gist export is nested by club_id so the dashboard can filter per club.
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


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

def init_schema():
    """
    Create/update schema. Safe to run on every startup.
    Automatically runs migration if club_id column is missing from existing data.
    """
    # Run migration first if needed — this is a no-op if already migrated
    migrate_add_club_id()

    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS polls (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                polled_at  TEXT NOT NULL,
                query_date TEXT NOT NULL,
                club_id    TEXT NOT NULL DEFAULT 'south_east_padel',
                success    INTEGER NOT NULL,
                error_msg  TEXT
            );

            CREATE TABLE IF NOT EXISTS slot_states (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                query_date           TEXT NOT NULL,
                club_id              TEXT NOT NULL DEFAULT 'south_east_padel',
                court_id             TEXT NOT NULL,
                block_time           TEXT NOT NULL,
                status               TEXT NOT NULL,
                first_seen_available TEXT,
                last_seen_available  TEXT,
                finalised            INTEGER NOT NULL DEFAULT 0,
                updated_at           TEXT NOT NULL,
                UNIQUE (query_date, club_id, court_id, block_time)
            );

            CREATE INDEX IF NOT EXISTS idx_ss_date  ON slot_states (query_date);
            CREATE INDEX IF NOT EXISTS idx_ss_club  ON slot_states (club_id);
            CREATE INDEX IF NOT EXISTS idx_ss_court ON slot_states (court_id);
        """)
    print(f"Schema ready at {DB_PATH}")


def migrate_add_club_id():
    """
    One-time migration: adds club_id column to existing tables and backfills
    all existing rows as 'south_east_padel'. Safe to run multiple times —
    skips gracefully if column already exists.

    Also drops and recreates the UNIQUE constraint to include club_id.
    Because SQLite doesn't support ALTER CONSTRAINT, we recreate the table.
    """
    with get_conn() as conn:
        # ── Check if club_id already exists in slot_states
        cols = [r[1] for r in conn.execute("PRAGMA table_info(slot_states)").fetchall()]

        if "club_id" in cols:
            print("[migrate] club_id already exists — skipping migration.")
            return

        print("[migrate] Adding club_id to polls table...")
        conn.execute("ALTER TABLE polls ADD COLUMN club_id TEXT NOT NULL DEFAULT 'south_east_padel'")

        print("[migrate] Recreating slot_states with club_id and updated UNIQUE key...")
        conn.executescript("""
            -- Copy existing data into a temp table
            CREATE TABLE slot_states_backup AS SELECT * FROM slot_states;

            -- Drop old table
            DROP TABLE slot_states;

            -- Recreate with club_id and new UNIQUE constraint
            CREATE TABLE slot_states (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                query_date           TEXT NOT NULL,
                club_id              TEXT NOT NULL DEFAULT 'south_east_padel',
                court_id             TEXT NOT NULL,
                block_time           TEXT NOT NULL,
                status               TEXT NOT NULL,
                first_seen_available TEXT,
                last_seen_available  TEXT,
                finalised            INTEGER NOT NULL DEFAULT 0,
                updated_at           TEXT NOT NULL,
                UNIQUE (query_date, club_id, court_id, block_time)
            );

            -- Restore data with club_id backfilled
            INSERT INTO slot_states
                (query_date, club_id, court_id, block_time, status,
                 first_seen_available, last_seen_available, finalised, updated_at)
            SELECT
                query_date,
                'south_east_padel',
                court_id, block_time, status,
                first_seen_available, last_seen_available, finalised, updated_at
            FROM slot_states_backup;

            -- Clean up
            DROP TABLE slot_states_backup;

            -- Recreate indexes
            CREATE INDEX IF NOT EXISTS idx_ss_date  ON slot_states (query_date);
            CREATE INDEX IF NOT EXISTS idx_ss_club  ON slot_states (club_id);
            CREATE INDEX IF NOT EXISTS idx_ss_court ON slot_states (court_id);
        """)

        print("[migrate] Migration complete. All existing rows tagged as 'south_east_padel'.")

        # Show summary
        rows = conn.execute("""
            SELECT club_id, COUNT(*) as cnt FROM slot_states GROUP BY club_id
        """).fetchall()
        for r in rows:
            print(f"  {r['club_id']}: {r['cnt']} rows")


# ─────────────────────────────────────────────────────────────────────────────
# WRITE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def record_poll(query_date: date, club_id: str, success: bool, error_msg: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO polls (polled_at, query_date, club_id, success, error_msg) VALUES (?,?,?,?,?)",
            (datetime.now(tz=AEST).isoformat(), str(query_date), club_id, int(success), error_msg)
        )


def upsert_slot_states(slot_history_for_date: dict, query_date: date, club_id: str):
    now = datetime.now(tz=AEST).isoformat()
    rows = []
    for court_id, blocks in slot_history_for_date.items():
        for block_time_str, h in blocks.items():
            rows.append((
                str(query_date),
                club_id,
                court_id,
                block_time_str,
                h.get("status", "booked"),
                h.get("first_seen_available"),
                h.get("last_seen_available"),
                int(h.get("finalised", False)),
                now,
            ))
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO slot_states
                (query_date, club_id, court_id, block_time, status,
                 first_seen_available, last_seen_available, finalised, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT (query_date, club_id, court_id, block_time) DO UPDATE SET
                status               = excluded.status,
                first_seen_available = COALESCE(slot_states.first_seen_available,
                                                excluded.first_seen_available),
                last_seen_available  = excluded.last_seen_available,
                finalised            = excluded.finalised,
                updated_at           = excluded.updated_at
        """, rows)


# ─────────────────────────────────────────────────────────────────────────────
# READ OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_slot_states_for_date(query_date: date, club_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM slot_states
               WHERE query_date=? AND club_id=?
               ORDER BY court_id, block_time""",
            (str(query_date), club_id)
        ).fetchall()
    return [dict(r) for r in rows]


def get_available_dates(club_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT query_date FROM slot_states
               WHERE club_id=? ORDER BY query_date DESC""",
            (club_id,)
        ).fetchall()
    return [r["query_date"] for r in rows]


def get_utilisation_by_date(club_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                query_date,
                SUM(status = 'booked')        AS booked_blocks,
                SUM(status = 'went_unbooked') AS unbooked_blocks,
                SUM(finalised = 1)             AS finalised_blocks,
                COUNT(DISTINCT court_id)       AS num_courts
            FROM slot_states
            WHERE club_id = ?
            GROUP BY query_date
            ORDER BY query_date DESC
        """, (club_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        f = d["finalised_blocks"] or 0
        d["utilisation_pct"] = round(d["booked_blocks"] / f * 100, 1) if f > 0 else None
        result.append(d)
    return result


def get_slot_history_for_date(query_date: date, club_id: str) -> dict:
    """
    Load existing slot state from DB into the in-memory dict format
    used by the tracker's diffing logic.
    Returns: { court_id: { "HH:MM": { status, first_seen_available, ... } } }
    """
    rows = get_slot_states_for_date(query_date, club_id)
    history: dict = {}
    for row in rows:
        cid = row["court_id"]
        bt  = row["block_time"][:5]   # always a string from SQLite e.g. "06:00"
        history.setdefault(cid, {})[bt] = {
            "status":               row["status"],
            # SQLite stores these as plain ISO strings — pass through as-is
            "first_seen_available": row["first_seen_available"] if row["first_seen_available"] else None,
            "last_seen_available":  row["last_seen_available"]  if row["last_seen_available"]  else None,
            "finalised":            bool(row["finalised"]),
        }
    return history


def get_recent_polls(limit: int = 10) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM polls ORDER BY polled_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_club_ids() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT club_id FROM slot_states ORDER BY club_id"
        ).fetchall()
    return [r["club_id"] for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# GIST EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def build_export_payload() -> dict:
    """
    Build the full JSON payload for the dashboard.
    Nested by club_id so the dashboard can filter per club.
    """
    club_ids = get_all_club_ids()
    clubs_data = {}
    for club_id in club_ids:
        dates = get_available_dates(club_id)[:30]
        slots_by_date = {}
        for d in dates:
            slots_by_date[d] = get_slot_states_for_date(date.fromisoformat(d), club_id)
        clubs_data[club_id] = {
            "available_dates":   dates,
            "utilisation_trend": get_utilisation_by_date(club_id)[:30],
            "slots_by_date":     slots_by_date,
        }
    return {
        "exported_at":  datetime.now(tz=AEST).isoformat(),
        "clubs":        clubs_data,
        "recent_polls": get_recent_polls(10),
    }


def export_gist():
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
    print(f"\nSet in Railway env vars:  GIST_ID / GITHUB_TOKEN")
    print(f"Set in Streamlit secrets: GIST_RAW_URL = \"{raw_url}\"")
    return gist_id


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--init",           action="store_true", help="Create/update SQLite tables")
    parser.add_argument("--migrate",        action="store_true", help="Add club_id to existing data (run once)")
    parser.add_argument("--create-gist",    action="store_true", help="Create GitHub Gist (run once)")
    parser.add_argument("--export-gist",    action="store_true", help="Push current data to Gist now")
    args = parser.parse_args()

    if args.init:
        init_schema()
    elif args.migrate:
        migrate_add_club_id()
    elif args.create_gist:
        create_gist()
    elif args.export_gist:
        export_gist()
    else:
        parser.print_help()