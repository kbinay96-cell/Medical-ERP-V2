"""
models/simple_master_model.py

Generic Simple Master Model - Medical ERP V2

Project rule: "No SQL outside the Model." This single, table-agnostic Model
serves every GENERIC lookup master (Category, Sub Category, Item Group,
Unit, Generic) because they all share an IDENTICAL table shape (see
database/schema_simple_masters.sql) -- one reusable class instead of five
near-duplicate files, per the project's "No Duplicate Logic" rule.

Manufacturer is NOT one of these tables -- it has its own dedicated
model/engine because of its distinct business rules (Country, auto
short-name generation, Settings-driven prefix, future tax integration).
Never route Manufacturer through this file.

Each concrete table is described by a MasterTableConfig (table name, id
column name, and -- for Sub Category only -- its scope column). This class
has NO business rules, NO validation, NO decisions -- it only executes SQL
and returns data. All business logic belongs in
engines/simple_master_engine.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from database.db import get_connection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MasterTableConfig:
    """
    Describes one simple lookup master table's shape so SimpleMasterModel /
    SimpleMasterEngine can operate on it generically.

    scope_column is only set for a SCOPED table (Sub Category -> "category_id").
    Leave it None for every unscoped table (Category, Item Group, Unit, Generic).
    """
    table_name: str
    id_column: str
    scope_column: Optional[str] = None
    code_prefix: str = "MST-"
    code_prefix_setting_key: str = ""  # e.g. "category.code_prefix" -- Settings key checked before falling back to code_prefix


class SimpleMasterModel:
    """Data-access layer for any table described by a MasterTableConfig. SQL only."""

    def __init__(self, config: MasterTableConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def insert(self, data: dict[str, Any]) -> int:
        """
        `data` must already contain every column this INSERT expects: code,
        name, status, remarks, created_by, created_at_ad, created_at_bs,
        and -- if this table is scoped -- the scope column too. The Engine
        is responsible for defaults and BS/AD stamping. Returns the new id.
        """
        cfg = self.config
        columns = ["code", "name", "status", "remarks", "created_by", "created_at_ad", "created_at_bs"]
        if cfg.scope_column:
            columns.append(cfg.scope_column)

        col_sql = ", ".join(columns)
        placeholder_sql = ", ".join(f"%({c})s" for c in columns)

        sql = f"""
            INSERT INTO {cfg.table_name} ({col_sql})
            VALUES ({placeholder_sql})
            RETURNING {cfg.id_column};
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()[cfg.id_column]
                conn.commit()
                logger.info("%s inserted: id=%s code=%s", cfg.table_name, new_id, data.get("code"))
                return new_id

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update(self, record_id: int, data: dict[str, Any]) -> bool:
        """
        Updates an existing, non-deleted row. `data` must contain
        code/name/status/remarks plus updated_by/updated_at_ad/
        updated_at_bs, and -- if scoped -- the scope column.
        """
        cfg = self.config
        set_parts = [
            "code = %(code)s",
            "name = %(name)s",
            "status = %(status)s",
            "remarks = %(remarks)s",
            "updated_by = %(updated_by)s",
            "updated_at_ad = %(updated_at_ad)s",
            "updated_at_bs = %(updated_at_bs)s",
        ]
        if cfg.scope_column:
            set_parts.append(f"{cfg.scope_column} = %({cfg.scope_column})s")

        params = dict(data)
        params["record_id"] = record_id

        sql = f"""
            UPDATE {cfg.table_name}
            SET {", ".join(set_parts)}
            WHERE {cfg.id_column} = %(record_id)s
              AND is_deleted = FALSE;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                if updated:
                    logger.info("%s updated: id=%s", cfg.table_name, record_id)
                return updated

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, record_id: int, include_deleted: bool = False) -> Optional[dict]:
        cfg = self.config
        sql = f"SELECT * FROM {cfg.table_name} WHERE {cfg.id_column} = %(record_id)s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"record_id": record_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_by_name(self, name: str, exclude_id: Optional[int] = None, scope_id: Optional[int] = None) -> bool:
        """Case-insensitive duplicate check among non-deleted rows. Scoped
        tables (Sub Category) additionally restrict the check to the given
        scope_id -- the same name is fine under a different parent."""
        cfg = self.config
        sql = f"SELECT 1 FROM {cfg.table_name} WHERE LOWER(name) = LOWER(%(name)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"name": name}
        if cfg.scope_column:
            sql += f" AND {cfg.scope_column} = %(scope_id)s"
            params["scope_id"] = scope_id
        if exclude_id is not None:
            sql += f" AND {cfg.id_column} != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def exists_by_code(self, code: str, exclude_id: Optional[int] = None, scope_id: Optional[int] = None) -> bool:
        cfg = self.config
        sql = f"SELECT 1 FROM {cfg.table_name} WHERE LOWER(code) = LOWER(%(code)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"code": code}
        if cfg.scope_column:
            sql += f" AND {cfg.scope_column} = %(scope_id)s"
            params["scope_id"] = scope_id
        if exclude_id is not None:
            sql += f" AND {cfg.id_column} != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def get_last_code_sequence(self, prefix: str) -> int:
        """Highest numeric suffix among codes (any status, non-deleted or
        deleted) starting with `prefix` -- codes are never reused, same
        rule as ItemModel.get_last_code_sequence()."""
        cfg = self.config
        sql = f"""
            SELECT COALESCE(MAX(
                CAST(REGEXP_REPLACE(code, %(prefix_pattern)s, '') AS INTEGER)
            ), 0) AS max_seq
            FROM {cfg.table_name}
            WHERE code ~ %(pattern)s;
        """
        params = {"prefix_pattern": f"^{prefix}", "pattern": f"^{prefix}[0-9]+$"}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()["max_seq"]

    def search(self, search_text: Optional[str] = None, include_deleted: bool = False) -> list[dict]:
        """
        Returns ALL matching rows, ordered by name. No server-side paging --
        these lookup lists (even the long ones like Manufacturer/Generic)
        stay in the low thousands at most, which is trivial for a single
        query; the Screen's own search box narrows what's visible.
        """
        cfg = self.config
        where = ["1=1"]
        params: dict[str, Any] = {}

        if not include_deleted:
            where.append("is_deleted = FALSE")

        if search_text:
            where.append("(code ILIKE %(search)s OR name ILIKE %(search)s)")
            params["search"] = f"%{search_text}%"

        where_clause = " AND ".join(where)
        sql = f"""
            SELECT * FROM {cfg.table_name}
            WHERE {where_clause}
            ORDER BY name ASC;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def list_active(self) -> list[dict]:
        """Convenience for populating dropdowns -- active, non-deleted rows only."""
        cfg = self.config
        sql = f"""
            SELECT * FROM {cfg.table_name}
            WHERE is_deleted = FALSE AND status = 'Active'
            ORDER BY name ASC;
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def soft_delete(self, record_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: Optional[str]) -> bool:
        cfg = self.config
        sql = f"""
            UPDATE {cfg.table_name}
            SET is_deleted = TRUE,
                deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s,
                deleted_at_bs = %(deleted_at_bs)s
            WHERE {cfg.id_column} = %(record_id)s
              AND is_deleted = FALSE;
        """
        params = {
            "record_id": record_id,
            "deleted_by": deleted_by,
            "deleted_at_ad": deleted_at_ad,
            "deleted_at_bs": deleted_at_bs,
        }
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                if ok:
                    logger.info("%s soft-deleted: id=%s by=%s", cfg.table_name, record_id, deleted_by)
                return ok

    def restore(self, record_id: int, updated_by: int, updated_at_ad, updated_at_bs: Optional[str]) -> bool:
        cfg = self.config
        sql = f"""
            UPDATE {cfg.table_name}
            SET is_deleted = FALSE,
                deleted_by = NULL,
                deleted_at_ad = NULL,
                deleted_at_bs = NULL,
                updated_by = %(updated_by)s,
                updated_at_ad = %(updated_at_ad)s,
                updated_at_bs = %(updated_at_bs)s
            WHERE {cfg.id_column} = %(record_id)s
              AND is_deleted = TRUE;
        """
        params = {
            "record_id": record_id,
            "updated_by": updated_by,
            "updated_at_ad": updated_at_ad,
            "updated_at_bs": updated_at_bs,
        }
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                if ok:
                    logger.info("%s restored: id=%s by=%s", cfg.table_name, record_id, updated_by)
                return ok


__all__ = ["MasterTableConfig", "SimpleMasterModel"]
