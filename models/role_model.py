"""
=========================================================
Medical ERP V2
Role Model
---------------------------------------------------------
Minimal operations needed right now (role lookup for the
Authentication Engine). Full Role Master screen (add/edit/
assign permissions) will be its own module later.
=========================================================
"""

from database.db import get_connection


def get_role_by_id(roleid: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM roles WHERE roleid = %s", (roleid,))
            return cur.fetchone()


def get_role_name(roleid: int) -> str:
    role = get_role_by_id(roleid)
    return role["rolename"] if role else "Unknown"
