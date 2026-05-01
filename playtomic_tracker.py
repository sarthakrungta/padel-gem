"""
playtomic_tracker.py — Court availability poller (cloud version)
=================================================================
Polls the Playtomic API, converts UTC->AEST, expands slots into 30-min blocks,
diffs against previous snapshots, writes to local SQLite, then pushes a JSON
export to a GitHub Gist for the Streamlit dashboard to consume.

Usage:
  python playtomic_tracker.py            # one poll
  python playtomic_tracker.py --loop     # poll every POLL_INTERVAL_SECONDS

One-time setup:
  python db.py --init                    # create SQLite tables
  python db.py --create-gist             # create the GitHub Gist (needs GITHUB_TOKEN)

Environment variables (set in Railway):
  GITHUB_TOKEN   — GitHub PAT with "gist" scope
  GIST_ID        — Gist ID printed by --create-gist
"""

import requests
import math
import time
import argparse
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import db  # our database layer

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

TENANT_ID   = "b5a636e5-35d0-421b-b823-d857b8c9f088"
SPORT_ID    = "PADEL"
API_BASE    = "https://playtomic.com/api/clubs/availability"

OPENING_HOURS = {
    "weekday": {"open": "06:00", "close": "21:00"},  # Mon–Fri AEST
    "weekend": {"open": "08:00", "close": "18:00"},  # Sat–Sun AEST
}

AEST              = ZoneInfo("Australia/Sydney")
BLOCK_MINUTES     = 30
POLL_INTERVAL_SECONDS = 300   # 5 minutes

# How many minutes before a slot's start time the platform stops showing it
# as available, even if nobody booked it. If a slot disappears from the API
# response within this window of its start time, AND we last saw it as
# available, we treat it as "went_unbooked" rather than "booked".
# Set based on observation — Playtomic appears to drop slots ~10–15 min early.
PRE_REMOVAL_WINDOW_MINUTES = 15

# ─────────────────────────────────────────────────────────────────────────────
# TIME UTILITIES  (identical to local version)
# ─────────────────────────────────────────────────────────────────────────────

def now_aest() -> datetime:
    return datetime.now(tz=AEST)

def today_aest() -> date:
    return now_aest().date()

