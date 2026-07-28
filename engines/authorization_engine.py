"""
=========================================================
Medical ERP V2
Authorization Engine
---------------------------------------------------------
Responsibilities:
    - Role validation
    - Permission validation
    - Screen access
    - Menu access
    - Button permissions
=========================================================
"""

from database.db import get_connection

PERMISSION_COLUMNS = (
    "can_view", "can_add", "can_edit", "can_delete", "can_restore",
    "can_print", "can_export", "can_import", "can_approve",
    "can_cancel", "can_lock", "can_unlock",
)


def get_permissions_for_screen(roleid: int, screenname: str) -> dict:
    """
    Returns the full permission row for a role+screen as a
    dict, e.g. {"can_view": True, "can_add": False, ...}.
    If no row exists for this role+screen, every permission
    defaults to False (deny by default).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM role_permissions WHERE roleid = %s AND screenname = %s",
                (roleid, screenname)
            )
            row = cur.fetchone()

    if row is None:
        return {col: False for col in PERMISSION_COLUMNS}

    return {col: bool(row[col]) for col in PERMISSION_COLUMNS}


def has_permission(roleid: int, screenname: str, action: str) -> bool:
    """
    Checks a single permission, e.g.
    has_permission(roleid, "PurchaseScreen", "can_delete")
    """
    if action not in PERMISSION_COLUMNS:
        raise ValueError(f"Unknown permission action: {action}")

    permissions = get_permissions_for_screen(roleid, screenname)
    return permissions[action]


def get_accessible_menus(roleid: int) -> list[str]:
    """
    Returns the list of distinct screen names this role has
    at least View access to - used to build the Dashboard's
    navigation menu.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT screenname FROM role_permissions WHERE roleid = %s AND can_view = TRUE",
                (roleid,)
            )
            rows = cur.fetchall()

    return [row["screenname"] for row in rows]
