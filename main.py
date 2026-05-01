"""
Playtomic Court Availability Tracker
=====================================
Polls the Playtomic API for padel court availability, converts UTC times to
AEST, tracks slot state changes over time via snapshots, and reports daily
court utilisation.

Atomic unit: 30-minute blocks.
  - A 60-min slot  → marks 2 × 30-min blocks as available
  - A 90-min slot  → marks 3 × 30-min blocks as available
  - A 120-min slot → marks 4 × 30-min blocks as available
  - A 45-min slot  → marks 2 × 30-min blocks (rounds up to next 30-min boundary)
  - Any other odd duration → ceil(duration / 30) blocks

Usage:
  python playtomic_tracker.py            # run one poll + print report
  python playtomic_tracker.py --loop     # poll every POLL_INTERVAL_SECONDS
  python playtomic_tracker.py --report   # print utilisation report only
"""

import requests
import json
import os
import math
import time
import argparse
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo            # Python 3.9+; use pytz if on older Python

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit this block to match the club
# ─────────────────────────────────────────────────────────────────────────────

TENANT_ID   = "b5a636e5-35d0-421b-b823-d857b8c9f088"
SPORT_ID    = "PADEL"
API_BASE    = "https://playtomic.com/api/clubs/availability"

# Club opening hours in local AEST time (24-hour).
# The tracker uses these to build the "full expected day" of 30-min blocks.
# If a court never shows a block (i.e. it was already booked before we first
# polled), we still count it as part of the day denominator once opening hours
# are crossed — it is treated as booked.
OPENING_HOURS = {
    # weekday: Monday=0 … Friday=4
    "weekday": {"open": "06:00", "close": "21:00"},
    # weekend: Saturday=5, Sunday=6
    "weekend": {"open": "08:00", "close": "18:00"},
}

AEST          = ZoneInfo("Australia/Sydney")   # handles AEST/AEDT automatically
BLOCK_MINUTES = 30                              # atomic slot size in minutes
POLL_INTERVAL_SECONDS = 300                     # 5 minutes between polls (--loop)

# Where to persist snapshot data between runs
DATA_DIR      = "./tracker_data"
SNAPSHOT_FILE = os.path.join(DATA_DIR, "snapshots.json")
HISTORY_FILE  = os.path.join(DATA_DIR, "slot_history.json")

# ─────────────────────────────────────────────────────────────────────────────
# TIME UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def now_aest() -> datetime:
    """Return current datetime in AEST/AEDT."""
    return datetime.now(tz=AEST)


def today_aest() -> date:
    """Return today's date in AEST/AEDT."""
    return now_aest().date()


