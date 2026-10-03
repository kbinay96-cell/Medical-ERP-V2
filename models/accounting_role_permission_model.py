"""Data access for accounting-specific role permissions."""

from __future__ import annotations

from models.accounting_connection import accounting_connection

ACCOUNTING_ROLES = ("Accountant", "Senior Accountant", "Manager", "Admin", "Auditor")
ACCOUNTING_PERMISSIONS = (
    "Create", "Edit", "Post", "Cancel", "Reverse", "Approve", "View", "Export", "Period Unlock"
)


class AccountingRolePermissionModel:
    def get_permissions_for_role(self, role_name: str) -> dict[str, bool]:
        normalized = (role_name or "").strip().casefold()
        role_name = {
            "administrator": "Admin",
            "admin": "Admin",
            "owner": "Manager",
        }.get(normalized, role_name)
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT permission_name, is_granted
                FROM accounting_role_permission
                WHERE role_name = %s;
                """,
                (role_name,),
            )
            permissions = {row["permission_name"]: bool(row["is_granted"]) for row in cur.fetchall()}
        return {permission: permissions.get(permission, False) for permission in ACCOUNTING_PERMISSIONS}

    def set_permission(self, role_name: str, permission_name: str, is_granted: bool) -> None:
        if role_name not in ACCOUNTING_ROLES or permission_name not in ACCOUNTING_PERMISSIONS:
            raise ValueError("Unknown accounting role or permission.")
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO accounting_role_permission (role_name, permission_name, is_granted)
                VALUES (%s, %s, %s)
                ON CONFLICT (role_name, permission_name)
                DO UPDATE SET is_granted = EXCLUDED.is_granted;
                """,
                (role_name, permission_name, is_granted),
            )

    def seed_defaults(self) -> None:
        grants = {
            "Accountant": {"Create", "Edit", "Post", "View"},
            "Senior Accountant": {"Create", "Edit", "Post", "Cancel", "Reverse", "View", "Export"},
            "Manager": set(ACCOUNTING_PERMISSIONS),
            "Admin": set(ACCOUNTING_PERMISSIONS),
            "Auditor": {"View", "Export"},
        }
        rows = [
            (role, permission, permission in grants[role])
            for role in ACCOUNTING_ROLES
            for permission in ACCOUNTING_PERMISSIONS
        ]
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO accounting_role_permission (role_name, permission_name, is_granted)
                VALUES (%s, %s, %s)
                ON CONFLICT (role_name, permission_name) DO NOTHING;
                """,
                rows,
            )
