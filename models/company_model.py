"""
=========================================================
Medical ERP V2
Company Model (minimal - Login screen needs this)
---------------------------------------------------------
Full Company Master (add/update/search/etc.) will be
built out later as its own module; this file currently
only provides what the Login screen's cmbCompany needs.
=========================================================
"""

from database.db import get_connection


def get_active_companies() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT companyid, companyname FROM company WHERE status = 'Active' ORDER BY companyname"
            )
            return cur.fetchall()