def utc_slot_to_aest(utc_date_str: str, utc_time_str: str) -> datetime:
    """
    Convert a UTC date + time string from the API into an AEST datetime.

    Args:
        utc_date_str: "2026-04-30"
        utc_time_str: "23:30:00"

    Returns:
        datetime in AEST timezone, e.g. 2026-05-01 09:30:00+10:00
    """
    from zoneinfo import ZoneInfo as _ZI
    UTC = _ZI("UTC")
    # Parse UTC datetime
    dt_utc = datetime.strptime(
        f"{utc_date_str} {utc_time_str}", "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=UTC)
    # Convert to AEST
    return dt_utc.astimezone(AEST)


def get_opening_hours(for_date: date) -> tuple[datetime, datetime]:
    """
    Return (open_dt, close_dt) as AEST-aware datetimes for the given date.
    Weekday = Mon–Fri, Weekend = Sat–Sun.
    """
    key = "weekend" if for_date.weekday() >= 5 else "weekday"
    hours = OPENING_HOURS[key]
    open_dt  = datetime.strptime(hours["open"],  "%H:%M").replace(
        year=for_date.year, month=for_date.month, day=for_date.day,
        tzinfo=AEST
    )
    close_dt = datetime.strptime(hours["close"], "%H:%M").replace(
        year=for_date.year, month=for_date.month, day=for_date.day,
        tzinfo=AEST
    )
    return open_dt, close_dt


def generate_full_day_blocks(for_date: date) -> list[str]:
    """
    Generate all expected 30-min block start times (as "HH:MM" strings) for
    the given date based on club opening hours.

    e.g. for a weekday (06:00–21:00):
    ["06:00","06:30","07:00", … "20:30"]  (last block starts at 20:30, ends 21:00)
    """
    open_dt, close_dt = get_opening_hours(for_date)
    blocks = []
    current = open_dt
    # The last block must START at least BLOCK_MINUTES before closing
    while current + timedelta(minutes=BLOCK_MINUTES) <= close_dt:
        blocks.append(current.strftime("%H:%M"))
        current += timedelta(minutes=BLOCK_MINUTES)
    return blocks


def slot_duration_to_blocks(duration_minutes: int) -> int:
    """
    How many 30-min blocks does a slot of `duration_minutes` cover?
    - 60 → 2 blocks
    - 90 → 3 blocks
    - 45 → 2 blocks (ceil(45/30) = 2)
    - 30 → 1 block
    """
    return math.ceil(duration_minutes / BLOCK_MINUTES)


# ─────────────────────────────────────────────────────────────────────────────
# API FETCHING
# ─────────────────────────────────────────────────────────────────────────────

def fetch_availability(query_date: date) -> list[dict]:
    """
    Call the Playtomic API for the given AEST date.
    Returns the raw JSON list, or raises on HTTP error.

    The API expects the local AEST date as input (e.g. "2026-05-01").
    The response contains UTC-based datetimes which we handle in parsing.
    """
    params = {
        "tenant_id": TENANT_ID,
        "date":      query_date.strftime("%Y-%m-%d"),   # AEST local date
        "sport_id":  SPORT_ID,
    }
    print(f"[{now_aest().strftime('%H:%M:%S')} AEST] Fetching availability for {query_date} …")
    resp = requests.get(API_BASE, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE PARSING — the UTC→AEST unwrapper
# ─────────────────────────────────────────────────────────────────────────────

def parse_response(raw: list[dict], target_date: date) -> dict[str, set[str]]:
    """
    Parse the raw API response and return a mapping of:
        court_id → set of available 30-min block start times (in AEST, "HH:MM")

    Key steps:
    1. Each entry in the raw list has a resource_id (court), a start_date (UTC),
       and a list of slots with UTC start_time and duration.
    2. We combine start_date + start_time as UTC, convert to AEST, then check
       if the AEST date matches target_date.
    3. We expand each slot into N × 30-min blocks.
    4. We keep only blocks that fall within the club's opening hours.

    Why target_date filter? The API may return slots for adjacent UTC dates
    that belong to a different AEST day — we only want target_date's slots.
    """
    open_dt, close_dt = get_opening_hours(target_date)
    court_blocks: dict[str, set[str]] = {}

    for entry in raw:
        court_id   = entry["resource_id"]
        utc_date   = entry["start_date"]   # e.g. "2026-04-30"
        slots      = entry.get("slots", [])

        for slot in slots:
            duration = slot["duration"]

            # ── Only process 60-min slots and above (or 30-min if they appear)
            # 45-min is treated as 2 blocks (ceil); all others by same formula.
            # Skip durations we've already covered via a larger slot at same time
            # (deduplication happens naturally via set addition below).

            # Convert UTC slot start → AEST datetime
            aest_dt = utc_slot_to_aest(utc_date, slot["start_time"])

            # Only process slots that belong to our target AEST date
            if aest_dt.date() != target_date:
                continue

            # Expand into 30-min blocks
            n_blocks = slot_duration_to_blocks(duration)
            for i in range(n_blocks):
                block_dt = aest_dt + timedelta(minutes=i * BLOCK_MINUTES)

                # Clip to opening hours: block must start within open window
                if block_dt < open_dt or block_dt >= close_dt:
                    continue

                block_key = block_dt.strftime("%H:%M")

                if court_id not in court_blocks:
                    court_blocks[court_id] = set()
                court_blocks[court_id].add(block_key)

    return court_blocks


# ─────────────────────────────────────────────────────────────────────────────
# PERSISTENCE — save/load snapshots and slot history
# ─────────────────────────────────────────────────────────────────────────────

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def save_json(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# SNAPSHOT LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def update_snapshots(
    target_date: date,
    court_blocks: dict[str, set[str]],
    snapshots: dict,
    slot_history: dict,
) -> tuple[dict, dict]:
    """
    Update the running snapshots and slot history based on the latest poll.

    snapshots structure:
    {
      "2026-05-01": {
        "court_id_1": ["06:00", "06:30", ...],   # last known available blocks
        ...
      }
    }

    slot_history structure:
    {
      "2026-05-01": {
        "court_id_1": {
          "06:00": {
            "status":              "available" | "booked" | "went_unbooked",
            "first_seen_available": "ISO timestamp",
            "last_seen_available":  "ISO timestamp",
            "finalised":            true | false   # true once the slot is in the past
          },
          ...
        }
      }
    }

    Logic for each 30-min block in the expected full day:
    - If API shows it as available → mark "available", update last_seen_available
    - If API does NOT show it as available:
        - If we've NEVER seen it as available → mark "booked" (was booked before first poll)
        - If we HAD seen it as available before → mark "booked" (someone just booked it)
    - Once the block's start time is in the past → finalise it:
        - last known status becomes its final status
        - "available" past blocks → "went_unbooked" (nobody booked it)
        - "booked" past blocks stay "booked"
    """
    date_str     = target_date.strftime("%Y-%m-%d")
    full_day     = generate_full_day_blocks(target_date)
    now          = now_aest()
    now_iso      = now.isoformat()
    open_dt, _   = get_opening_hours(target_date)

    # Ensure nested dicts exist
    if date_str not in snapshots:
        snapshots[date_str] = {}
    if date_str not in slot_history:
        slot_history[date_str] = {}

    for court_id, available_blocks in court_blocks.items():
        if court_id not in slot_history[date_str]:
            slot_history[date_str][court_id] = {}

        prev_available = set(snapshots[date_str].get(court_id, []))

        for block_time_str in full_day:
            # Build the AEST datetime for this block so we can check if it's past
            block_dt = datetime.strptime(
                f"{date_str} {block_time_str}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=AEST)
            is_past = now >= block_dt + timedelta(minutes=BLOCK_MINUTES)

            history = slot_history[date_str][court_id].get(block_time_str, {
                "status":               "unknown",
                "first_seen_available": None,
                "last_seen_available":  None,
                "finalised":            False,
            })

            # Skip already-finalised slots (past + status locked)
            if history.get("finalised"):
                slot_history[date_str][court_id][block_time_str] = history
                continue

            if block_time_str in available_blocks:
                # ── API says this block is available right now ──
                if history["first_seen_available"] is None:
                    history["first_seen_available"] = now_iso
                history["last_seen_available"] = now_iso
                history["status"] = "available"

            else:
                # ── API does NOT show this block as available ──
                if history["first_seen_available"] is None:
                    # Never seen as available → booked before we started polling
                    history["status"] = "booked"
                else:
                    # Was available in a previous snapshot, now gone → just booked
                    history["status"] = "booked"

            # Finalise past slots — lock in their fate
            if is_past and not history["finalised"]:
                if history["status"] == "available":
                    # Still showed as available after the slot ended → went unbooked
                    history["status"] = "went_unbooked"
                history["finalised"] = True

            slot_history[date_str][court_id][block_time_str] = history

        # Update snapshot for this court with the current available set
        snapshots[date_str][court_id] = sorted(available_blocks)

    # Handle courts that appeared in a previous snapshot but NOT in this poll
    # (e.g. all their slots are now booked — they return nothing)
    for court_id in snapshots.get(date_str, {}):
        if court_id not in court_blocks:
            # Court has zero available blocks now — treat all as booked
            if court_id not in slot_history[date_str]:
                slot_history[date_str][court_id] = {}
            for block_time_str in full_day:
                block_dt = datetime.strptime(
                    f"{date_str} {block_time_str}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=AEST)
                is_past = now >= block_dt + timedelta(minutes=BLOCK_MINUTES)
                history = slot_history[date_str][court_id].get(block_time_str, {
                    "status":               "booked",
                    "first_seen_available": None,
                    "last_seen_available":  None,
                    "finalised":            False,
                })
                if not history.get("finalised"):
                    if history["first_seen_available"] is None:
                        history["status"] = "booked"
                    else:
                        history["status"] = "booked"
                    if is_past:
                        history["finalised"] = True
                    slot_history[date_str][court_id][block_time_str] = history

    return snapshots, slot_history


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def build_utilisation_report(slot_history: dict, target_date: date) -> dict:
    """
    Calculate utilisation stats for target_date.

    For each court, for each 30-min block in the full day:
      - "booked"        → counts as booked time
      - "went_unbooked" → counts as unbooked time
      - "available"     → still open (future or current); excluded from finalised stats
      - "unknown"       → never seen; excluded

    Returns a dict with per-court and overall stats.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    full_day = generate_full_day_blocks(target_date)
    total_blocks_possible = len(full_day)  # same for every court

    courts_data = slot_history.get(date_str, {})
    report = {
        "date":          date_str,
        "total_blocks":  total_blocks_possible,
        "block_minutes": BLOCK_MINUTES,
        "courts":        {},
        "overall":       {},
    }

    all_booked   = 0
    all_unbooked = 0
    all_unknown  = 0

    for court_id, blocks in courts_data.items():
        booked   = 0
        unbooked = 0
        unknown  = 0

        for block_time_str in full_day:
            h = blocks.get(block_time_str, {})
            status = h.get("status", "unknown")
            if status == "booked":
                booked += 1
            elif status == "went_unbooked":
                unbooked += 1
            else:
                # "available" (future/current) and "unknown" both excluded from ratio
                unknown += 1

        finalised = booked + unbooked
        utilisation_pct = (booked / finalised * 100) if finalised > 0 else None

        report["courts"][court_id] = {
            "booked_blocks":   booked,
            "unbooked_blocks": unbooked,
            "pending_blocks":  unknown,
            "booked_hours":    round(booked   * BLOCK_MINUTES / 60, 1),
            "unbooked_hours":  round(unbooked * BLOCK_MINUTES / 60, 1),
            "utilisation_pct": round(utilisation_pct, 1) if utilisation_pct is not None else "N/A (no finalised data)",
        }

        all_booked   += booked
        all_unbooked += unbooked
        all_unknown  += unknown

    # Overall across all courts
    total_finalised = all_booked + all_unbooked
    overall_util = (all_booked / total_finalised * 100) if total_finalised > 0 else None

    n_courts = len(courts_data) or 1
    report["overall"] = {
        "courts_tracked":       len(courts_data),
        "total_booked_blocks":  all_booked,
        "total_unbooked_blocks":all_unbooked,
        "total_booked_hours":   round(all_booked   * BLOCK_MINUTES / 60, 1),
        "total_unbooked_hours": round(all_unbooked * BLOCK_MINUTES / 60, 1),
        "avg_booked_hours_per_court":   round(all_booked   * BLOCK_MINUTES / 60 / n_courts, 1),
        "avg_unbooked_hours_per_court": round(all_unbooked * BLOCK_MINUTES / 60 / n_courts, 1),
        "utilisation_pct": round(overall_util, 1) if overall_util is not None else "N/A (no finalised data)",
    }

    return report


def print_report(report: dict):
    """Pretty-print the utilisation report to stdout."""
    print("\n" + "═" * 60)
    print(f"  COURT UTILISATION REPORT  —  {report['date']}")
    print(f"  Block size: {report['block_minutes']} min  |  "
          f"Total blocks/court/day: {report['total_blocks']} "
          f"({report['total_blocks'] * report['block_minutes'] // 60}h)")
    print("═" * 60)

    for court_id, stats in report["courts"].items():
        print(f"\n  Court: {court_id}")
        print(f"    Booked   : {stats['booked_blocks']:>3} blocks  ({stats['booked_hours']}h)")
        print(f"    Unbooked : {stats['unbooked_blocks']:>3} blocks  ({stats['unbooked_hours']}h)")
        print(f"    Pending  : {stats['pending_blocks']:>3} blocks  (future/current)")
        print(f"    Utilisation (finalised): {stats['utilisation_pct']}%")

    o = report["overall"]
    print("\n" + "─" * 60)
    print(f"  OVERALL ({o['courts_tracked']} courts)")
    print(f"    Total booked  : {o['total_booked_hours']}h  |  avg {o['avg_booked_hours_per_court']}h/court")
    print(f"    Total unbooked: {o['total_unbooked_hours']}h  |  avg {o['avg_unbooked_hours_per_court']}h/court")
    print(f"    Overall utilisation: {o['utilisation_pct']}%")
    print("═" * 60 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN POLL CYCLE
# ─────────────────────────────────────────────────────────────────────────────

def run_poll():
    """
    Execute one full poll cycle:
      1. Fetch today's availability from the API (using AEST local date)
      2. Parse and unwrap UTC → AEST, expand into 30-min blocks
      3. Load existing snapshots + slot history from disk
      4. Update with new data
      5. Save back to disk
      6. Print report
    """
    ensure_data_dir()

    target_date = today_aest()
    print(f"[{now_aest().strftime('%Y-%m-%d %H:%M:%S')} AEST]  Poll starting for {target_date}")

    # 1. Fetch
    raw = fetch_availability(target_date)

    # 2. Parse: UTC → AEST, expand to 30-min blocks, filter to target_date
    court_blocks = parse_response(raw, target_date)

    courts_found = list(court_blocks.keys())
    print(f"  Courts in response: {len(courts_found)}")
    for cid in courts_found:
        print(f"    {cid}: {len(court_blocks[cid])} available 30-min blocks in AEST")

    # 3. Load persistence
    snapshots    = load_json(SNAPSHOT_FILE)
    slot_history = load_json(HISTORY_FILE)

    # 4. Update
    snapshots, slot_history = update_snapshots(
        target_date, court_blocks, snapshots, slot_history
    )

    # 5. Save
    save_json(SNAPSHOT_FILE, snapshots)
    save_json(HISTORY_FILE, slot_history)

    # 6. Report
    report = build_utilisation_report(slot_history, target_date)
    print_report(report)

    print(f"  Data saved to {DATA_DIR}/")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Playtomic court utilisation tracker")
    parser.add_argument(
        "--loop",   action="store_true",
        help=f"Poll continuously every {POLL_INTERVAL_SECONDS}s"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Print utilisation report from saved data without polling"
    )
    args = parser.parse_args()

    if args.report:
        # Just print report from existing data
        ensure_data_dir()
        slot_history = load_json(HISTORY_FILE)
        if not slot_history:
            print("No saved data found. Run a poll first.")
            return
        report = build_utilisation_report(slot_history, today_aest())
        print_report(report)
        return

    if args.loop:
        print(f"Starting continuous poll loop (interval: {POLL_INTERVAL_SECONDS}s). Ctrl+C to stop.")
        while True:
            try:
                run_poll()
            except requests.HTTPError as e:
                print(f"  [ERROR] HTTP error: {e}")
            except Exception as e:
                print(f"  [ERROR] Unexpected error: {e}")
            print(f"  Sleeping {POLL_INTERVAL_SECONDS}s …\n")
            time.sleep(POLL_INTERVAL_SECONDS)
    else:
        run_poll()


if __name__ == "__main__":
    main()