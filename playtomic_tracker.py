"""
playtomic_tracker.py — Multi-club court availability poller
============================================================
Polls all configured clubs every POLL_INTERVAL_SECONDS, converts UTC->AEST,
expands slots into 30-min blocks, diffs against previous snapshots, writes to
SQLite, then pushes a JSON export to a GitHub Gist.

To add a new club: add an entry to the CLUBS dict below. That's it.

Usage:
  python playtomic_tracker.py          # one poll of all clubs
  python playtomic_tracker.py --loop   # continuous polling

One-time setup:
  python db.py --migrate   # add club_id to existing data (run once, then remove)
  python db.py --init      # create/update schema
"""

import requests
import math
import time
import argparse
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import db

# ─────────────────────────────────────────────────────────────────────────────
# CLUB REGISTRY — add new clubs here
# ─────────────────────────────────────────────────────────────────────────────

CLUBS = {
    "south_east_padel": {
        "display_name": "South East Padel",
        "tenant_id":    "b5a636e5-35d0-421b-b823-d857b8c9f088",
        "opening_hours": {
            "weekday": {"open": "06:00", "close": "21:00"},
            "weekend": {"open": "08:00", "close": "18:00"},
        },
    },
    "game4padel_richmond": {
        "display_name": "Game4Padel Richmond",
        "tenant_id":    "fd015cf7-b26b-4f7b-9a1f-8ed26f97ca05",
        "opening_hours": {
            "weekday": {"open": "08:00", "close": "22:00"},
            "weekend": {"open": "08:00", "close": "21:00"},
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

SPORT_ID              = "PADEL"
API_BASE              = "https://playtomic.com/api/clubs/availability"
AEST                  = ZoneInfo("Australia/Sydney")
BLOCK_MINUTES         = 30
POLL_INTERVAL_SECONDS = 300   # 5 minutes between full cycles (all clubs)

# Playtomic stops showing a slot as available a few minutes before its start
# time even if nobody booked it. If a slot disappears within this many minutes
# of its start time AND we previously saw it as available, we call it
# went_unbooked rather than booked.
PRE_REMOVAL_WINDOW_MINUTES = 15

# ─────────────────────────────────────────────────────────────────────────────
# TIME UTILITIES
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

def get_opening_hours(club_cfg: dict, for_date: date) -> tuple:
    key = "weekend" if for_date.weekday() >= 5 else "weekday"
    hours = club_cfg["opening_hours"][key]
    open_dt  = datetime.strptime(hours["open"],  "%H:%M").replace(
        year=for_date.year, month=for_date.month, day=for_date.day, tzinfo=AEST
    )
    close_dt = datetime.strptime(hours["close"], "%H:%M").replace(
        year=for_date.year, month=for_date.month, day=for_date.day, tzinfo=AEST
    )
    return open_dt, close_dt

def generate_full_day_blocks(club_cfg: dict, for_date: date) -> list:
    """All expected 30-min block start times (HH:MM) for this club/date."""
    open_dt, close_dt = get_opening_hours(club_cfg, for_date)
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

def fetch_availability(tenant_id: str, query_date: date) -> list:
    params = {
        "tenant_id": tenant_id,
        "date":      query_date.strftime("%Y-%m-%d"),
        "sport_id":  SPORT_ID,
    }
    resp = requests.get(API_BASE, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()

# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE PARSING — UTC → AEST, expand to 30-min blocks
# ─────────────────────────────────────────────────────────────────────────────

def parse_response(raw: list, club_cfg: dict, target_date: date) -> dict:
    """
    Returns { court_id: set of "HH:MM" available block start times in AEST }
    Filters to target_date only and clips to opening hours.
    """
    open_dt, close_dt = get_opening_hours(club_cfg, target_date)
    court_blocks: dict = {}

    for entry in raw:
        court_id = entry["resource_id"]
        utc_date = entry["start_date"]

        for slot in entry.get("slots", []):
            aest_dt = utc_slot_to_aest(utc_date, slot["start_time"])

            if aest_dt.date() != target_date:
                continue

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
# SNAPSHOT DIFFING
# ─────────────────────────────────────────────────────────────────────────────

def update_slot_history(
    target_date:  date,
    club_cfg:     dict,
    court_blocks: dict,   # from parse_response
    prev_history: dict,   # loaded from DB via db.get_slot_history_for_date
) -> dict:
    """
    Diffs current API snapshot against previous state.
    Returns updated history dict ready for db.upsert_slot_states().

    Status rules:
      - In API response                          → available
      - Not in response, never seen              → booked
      - Not in response, last seen within grace window of start → went_unbooked
      - Not in response, last seen before grace window          → booked
    Finalisation (slot end time passed):
      available     → went_unbooked
      booked        → booked (unchanged)
      went_unbooked → went_unbooked (unchanged)
    """
    full_day   = generate_full_day_blocks(club_cfg, target_date)
    date_str   = target_date.strftime("%Y-%m-%d")
    now        = now_aest()
    now_iso    = now.isoformat()
    updated    = {}

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
                "status":               "booked",
                "first_seen_available": None,
                "last_seen_available":  None,
                "finalised":            False,
            })

            if prev.get("finalised"):
                updated[court_id][block_time_str] = prev
                continue

            h = dict(prev)

            if block_time_str in available_blocks:
                if h["first_seen_available"] is None:
                    h["first_seen_available"] = now_iso
                h["last_seen_available"] = now_iso
                h["status"] = "available"
            else:
                last_seen_str = h.get("last_seen_available")
                if last_seen_str is not None:
                    last_seen_dt = datetime.fromisoformat(last_seen_str)
                    mins_from_last_seen_to_start = (
                        block_dt - last_seen_dt
                    ).total_seconds() / 60
                    if mins_from_last_seen_to_start <= PRE_REMOVAL_WINDOW_MINUTES:
                        h["status"] = "went_unbooked"
                    else:
                        h["status"] = "booked"
                else:
                    h["status"] = "booked"

            if is_past and not h["finalised"]:
                if h["status"] == "available":
                    h["status"] = "went_unbooked"
                h["finalised"] = True

            updated[court_id][block_time_str] = h

    return updated

# ─────────────────────────────────────────────────────────────────────────────
# SINGLE CLUB POLL
# ─────────────────────────────────────────────────────────────────────────────

def poll_club(club_id: str, club_cfg: dict, target_date: date):
    """Run one full poll cycle for a single club."""
    print(f"  [{club_cfg['display_name']}] Fetching …")
    try:
        raw          = fetch_availability(club_cfg["tenant_id"], target_date)
        court_blocks = parse_response(raw, club_cfg, target_date)

        for cid, blocks in court_blocks.items():
            print(f"    {cid[:8]}…: {len(blocks)} available blocks")

        prev_history    = db.get_slot_history_for_date(target_date, club_id)
        updated_history = update_slot_history(target_date, club_cfg, court_blocks, prev_history)

        db.upsert_slot_states(updated_history, target_date, club_id)
        db.record_poll(target_date, club_id, success=True)
        print(f"  [{club_cfg['display_name']}] ✓ Done")

    except Exception as e:
        print(f"  [{club_cfg['display_name']}] ✗ Failed: {e}")
        try:
            db.record_poll(target_date, club_id, success=False, error_msg=str(e))
        except Exception:
            pass
        raise

# ─────────────────────────────────────────────────────────────────────────────
# MAIN POLL CYCLE
# ─────────────────────────────────────────────────────────────────────────────

def run_poll():
    target_date = today_aest()
    ts = now_aest().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{ts} AEST] ── Poll cycle starting for {target_date}")

    for club_id, club_cfg in CLUBS.items():
        try:
            poll_club(club_id, club_cfg, target_date)
        except Exception as e:
            # Log and continue to next club rather than aborting the whole cycle
            print(f"  [ERROR] {club_id}: {e}")

    # Export Gist once after all clubs are done
    db.export_gist()
    print(f"  Cycle complete.")

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Padel court utilisation tracker")
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