"""
fix_may3_morning.py — Corrects May 3rd morning slots
=====================================================
The poller started fresh at ~11:14am with no prior history, so all slots
before that point were marked as 'booked' by default. This script corrects
the morning slots (08:00–11:00) based on what actually happened.

Only updates rows that currently show 'booked' — leaves anything already
correct (went_unbooked, available) untouched.

Safe to run multiple times.
"""

import os
import sys
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

D  = "2026-05-03"
SE = "south_east_padel"
G4 = "game4padel_richmond"

C1 = "4a5fb5fe-139f-40b0-85e7-634c705d7284"
C2 = "6a01f11b-3f57-4e81-bf0d-c1359d82caef"
C3 = "e60b3a03-4c04-4021-a531-626d7d973135"

GA = "14929aea-a5d3-4ed9-bb45-2dd602292abf"
GB = "5bd1f97a-96cd-430b-968c-8895873f00e4"
GC = "98026b0c-9627-4d24-92a8-fd100dd77ac7"
GD = "b494a00e-f87b-4d2f-9b47-330670234cbb"
GE = "c7867aac-4ae3-4ed1-b5d9-fce0bee53151"
GF = "f30f0a7e-8ead-4b17-bbf0-9c6a78da0384"

FIRST_SEEN = "2026-05-03T06:08:09+10:00"
LAST_SEEN_WU = "2026-05-03T07:59:00+10:00"  # went_unbooked — last seen before slot start

# (club_id, court_id, block_time, correct_status, first_seen, last_seen, finalised)
# Only morning slots that need correcting.
# went_unbooked = was available, nobody booked it
# booked = correctly booked (leave these — they're already right in the DB)
CORRECTIONS = [
    # ── South East Padel ──────────────────────────────────────────────────────
    # All 3 courts: 08:00 went_unbooked, 08:30 booked (already correct), 09:00–11:00 went_unbooked
    (SE, C1, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),
    (SE, C1, "09:00", "went_unbooked", FIRST_SEEN, "2026-05-03T09:29:00+10:00", 1),
    (SE, C1, "09:30", "went_unbooked", FIRST_SEEN, "2026-05-03T09:44:00+10:00", 1),
    (SE, C1, "10:00", "went_unbooked", FIRST_SEEN, "2026-05-03T10:29:00+10:00", 1),
    (SE, C1, "10:30", "went_unbooked", FIRST_SEEN, "2026-05-03T10:59:00+10:00", 1),
    (SE, C1, "11:00", "went_unbooked", FIRST_SEEN, "2026-05-03T11:13:00+10:00", 1),

    (SE, C2, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),
    (SE, C2, "09:00", "went_unbooked", FIRST_SEEN, "2026-05-03T09:29:00+10:00", 1),
    (SE, C2, "09:30", "went_unbooked", FIRST_SEEN, "2026-05-03T09:44:00+10:00", 1),
    (SE, C2, "10:00", "went_unbooked", FIRST_SEEN, "2026-05-03T10:29:00+10:00", 1),
    (SE, C2, "10:30", "went_unbooked", FIRST_SEEN, "2026-05-03T10:59:00+10:00", 1),
    (SE, C2, "11:00", "went_unbooked", FIRST_SEEN, "2026-05-03T11:13:00+10:00", 1),

    (SE, C3, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),
    (SE, C3, "09:00", "went_unbooked", FIRST_SEEN, "2026-05-03T09:29:00+10:00", 1),
    (SE, C3, "09:30", "went_unbooked", FIRST_SEEN, "2026-05-03T09:44:00+10:00", 1),
    (SE, C3, "10:00", "went_unbooked", FIRST_SEEN, "2026-05-03T10:29:00+10:00", 1),
    (SE, C3, "10:30", "went_unbooked", FIRST_SEEN, "2026-05-03T10:59:00+10:00", 1),
    (SE, C3, "11:00", "went_unbooked", FIRST_SEEN, "2026-05-03T11:13:00+10:00", 1),

    # ── Game4Padel Richmond ───────────────────────────────────────────────────
    # All 6 courts: 08:00 went_unbooked
    (G4, GA, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),
    (G4, GB, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),
    (G4, GC, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),
    (G4, GD, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),
    (G4, GE, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),
    (G4, GF, "08:00", "went_unbooked", FIRST_SEEN, LAST_SEEN_WU, 1),

    # Court GA: 10:00 went_unbooked
    (G4, GA, "10:00", "went_unbooked", FIRST_SEEN, "2026-05-03T09:59:00+10:00", 1),

    # Court GB: 10:30 went_unbooked
    (G4, GB, "10:30", "went_unbooked", FIRST_SEEN, "2026-05-03T10:29:00+10:00", 1),

    # Court GC: 10:30 went_unbooked
    (G4, GC, "10:30", "went_unbooked", FIRST_SEEN, "2026-05-03T10:29:00+10:00", 1),

    # Court GD: 10:00 and 10:30 went_unbooked
    (G4, GD, "10:00", "went_unbooked", FIRST_SEEN, "2026-05-03T09:59:00+10:00", 1),
    (G4, GD, "10:30", "went_unbooked", FIRST_SEEN, "2026-05-03T10:29:00+10:00", 1),
]


def fix():
    conn = psycopg2.connect(DATABASE_URL)
    updated = 0
    skipped = 0
    try:
        with conn.cursor() as cur:
            for club_id, court_id, block_time, status, first_seen, last_seen, finalised in CORRECTIONS:
                # Only update if the row currently shows 'booked' — don't overwrite
                # anything the poller may have already correctly set
                cur.execute("""
                    UPDATE slot_states
                    SET status               = %s,
                        first_seen_available = %s,
                        last_seen_available  = %s,
                        finalised            = %s,
                        updated_at           = '2026-05-03T23:59:00+10:00'
                    WHERE query_date = %s
                      AND club_id    = %s
                      AND court_id   = %s
                      AND block_time = %s
                      AND status     = 'booked'
                """, (status, first_seen, last_seen, finalised,
                      D, club_id, court_id, block_time))

                if cur.rowcount > 0:
                    updated += 1
                else:
                    skipped += 1

        conn.commit()
        print(f"[fix_may3] ✓ Updated {updated} rows, skipped {skipped} (already correct or not found).")

    except Exception as e:
        conn.rollback()
        print(f"[fix_may3] ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    fix()