def utc_slot_to_aest(utc_date_str: str, utc_time_str: str) -> datetime:
    UTC = ZoneInfo("UTC")
    dt_utc = datetime.strptime(
        f"{utc_date_str} {utc_time_str}", "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=UTC)
    return dt_utc.astimezone(AEST)

def get_opening_hours(for_date: date) -> tuple[datetime, datetime]:
    key = "weekend" if for_date.weekday() >= 5 else "weekday"
    hours = OPENING_HOURS[key]
    open_dt  = datetime.strptime(hours["open"],  "%H:%M").replace(
        year=for_date.year, month=for_date.month, day=for_date.day, tzinfo=AEST
    )
    close_dt = datetime.strptime(hours["close"], "%H:%M").replace(
        year=for_date.year, month=for_date.month, day=for_date.day, tzinfo=AEST
    )
    return open_dt, close_dt

def generate_full_day_blocks(for_date: date) -> list[str]:
    open_dt, close_dt = get_opening_hours(for_date)
    blocks, current = [], open_dt
    while current + timedelta(minutes=BLOCK_MINUTES) <= close_dt:
        blocks.append(current.strftime("%H:%M"))
        current += timedelta(minutes=BLOCK_MINUTES)
    return blocks

def slot_duration_to_blocks(duration_minutes: int) -> int:
    return math.ceil(duration_minutes / BLOCK_MINUTES)

# ─────────────────────────────────────────────────────────────────────────────
# API FETCH
# ─────────────────────────────────────────────────────────────────────────────

def fetch_availability(query_date: date) -> list[dict]:
    params = {
        "tenant_id": TENANT_ID,
        "date":      query_date.strftime("%Y-%m-%d"),
        "sport_id":  SPORT_ID,
    }
    print(f"  Fetching API for {query_date} …")
    resp = requests.get(API_BASE, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()

# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE PARSING — UTC → AEST, expand to 30-min blocks
# ─────────────────────────────────────────────────────────────────────────────

def parse_response(raw: list[dict], target_date: date) -> dict[str, set[str]]:
    """
    Returns { court_id: set of "HH:MM" block start times in AEST }
    Only includes blocks that:
      - Fall on target_date in AEST
      - Fall within opening hours
    """
    open_dt, close_dt = get_opening_hours(target_date)
    court_blocks: dict[str, set[str]] = {}

    for entry in raw:
        court_id = entry["resource_id"]
        utc_date = entry["start_date"]

        for slot in entry.get("slots", []):
            aest_dt = utc_slot_to_aest(utc_date, slot["start_time"])

            # Skip slots that belong to a different AEST day
            if aest_dt.date() != target_date:
                continue

            # Expand into N × 30-min blocks
            n_blocks = slot_duration_to_blocks(slot["duration"])
            for i in range(n_blocks):
                block_dt = aest_dt + timedelta(minutes=i * BLOCK_MINUTES)
                if block_dt < open_dt or block_dt >= close_dt:
                    continue
                court_blocks.setdefault(court_id, set()).add(
                    block_dt.strftime("%H:%M")
                )

    return court_blocks

# ─────────────────────────────────────────────────────────────────────────────
# SNAPSHOT DIFFING — produces slot_history dict, then writes to DB
# ─────────────────────────────────────────────────────────────────────────────

def build_slot_history_from_db(target_date: date) -> dict:
    """
    Load existing slot state from the database into the same in-memory
    dict format used by update_snapshots().
    Shape: { court_id: { "HH:MM": { status, first_seen_available, ... } } }
    """
    rows = db.get_slot_states_for_date(target_date)
    history: dict[str, dict] = {}
    for row in rows:
        cid = row["court_id"]
        bt  = row["block_time"][:5] if isinstance(row["block_time"], str) else row["block_time"].strftime("%H:%M")
        history.setdefault(cid, {})[bt] = {
            "status":               row["status"],
            "first_seen_available": row["first_seen_available"].isoformat() if row["first_seen_available"] else None,
            "last_seen_available":  row["last_seen_available"].isoformat()  if row["last_seen_available"]  else None,
            "finalised":            row["finalised"],
        }
    return history


def update_slot_history(
    target_date:   date,
    court_blocks:  dict[str, set[str]],   # from parse_response
    prev_history:  dict,                  # loaded from DB
) -> dict:
    """
    Diff current API snapshot against previous state and return updated history.

    Two live statuses:
      available     — slot is in the API response right now (not yet booked)
      booked        — slot is NOT in the API response

    One finalised status:
      went_unbooked — slot was available, then disappeared within
                      PRE_REMOVAL_WINDOW_MINUTES of its start time,
                      meaning the platform aged it out rather than
                      someone booking it

    Rule: if a slot is not in the response, it is booked — UNLESS it was
    previously available and disappeared within the grace window, in which
    case it went unbooked.

    There is no unknown state. Every slot is either available or booked
    from the very first poll that covers it.
    """
    full_day   = generate_full_day_blocks(target_date)
    date_str   = target_date.strftime("%Y-%m-%d")
    now        = now_aest()
    now_iso    = now.isoformat()
    updated    = {}

    # Union of courts: currently in API + previously in DB
    all_courts = set(court_blocks.keys()) | set(prev_history.keys())

    for court_id in all_courts:
        available_blocks = court_blocks.get(court_id, set())
        prev_court       = prev_history.get(court_id, {})
        updated[court_id] = {}

        for block_time_str in full_day:
            block_dt = datetime.strptime(
                f"{date_str} {block_time_str}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=AEST)
            is_past = now >= block_dt + timedelta(minutes=BLOCK_MINUTES)

            prev = prev_court.get(block_time_str, {
                "status":               "booked",   # default: not seen = booked
                "first_seen_available": None,
                "last_seen_available":  None,
                "finalised":            False,
            })

            # Don't re-process already-finalised slots
            if prev.get("finalised"):
                updated[court_id][block_time_str] = prev
                continue

            h = dict(prev)

            if block_time_str in available_blocks:
                # ── In API response → available ──
                if h["first_seen_available"] is None:
                    h["first_seen_available"] = now_iso
                h["last_seen_available"] = now_iso
                h["status"] = "available"

            else:
                # ── Not in API response → booked, unless grace window applies ──
                last_seen_str = h.get("last_seen_available")

                if last_seen_str is not None:
                    # Was available in a previous poll — check grace window.
                    # If it disappeared within PRE_REMOVAL_WINDOW_MINUTES of
                    # start time, the platform aged it out → went_unbooked.
                    # If it disappeared earlier, someone booked it → booked.
                    last_seen_dt = datetime.fromisoformat(last_seen_str)
                    minutes_from_last_seen_to_start = (
                        block_dt - last_seen_dt
                    ).total_seconds() / 60

                    if minutes_from_last_seen_to_start <= PRE_REMOVAL_WINDOW_MINUTES:
                        h["status"] = "went_unbooked"
                    else:
                        h["status"] = "booked"
                else:
                    # Never seen as available → booked
                    h["status"] = "booked"

            # ── Finalise once the slot's end time has passed ──
            if is_past and not h["finalised"]:
                if h["status"] == "available":
                    # Still showing as available after end time → went unbooked
                    h["status"] = "went_unbooked"
                # booked stays booked, went_unbooked stays went_unbooked
                h["finalised"] = True

            updated[court_id][block_time_str] = h

    return updated

# ─────────────────────────────────────────────────────────────────────────────
# MAIN POLL CYCLE
# ─────────────────────────────────────────────────────────────────────────────

def run_poll():
    target_date = today_aest()
    ts = now_aest().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{ts} AEST] ── Poll starting for {target_date}")

    try:
        # 1. Fetch API
        raw = fetch_availability(target_date)

        # 2. Parse UTC → AEST, expand to 30-min blocks
        court_blocks = parse_response(raw, target_date)
        print(f"  Courts found: {len(court_blocks)}")
        for cid, blocks in court_blocks.items():
            print(f"    {cid[:8]}…: {len(blocks)} available blocks")

        # 3. Load previous state from SQLite
        prev_history = build_slot_history_from_db(target_date)

        # 4. Diff
        updated_history = update_slot_history(target_date, court_blocks, prev_history)

        # 5. Write to SQLite
        db.upsert_slot_states(updated_history, target_date)
        db.record_poll(target_date, success=True)

        # 6. Push export to GitHub Gist so Streamlit dashboard can read it
        db.export_gist()

        print(f"  Poll complete.")

    except Exception as e:
        print(f"  ✗ Poll failed: {e}")
        try:
            db.record_poll(target_date, success=False, error_msg=str(e))
        except Exception:
            pass
        raise

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Playtomic court utilisation tracker")
    parser.add_argument("--loop", action="store_true",
                        help=f"Poll every {POLL_INTERVAL_SECONDS}s continuously")
    args = parser.parse_args()

    if args.loop:
        print(f"Continuous mode — polling every {POLL_INTERVAL_SECONDS}s. Ctrl+C to stop.")
        while True:
            try:
                run_poll()
            except Exception as e:
                print(f"  [ERROR] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)
    else:
        run_poll()

if __name__ == "__main__":
    main()