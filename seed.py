"""
seed.py — One-time historical data seeder
==========================================
Seeds May 2nd (South East Padel, all 60 rows) into the fresh Postgres DB.
Safe to run multiple times — skips if data already exists.

Usage:
  DATABASE_URL=<url> python seed.py
"""

import os
import sys
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

# All 60 finalised May 2nd rows for South East Padel
# (query_date, club_id, court_id, block_time, status,
#  first_seen_available, last_seen_available, finalised, updated_at)
MAY2_ROWS = [
    # Court 1
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","08:00","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T07:57:30.461726+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","08:30","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T07:57:30.461726+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","09:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","09:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","10:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","10:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","11:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","11:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T11:28:39.851459+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","12:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T11:28:39.851459+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","12:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","13:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","13:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","14:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","14:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","15:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","15:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T15:29:58.601582+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","16:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T15:29:58.601582+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","16:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T16:30:17.687744+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","17:00","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T17:00:28.194935+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","4a5fb5fe-139f-40b0-85e7-634c705d7284","17:30","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T17:00:28.194935+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    # Court 2
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","08:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","08:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","09:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","09:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T09:28:00.262586+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","10:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T09:28:00.262586+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","10:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","11:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","11:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T11:28:39.851459+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","12:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T11:28:39.851459+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","12:30","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T10:18:17.105752+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","13:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T10:18:17.105752+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","13:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T13:29:19.850638+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","14:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T13:29:19.850638+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","14:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T14:29:39.350097+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","15:00","went_unbooked","2026-05-02T11:03:31.647380+10:00","2026-05-02T14:54:47.524431+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","15:30","booked","2026-05-02T11:03:31.647380+10:00","2026-05-02T14:54:47.524431+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","16:00","booked","2026-05-02T11:03:31.647380+10:00","2026-05-02T14:54:47.524431+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","16:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T16:30:17.687744+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","17:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T16:30:17.687744+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","6a01f11b-3f57-4e81-bf0d-c1359d82caef","17:30","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T16:30:17.687744+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    # Court 3
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","08:00","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T07:57:30.461726+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","08:30","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T07:57:30.461726+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","09:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","09:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","10:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","10:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","11:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","11:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T11:28:39.851459+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","12:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T11:28:39.851459+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","12:30","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T11:28:39.851459+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","13:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","13:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","14:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","14:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","15:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","15:30","went_unbooked","2026-05-02T05:41:43.401489+10:00","2026-05-02T15:29:58.601582+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","16:00","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T15:29:58.601582+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","16:30","booked","2026-05-02T05:41:43.401489+10:00","2026-05-02T15:29:58.601582+10:00",1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","17:00","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
    ("2026-05-02","south_east_padel","e60b3a03-4c04-4021-a531-626d7d973135","17:30","booked",None,None,1,"2026-05-02T23:57:43.261687+10:00"),
]


def seed():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            # Create tables if they don't exist yet (first ever deploy)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS polls (
                    id          SERIAL PRIMARY KEY,
                    polled_at   TEXT NOT NULL,
                    query_date  TEXT NOT NULL,
                    club_id     TEXT NOT NULL DEFAULT 'south_east_padel',
                    success     INTEGER NOT NULL DEFAULT 1,
                    error_msg   TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS slot_states (
                    id                   SERIAL PRIMARY KEY,
                    query_date           TEXT NOT NULL,
                    club_id              TEXT NOT NULL,
                    court_id             TEXT NOT NULL,
                    block_time           TEXT NOT NULL,
                    status               TEXT NOT NULL,
                    first_seen_available TEXT,
                    last_seen_available  TEXT,
                    finalised            INTEGER NOT NULL DEFAULT 0,
                    updated_at           TEXT NOT NULL,
                    UNIQUE (query_date, club_id, court_id, block_time)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ss_date  ON slot_states (query_date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ss_club  ON slot_states (club_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ss_court ON slot_states (court_id)")
            conn.commit()
            print("[seed] Tables ready.")

            cur.execute(
                "SELECT COUNT(*) FROM slot_states WHERE query_date='2026-05-02' AND club_id='south_east_padel'"
            )
            existing = cur.fetchone()[0]
            if existing > 0:
                print(f"[seed] May 2nd already present ({existing} rows) — skipping.")
                return

            psycopg2.extras.execute_values(cur, """
                INSERT INTO slot_states
                    (query_date, club_id, court_id, block_time, status,
                     first_seen_available, last_seen_available, finalised, updated_at)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, MAY2_ROWS)
            conn.commit()

            cur.execute(
                "SELECT COUNT(*) FROM slot_states WHERE query_date='2026-05-02' AND club_id='south_east_padel'"
            )
            inserted = cur.fetchone()[0]
            print(f"[seed] ✓ Inserted {inserted} May 2nd rows for South East Padel.")

    except Exception as e:
        conn.rollback()
        print(f"[seed] ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()