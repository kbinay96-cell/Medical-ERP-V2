"""
models/manufacturer_model.py

Manufacturer Model - Medical ERP V2

Project rule: "No SQL outside the Model." Every statement that touches the
`manufacturer` table lives in this file and nowhere else. This class has NO
business rules, NO validation, and NO decisions -- it only executes SQL and
returns data. All business logic belongs in engines/manufacturer_engine.py.

Integration contract (matches models/supplier_model.py exactly):
    from database.db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# NOTE: psycopg2 and database.db.get_connection are imported LAZILY inside
# each method (rather than at module scope), matching models/supplier_model.py,
# so `import models.manufacturer_model` stays safe for unit-testing the
# Engine/Validator layers without a live database.


def _get_connection():
    """Lazy import wrapper -- see module docstring for why."""
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    """Lazy import wrapper -- see module docstring for why."""
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class ManufacturerSearchFilters:
    """Filter parameters for manufacturer search/listing."""
    search_text: Optional[str] = None      # matches code, name, short name, country
    status: Optional[str] = None           # 'Active' | 'Inactive' | None (=both)
    country: Optional[str] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


class ManufacturerModel:
    """Data-access layer for the `manufacturer` table. SQL only, no business logic."""

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def insert(self, data: dict[str, Any]) -> int:
        """
        Insert a new manufacturer row. `data` must already contain every
        column this INSERT expects (the Engine is responsible for defaults,
        generated manufacturer_code, generated manufacturer_short_name,
        created_by/created_at_ad/created_at_bs). Returns the new
        manufacturer_id.
        """
        sql = """
            INSERT INTO manufacturer (
                manufacturer_code, manufacturer_name, manufacturer_short_name,
                country, status,
                created_by, created_at_ad, created_at_bs
            ) VALUES (
                %(manufacturer_code)s, %(manufacturer_name)s, %(manufacturer_short_name)s,
                %(country)s, %(status)s,
                %(created_by)s, %(created_at_ad)s, %(created_at_bs)s
            )
            RETURNING manufacturer_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()["manufacturer_id"]
                conn.commit()
                logger.info("Manufacturer inserted: id=%s code=%s", new_id, data.get("manufacturer_code"))
                return new_id

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update(self, manufacturer_id: int, data: dict[str, Any]) -> bool:
        """
        Update an existing, non-deleted manufacturer. `data` must contain
        updated_by/updated_at_ad/updated_at_bs plus every editable field
        (manufacturer_name, manufacturer_short_name, country, status).
        manufacturer_code is immutable after creation, same as Supplier.
        Returns True if a row was updated.
        """
        sql = """
            UPDATE manufacturer
            SET manufacturer_name       = %(manufacturer_name)s,
                manufacturer_short_name = %(manufacturer_short_name)s,
                country                 = %(country)s,
                status                  = %(status)s,
                updated_by              = %(updated_by)s,
                updated_at_ad           = %(updated_at_ad)s,
                updated_at_bs           = %(updated_at_bs)s
            WHERE manufacturer_id = %(manufacturer_id)s
              AND is_deleted = FALSE;
        """
        params = dict(data)
        params["manufacturer_id"] = manufacturer_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                if updated:
                    logger.info("Manufacturer updated: id=%s", manufacturer_id)
                return updated

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, manufacturer_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM manufacturer WHERE manufacturer_id = %(manufacturer_id)s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"manufacturer_id": manufacturer_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_name(self, manufacturer_name: str, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM manufacturer WHERE LOWER(manufacturer_name) = LOWER(%(name)s)"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"name": manufacturer_name})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_code(self, manufacturer_code: str, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM manufacturer WHERE LOWER(manufacturer_code) = LOWER(%(code)s)"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"code": manufacturer_code})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_by_name(self, manufacturer_name: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM manufacturer WHERE LOWER(manufacturer_name) = LOWER(%(name)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"name": manufacturer_name}
        if exclude_id is not None:
            sql += " AND manufacturer_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def exists_by_code(self, manufacturer_code: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM manufacturer WHERE LOWER(manufacturer_code) = LOWER(%(code)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"code": manufacturer_code}
        if exclude_id is not None:
            sql += " AND manufacturer_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def exists_by_short_name(self, short_name: str, exclude_id: Optional[int] = None) -> bool:
        """Used by the Engine to resolve Sun / Sun1 / Sun2 collisions."""
        sql = (
            "SELECT 1 FROM manufacturer "
            "WHERE LOWER(manufacturer_short_name) = LOWER(%(short_name)s) AND is_deleted = FALSE"
        )
        params: dict[str, Any] = {"short_name": short_name}
        if exclude_id is not None:
            sql += " AND manufacturer_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def get_last_code_sequence(self, prefix: str) -> int:
        """
        Returns the highest numeric suffix currently used among ACTIVE-or-
        DELETED manufacturer codes starting with `prefix` (codes are never
        reused across the table's full history). Returns 0 if none exist.
        """
        sql = """
            SELECT COALESCE(MAX(
                CAST(REGEXP_REPLACE(manufacturer_code, %(prefix_pattern)s, '') AS INTEGER)
            ), 0) AS max_seq
            FROM manufacturer
            WHERE manufacturer_code ~ %(pattern)s;
        """
        params = {
            "prefix_pattern": f"^{prefix}",
            "pattern": f"^{prefix}[0-9]+$",
        }
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()["max_seq"]

    def search(self, filters: ManufacturerSearchFilters) -> tuple[list[dict], int]:
        """Returns (rows, total_count) honoring search text, status/country filters and paging."""
        where = ["1=1"]
        params: dict[str, Any] = {}

        if not filters.include_deleted:
            where.append("is_deleted = FALSE")

        if filters.status:
            where.append("status = %(status)s")
            params["status"] = filters.status

        if filters.country:
            where.append("country = %(country)s")
            params["country"] = filters.country

        if filters.search_text:
            where.append("""(
                manufacturer_code ILIKE %(search)s OR
                manufacturer_name ILIKE %(search)s OR
                manufacturer_short_name ILIKE %(search)s OR
                country ILIKE %(search)s
            )""")
            params["search"] = f"%{filters.search_text}%"

        where_clause = " AND ".join(where)
        offset = max(filters.page - 1, 0) * filters.page_size

        count_sql = f"SELECT COUNT(*) FROM manufacturer WHERE {where_clause};"
        data_sql = f"""
            SELECT * FROM manufacturer
            WHERE {where_clause}
            ORDER BY manufacturer_name ASC
            LIMIT %(limit)s OFFSET %(offset)s;
        """

        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(count_sql, params)
                row = cur.fetchone()
                total_count = row["count"] if row else 0

            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                data_params = dict(params)
                data_params["limit"] = filters.page_size
                data_params["offset"] = offset
                cur.execute(data_sql, data_params)
                rows = [dict(r) for r in cur.fetchall()]

        return rows, total_count

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def soft_delete(self, manufacturer_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> bool:
        sql = """
            UPDATE manufacturer
            SET is_deleted = TRUE,
                deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s,
                deleted_at_bs = %(deleted_at_bs)s
            WHERE manufacturer_id = %(manufacturer_id)s
              AND is_deleted = FALSE;
        """
        params = {
            "manufacturer_id": manufacturer_id,
            "deleted_by": deleted_by,
            "deleted_at_ad": deleted_at_ad,
            "deleted_at_bs": deleted_at_bs,
        }
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                if ok:
                    logger.info("Manufacturer soft-deleted: id=%s by=%s", manufacturer_id, deleted_by)
                return ok

    def restore(self, manufacturer_id: int, updated_by: int, updated_at_ad, updated_at_bs: str) -> bool:
        sql = """
            UPDATE manufacturer
            SET is_deleted = FALSE,
                deleted_by = NULL,
                deleted_at_ad = NULL,
                deleted_at_bs = NULL,
                updated_by = %(updated_by)s,
                updated_at_ad = %(updated_at_ad)s,
                updated_at_bs = %(updated_at_bs)s
            WHERE manufacturer_id = %(manufacturer_id)s
              AND is_deleted = TRUE;
        """
        params = {
            "manufacturer_id": manufacturer_id,
            "updated_by": updated_by,
            "updated_at_ad": updated_at_ad,
            "updated_at_bs": updated_at_bs,
        }
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                if ok:
                    logger.info("Manufacturer restored: id=%s by=%s", manufacturer_id, updated_by)
                return ok
