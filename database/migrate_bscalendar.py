"""
=========================================================
Medical ERP V2
bscalendar Migration Script (run ONCE)
---------------------------------------------------------
Copies the real, already-verified BS<->AD calendar data
from the V1 database (medical_erp) into the V2 database
(medical_erp_v2), so the new Date Engine has real data to
work with instead of inventing/faking any conversion.

Run from the Medical-ERP-V2 folder:
    python database/migrate_bscalendar.py

Edit V1_DB_CONFIG below if your V1 database connection
details are different.
=========================================================
"""

import psycopg2
import psycopg2.extras

from database.db import get_connection as get_v2_connection

V1_DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "medical_erp",
    "user": "postgres",
    "password": "postgres",
}


def migrate():
    print("Connecting to V1 database (medical_erp)...")
    v1_conn = psycopg2.connect(
        cursor_factory=psycopg2.extras.RealDictCursor, **V1_DB_CONFIG
    )
    v1_cursor = v1_conn.cursor()

    print("Reading bscalendar rows from V1...")
    v1_cursor.execute("""
        SELECT bsdate, addate, bsyear, bsmonth, bsday, monthnameen,
               weekdayno, weekdayen, financialyear, isweekend,
               isholiday, holidayname
        FROM bscalendar
        ORDER BY addate
    """)
    rows = v1_cursor.fetchall()
    print(f"Found {len(rows)} rows in V1 bscalendar.")

    if not rows:
        print("Nothing to migrate. Is the V1 bscalendar table populated?")
        v1_conn.close()
        return

    print("Connecting to V2 database (medical_erp_v2)...")
    v2_conn = get_v2_connection()
    v2_cursor = v2_conn.cursor()

    inserted = 0
    for row in rows:
        v2_cursor.execute(
            """
            INSERT INTO bscalendar (
                bsdate, addate, bsyear, bsmonth, bsday, monthnameen,
                weekdayno, weekdayen, financialyear, isweekend,
                isholiday, holidayname
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (bsdate) DO NOTHING
            """,
            (
                row["bsdate"], row["addate"], row["bsyear"], row["bsmonth"],
                row["bsday"], row["monthnameen"], row["weekdayno"],
                row["weekdayen"], row["financialyear"], row["isweekend"],
                row["isholiday"], row["holidayname"],
            )
        )
        inserted += 1

    v2_conn.commit()
    print(f"Migration complete. {inserted} rows processed into V2 bscalendar.")

    v1_conn.close()
    v2_conn.close()


if __name__ == "__main__":
    migrate()
