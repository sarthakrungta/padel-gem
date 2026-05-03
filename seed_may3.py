"""
seed_may3.py — One-time May 3rd data seeder
============================================
Seeds May 3rd slot data for both clubs into Postgres.
Statuses are accurate. Timestamps are approximate.
Safe to run multiple times — skips if data already exists.

Run once then remove from railway.toml start command.
"""

import os
import sys
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

# Timestamps — approximate but reasonable
FIRST_SEEN   = "2026-05-03T06:08:09+10:00"
LAST_SEEN    = "2026-05-03T21:00:00+10:00"  # end of day
UPDATED_AT   = "2026-05-03T23:59:00+10:00"

def row(date, club, court, block, status, first=None, last=None):
    f = FIRST_SEEN if first is None and status in ("available", "went_unbooked") else first
    l = LAST_SEEN  if last  is None and status in ("available", "went_unbooked") else last
    return (date, club, court, block, status, f, l, 1, UPDATED_AT)

D  = "2026-05-03"
SE = "south_east_padel"
G4 = "game4padel_richmond"

C1 = "4a5fb5fe-139f-40b0-85e7-634c705d7284"  # SEP Court 1
C2 = "6a01f11b-3f57-4e81-bf0d-c1359d82caef"  # SEP Court 2
C3 = "e60b3a03-4c04-4021-a531-626d7d973135"  # SEP Court 3

GA = "14929aea-a5d3-4ed9-bb45-2dd602292abf"  # G4P Court 1
GB = "5bd1f97a-96cd-430b-968c-8895873f00e4"  # G4P Court 2
GC = "98026b0c-9627-4d24-92a8-fd100dd77ac7"  # G4P Court 3
GD = "b494a00e-f87b-4d2f-9b47-330670234cbb"  # G4P Court 4
GE = "c7867aac-4ae3-4ed1-b5d9-fce0bee53151"  # G4P Court 5
GF = "f30f0a7e-8ead-4b17-bbf0-9c6a78da0384"  # G4P Court 6

