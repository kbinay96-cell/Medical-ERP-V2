"""
models/country_tax_model.py

Country Tax Settings Model - Medical ERP V2

Project rule: "No SQL outside the Model." Every statement that touches the
`country_tax` table lives in this file and nowhere else. This class has NO
business rules, NO validation, and NO decisions -- it only executes SQL and
returns data. All business logic belongs in engines/country_tax_engine.py.

Mirrors models/manufacturer_model.py's shape exactly, minus the code /
short-name generation machinery -- Country Tax has no generated code, the
Country name itself is the unique business key.

Integration contract (matches models/manufacturer_model.py and
models/supplier_model.py exactly):
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
# each method (rather than at module scope), matching models/manufacturer_model.py,
# so `import models.country_tax_model` stays safe for unit-testing the
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
class CountryTaxSearchFilters:
    """Filter parameters for country tax search/listing."""
    search_text: Optional[str] = None      # matches country, remarks
    status: Optional[str] = None           # 'Active' | 'Inactive' | None (=both)
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


class CountryTaxModel:
    """Data-access layer for the `country_tax` table. SQL only, no business logic."""

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def insert(self, data: dict[str, Any]) -> int:
        """
        Insert a new country tax row. `data` must already contain every
        column this INSERT expects (the Engine is responsible for defaults,
        created_by/created_at_ad/created_at_bs). Returns the new
        country_tax_id.
        """
        sql = """
            INSERT INTO country_tax (
                country, vat_percent, custom_percent, remarks, status,
                created_by, created_at_ad, created_at_bs
            ) VALUES (
                %(country)s, %(vat_percent)s, %(custom_percent)s, %(remarks)s, %(status)s,
                %(created_by)s, %(created_at_ad)s, %(created_at_bs)s
            )
            RETURNING country_tax_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()["country_tax_id"]
                conn.commit()
                logger.info("Country Tax inserted: id=%s country=%s", new_id, data.get("country"))
                return new_id

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update(self, country_tax_id: int, data: dict[str, Any]) -> bool:
        """
        Update an existing, non-deleted row. `data` must contain
        updated_by/updated_at_ad/updated_at_bs plus every editable field
        (country, vat_percent, custom_percent, remarks, status).
        Returns True if a row was updated.
        """
        sql = """
            UPDATE country_tax
            SET country          = %(country)s,
                vat_percent      = %(vat_percent)s,
                custom_percent   = %(custom_percent)s,
                remarks          = %(remarks)s,
                status           = %(status)s,
                updated_by       = %(updated_by)s,
                updated_at_ad    = %(updated_at_ad)s,
                updated_at_bs    = %(updated_at_bs)s
            WHERE country_tax_id = %(country_tax_id)s
              AND is_deleted = FALSE;
        """
        params = dict(data)
        params["country_tax_id"] = country_tax_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                if updated:
                    logger.info("Country Tax updated: id=%s", country_tax_id)
                return updated

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, country_tax_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM country_tax WHERE country_tax_id = %(country_tax_id)s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"country_tax_id": country_tax_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_country(self, country: str, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM country_tax WHERE LOWER(country) = LOWER(%(country)s)"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"country": country})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_by_country(self, country: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM country_tax WHERE LOWER(country) = LOWER(%(country)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"country": country}
        if exclude_id is not None:
            sql += " AND country_tax_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def search(self, filters: CountryTaxSearchFilters) -> tuple[list[dict], int]:
        """Returns (rows, total_count) honoring search text, status filter and paging."""
        where = ["1=1"]
        params: dict[str, Any] = {}

        if not filters.include_deleted:
            where.append("is_deleted = FALSE")

        if filters.status:
            where.append("status = %(status)s")
            params["status"] = filters.status

        if filters.search_text:
            where.append("(country ILIKE %(search)s OR remarks ILIKE %(search)s)")
            params["search"] = f"%{filters.search_text}%"

        where_clause = " AND ".join(where)
        offset = max(filters.page - 1, 0) * filters.page_size

        count_sql = f"SELECT COUNT(*) FROM country_tax WHERE {where_clause};"
        data_sql = f"""
            SELECT * FROM country_tax
            WHERE {where_clause}
            ORDER BY country ASC
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

    def list_active(self) -> list[dict]:
        """Convenience for lookups (e.g. Item Form's future country dropdown) --
        active, non-deleted rows only."""
        sql = """
            SELECT * FROM country_tax
            WHERE is_deleted = FALSE AND status = 'Active'
            ORDER BY country ASC;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql)
                return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def soft_delete(self, country_tax_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> bool:
        sql = """
            UPDATE country_tax
            SET is_deleted = TRUE,
                deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s,
                deleted_at_bs = %(deleted_at_bs)s
            WHERE country_tax_id = %(country_tax_id)s
              AND is_deleted = FALSE;
        """
        params = {
            "country_tax_id": country_tax_id,
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
                    logger.info("Country Tax soft-deleted: id=%s by=%s", country_tax_id, deleted_by)
                return ok

    def restore(self, country_tax_id: int, updated_by: int, updated_at_ad, updated_at_bs: str) -> bool:
        sql = """
            UPDATE country_tax
            SET is_deleted = FALSE,
                deleted_by = NULL,
                deleted_at_ad = NULL,
                deleted_at_bs = NULL,
                updated_by = %(updated_by)s,
                updated_at_ad = %(updated_at_ad)s,
                updated_at_bs = %(updated_at_bs)s
            WHERE country_tax_id = %(country_tax_id)s
              AND is_deleted = TRUE;
        """
        params = {
            "country_tax_id": country_tax_id,
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
                    logger.info("Country Tax restored: id=%s by=%s", country_tax_id, updated_by)
                return ok


__all__ = ["CountryTaxModel", "CountryTaxSearchFilters"]
