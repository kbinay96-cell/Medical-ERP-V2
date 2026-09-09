"""
=========================================================
Medical ERP V2
Financial Year Model (minimal - Login screen needs this)
=========================================================
"""

from database.db import get_connection


def get_all_financial_years() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT financialyearid, financialyear, isactive, isclosed
                FROM financialyear
                WHERE isclosed = FALSE
                ORDER BY financialyear DESC
                """
            )
            return cur.fetchall()


def get_active_financial_year() -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM financialyear WHERE isactive = TRUE LIMIT 1")
            return cur.fetchone()

def insert_financial_year(financialyear: str, startbsdate: str, endbsdate: str,
                          startaddate, endaddate, isactive: bool = True) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO financialyear
                    (financialyear, startbsdate, endbsdate, startaddate, endaddate, isactive, isclosed)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                RETURNING financialyearid
                """,
                (financialyear, startbsdate, endbsdate, startaddate, endaddate, isactive)
            )
            fid = cur.fetchone()["financialyearid"]
        conn.commit()
        return fid