MAY3_ROWS = [
    # ── South East Padel — Court 1 (4a5fb5fe) ────────────────────────────────
    row(D, SE, C1, "08:00", "went_unbooked"),
    row(D, SE, C1, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, SE, C1, "09:00", "went_unbooked"),
    row(D, SE, C1, "09:30", "went_unbooked"),
    row(D, SE, C1, "10:00", "went_unbooked"),
    row(D, SE, C1, "10:30", "went_unbooked"),
    row(D, SE, C1, "11:00", "went_unbooked"),
    row(D, SE, C1, "11:30", "available"),
    row(D, SE, C1, "12:00", "available"),
    row(D, SE, C1, "12:30", "available"),
    row(D, SE, C1, "13:00", "available"),
    row(D, SE, C1, "13:30", "available"),
    row(D, SE, C1, "14:00", "available"),
    row(D, SE, C1, "14:30", "available"),
    row(D, SE, C1, "15:00", "available"),
    row(D, SE, C1, "15:30", "available"),
    row(D, SE, C1, "16:00", "available"),
    row(D, SE, C1, "16:30", "available"),
    row(D, SE, C1, "17:00", "available"),
    row(D, SE, C1, "17:30", "available"),

    # ── South East Padel — Court 2 (6a01f11b) ────────────────────────────────
    row(D, SE, C2, "08:00", "went_unbooked"),
    row(D, SE, C2, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, SE, C2, "09:00", "went_unbooked"),
    row(D, SE, C2, "09:30", "went_unbooked"),
    row(D, SE, C2, "10:00", "went_unbooked"),
    row(D, SE, C2, "10:30", "went_unbooked"),
    row(D, SE, C2, "11:00", "went_unbooked"),
    row(D, SE, C2, "11:30", "available"),
    row(D, SE, C2, "12:00", "available"),
    row(D, SE, C2, "12:30", "available"),
    row(D, SE, C2, "13:00", "available"),
    row(D, SE, C2, "13:30", "booked", None, None),
    row(D, SE, C2, "14:00", "booked", None, None),
    row(D, SE, C2, "14:30", "available"),
    row(D, SE, C2, "15:00", "available"),
    row(D, SE, C2, "15:30", "available"),
    row(D, SE, C2, "16:00", "available"),
    row(D, SE, C2, "16:30", "available"),
    row(D, SE, C2, "17:00", "available"),
    row(D, SE, C2, "17:30", "available"),

    # ── South East Padel — Court 3 (e60b3a03) ────────────────────────────────
    row(D, SE, C3, "08:00", "went_unbooked"),
    row(D, SE, C3, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, SE, C3, "09:00", "went_unbooked"),
    row(D, SE, C3, "09:30", "went_unbooked"),
    row(D, SE, C3, "10:00", "went_unbooked"),
    row(D, SE, C3, "10:30", "went_unbooked"),
    row(D, SE, C3, "11:00", "went_unbooked"),
    row(D, SE, C3, "11:30", "available"),  # was briefly booked, then cancelled ~10:10
    row(D, SE, C3, "12:00", "available"),
    row(D, SE, C3, "12:30", "available"),
    row(D, SE, C3, "13:00", "available"),
    row(D, SE, C3, "13:30", "available"),
    row(D, SE, C3, "14:00", "available"),
    row(D, SE, C3, "14:30", "available"),
    row(D, SE, C3, "15:00", "available"),
    row(D, SE, C3, "15:30", "available"),
    row(D, SE, C3, "16:00", "available"),
    row(D, SE, C3, "16:30", "available"),
    row(D, SE, C3, "17:00", "available"),
    row(D, SE, C3, "17:30", "available"),

    # ── Game4Padel Richmond — Court 1 (14929aea) ─────────────────────────────
    row(D, G4, GA, "08:00", "went_unbooked"),
    row(D, G4, GA, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, G4, GA, "09:00", "booked", None, None),
    row(D, G4, GA, "09:30", "booked", None, None),
    row(D, G4, GA, "10:00", "went_unbooked"),
    row(D, G4, GA, "10:30", "booked", None, None),
    row(D, G4, GA, "11:00", "booked", None, None),
    row(D, G4, GA, "11:30", "booked", None, None),
    row(D, G4, GA, "12:00", "booked", None, None),
    row(D, G4, GA, "12:30", "available"),
    row(D, G4, GA, "13:00", "available"),
    row(D, G4, GA, "13:30", "available"),
    row(D, G4, GA, "14:00", "available"),
    row(D, G4, GA, "14:30", "available"),
    row(D, G4, GA, "15:00", "available"),
    row(D, G4, GA, "15:30", "available"),
    row(D, G4, GA, "16:00", "available"),
    row(D, G4, GA, "16:30", "available"),
    row(D, G4, GA, "17:00", "booked", None, None),
    row(D, G4, GA, "17:30", "booked", None, None),
    row(D, G4, GA, "18:00", "booked", None, None),
    row(D, G4, GA, "18:30", "available"),
    row(D, G4, GA, "19:00", "available"),
    row(D, G4, GA, "19:30", "available"),
    row(D, G4, GA, "20:00", "available"),
    row(D, G4, GA, "20:30", "available"),

    # ── Game4Padel Richmond — Court 2 (5bd1f97a) ─────────────────────────────
    row(D, G4, GB, "08:00", "went_unbooked"),
    row(D, G4, GB, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, G4, GB, "09:00", "booked", None, None),
    row(D, G4, GB, "09:30", "booked", None, None),
    row(D, G4, GB, "10:00", "booked", None, None),
    row(D, G4, GB, "10:30", "went_unbooked"),
    row(D, G4, GB, "11:00", "booked", None, None),
    row(D, G4, GB, "11:30", "booked", None, None),
    row(D, G4, GB, "12:00", "booked", None, None),
    row(D, G4, GB, "12:30", "booked", None, None),
    row(D, G4, GB, "13:00", "available"),
    row(D, G4, GB, "13:30", "available"),
    row(D, G4, GB, "14:00", "available"),
    row(D, G4, GB, "14:30", "available"),
    row(D, G4, GB, "15:00", "available"),
    row(D, G4, GB, "15:30", "booked", None, None),
    row(D, G4, GB, "16:00", "booked", None, None),
    row(D, G4, GB, "16:30", "booked", None, None),
    row(D, G4, GB, "17:00", "booked", None, None),
    row(D, G4, GB, "17:30", "booked", None, None),
    row(D, G4, GB, "18:00", "booked", None, None),
    row(D, G4, GB, "18:30", "booked", None, None),
    row(D, G4, GB, "19:00", "booked", None, None),
    row(D, G4, GB, "19:30", "available"),
    row(D, G4, GB, "20:00", "available"),
    row(D, G4, GB, "20:30", "available"),

    # ── Game4Padel Richmond — Court 3 (98026b0c) ─────────────────────────────
    row(D, G4, GC, "08:00", "went_unbooked"),
    row(D, G4, GC, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, G4, GC, "09:00", "booked", None, None),
    row(D, G4, GC, "09:30", "booked", None, None),
    row(D, G4, GC, "10:00", "booked", None, None),
    row(D, G4, GC, "10:30", "went_unbooked"),
    row(D, G4, GC, "11:00", "booked", None, None),
    row(D, G4, GC, "11:30", "booked", None, None),
    row(D, G4, GC, "12:00", "booked", None, None),
    row(D, G4, GC, "12:30", "booked", None, None),
    row(D, G4, GC, "13:00", "booked", None, None),
    row(D, G4, GC, "13:30", "booked", None, None),
    row(D, G4, GC, "14:00", "booked", None, None),
    row(D, G4, GC, "14:30", "booked", None, None),
    row(D, G4, GC, "15:00", "booked", None, None),
    row(D, G4, GC, "15:30", "available"),
    row(D, G4, GC, "16:00", "available"),
    row(D, G4, GC, "16:30", "available"),
    row(D, G4, GC, "17:00", "booked", None, None),
    row(D, G4, GC, "17:30", "booked", None, None),
    row(D, G4, GC, "18:00", "booked", None, None),
    row(D, G4, GC, "18:30", "booked", None, None),
    row(D, G4, GC, "19:00", "booked", None, None),
    row(D, G4, GC, "19:30", "available"),
    row(D, G4, GC, "20:00", "available"),
    row(D, G4, GC, "20:30", "available"),

    # ── Game4Padel Richmond — Court 4 (b494a00e) ─────────────────────────────
    row(D, G4, GD, "08:00", "went_unbooked"),
    row(D, G4, GD, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, G4, GD, "09:00", "booked", None, None),
    row(D, G4, GD, "09:30", "booked", None, None),
    row(D, G4, GD, "10:00", "went_unbooked"),
    row(D, G4, GD, "10:30", "went_unbooked"),
    row(D, G4, GD, "11:00", "booked", None, None),
    row(D, G4, GD, "11:30", "booked", None, None),
    row(D, G4, GD, "12:00", "booked", None, None),
    row(D, G4, GD, "12:30", "booked", None, None),
    row(D, G4, GD, "13:00", "booked", None, None),
    row(D, G4, GD, "13:30", "available"),
    row(D, G4, GD, "14:00", "available"),
    row(D, G4, GD, "14:30", "available"),
    row(D, G4, GD, "15:00", "available"),
    row(D, G4, GD, "15:30", "available"),
    row(D, G4, GD, "16:00", "available"),
    row(D, G4, GD, "16:30", "booked", None, None),
    row(D, G4, GD, "17:00", "booked", None, None),
    row(D, G4, GD, "17:30", "booked", None, None),
    row(D, G4, GD, "18:00", "booked", None, None),
    row(D, G4, GD, "18:30", "booked", None, None),
    row(D, G4, GD, "19:00", "available"),
    row(D, G4, GD, "19:30", "available"),
    row(D, G4, GD, "20:00", "available"),
    row(D, G4, GD, "20:30", "available"),

    # ── Game4Padel Richmond — Court 5 (c7867aac) ─────────────────────────────
    row(D, G4, GE, "08:00", "went_unbooked"),
    row(D, G4, GE, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, G4, GE, "09:00", "booked", None, None),
    row(D, G4, GE, "09:30", "booked", None, None),
    row(D, G4, GE, "10:00", "booked", None, None),
    row(D, G4, GE, "10:30", "booked", None, None),
    row(D, G4, GE, "11:00", "booked", None, None),
    row(D, G4, GE, "11:30", "booked", None, None),
    row(D, G4, GE, "12:00", "booked", None, None),
    row(D, G4, GE, "12:30", "booked", None, None),
    row(D, G4, GE, "13:00", "booked", None, None),
    row(D, G4, GE, "13:30", "available"),
    row(D, G4, GE, "14:00", "available"),
    row(D, G4, GE, "14:30", "booked", None, None),
    row(D, G4, GE, "15:00", "booked", None, None),
    row(D, G4, GE, "15:30", "booked", None, None),
    row(D, G4, GE, "16:00", "booked", None, None),
    row(D, G4, GE, "16:30", "booked", None, None),
    row(D, G4, GE, "17:00", "booked", None, None),
    row(D, G4, GE, "17:30", "booked", None, None),
    row(D, G4, GE, "18:00", "booked", None, None),
    row(D, G4, GE, "18:30", "booked", None, None),
    row(D, G4, GE, "19:00", "booked", None, None),
    row(D, G4, GE, "19:30", "booked", None, None),
    row(D, G4, GE, "20:00", "available"),
    row(D, G4, GE, "20:30", "available"),

    # ── Game4Padel Richmond — Court 6 (f30f0a7e) ─────────────────────────────
    row(D, G4, GF, "08:00", "went_unbooked"),
    row(D, G4, GF, "08:30", "booked", FIRST_SEEN, "2026-05-03T07:59:00+10:00"),
    row(D, G4, GF, "09:00", "booked", None, None),
    row(D, G4, GF, "09:30", "booked", None, None),
    row(D, G4, GF, "10:00", "booked", None, None),
    row(D, G4, GF, "10:30", "booked", None, None),
    row(D, G4, GF, "11:00", "booked", None, None),
    row(D, G4, GF, "11:30", "booked", None, None),
    row(D, G4, GF, "12:00", "booked", None, None),
    row(D, G4, GF, "12:30", "booked", None, None),
    row(D, G4, GF, "13:00", "available"),
    row(D, G4, GF, "13:30", "available"),
    row(D, G4, GF, "14:00", "available"),
    row(D, G4, GF, "14:30", "booked", None, None),
    row(D, G4, GF, "15:00", "booked", None, None),
    row(D, G4, GF, "15:30", "booked", None, None),
    row(D, G4, GF, "16:00", "booked", None, None),
    row(D, G4, GF, "16:30", "booked", None, None),
    row(D, G4, GF, "17:00", "booked", None, None),
    row(D, G4, GF, "17:30", "booked", None, None),
    row(D, G4, GF, "18:00", "booked", None, None),
    row(D, G4, GF, "18:30", "booked", None, None),
    row(D, G4, GF, "19:00", "booked", None, None),
    row(D, G4, GF, "19:30", "booked", None, None),
    row(D, G4, GF, "20:00", "booked", None, None),
    row(D, G4, GF, "20:30", "booked", None, None),
]


def seed_may3():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            for club in [SE, G4]:
                cur.execute(
                    "SELECT COUNT(*) FROM slot_states WHERE query_date=%s AND club_id=%s",
                    (D, club)
                )
                existing = cur.fetchone()[0]
                if existing > 0:
                    print(f"[seed_may3] {club}: May 3rd already present ({existing} rows) — skipping.")
                    return

            psycopg2.extras.execute_values(cur, """
                INSERT INTO slot_states
                    (query_date, club_id, court_id, block_time, status,
                     first_seen_available, last_seen_available, finalised, updated_at)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, MAY3_ROWS)
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM slot_states WHERE query_date=%s", (D,))
            inserted = cur.fetchone()[0]
            print(f"[seed_may3] ✓ Inserted {inserted} May 3rd rows across both clubs.")

    except Exception as e:
        conn.rollback()
        print(f"[seed_may3] ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed_may3()