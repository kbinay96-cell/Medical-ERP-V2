"""
models/supplier_model.py

Supplier Model - Medical ERP V2

Project rule: "No SQL outside the Model." Every statement that touches the
`supplier` table lives in this file and nowhere else. This class has NO
business rules, NO validation, and NO decisions -- it only executes SQL and
returns data. All business logic belongs in engines/supplier_engine.py.

Integration contract with the existing project (as previously established
for the Login/Dashboard module):
    - database/db.py exposes `get_connection()`, a context manager that
      yields a psycopg2 connection (autocommit=False) from the shared
      connection pool, e.g.:

          from database.db import get_connection
          with _get_connection() as conn:
              with conn.cursor() as cur:
                  cur.execute(...)

      If your actual db.py exposes a differently-named helper, update the
      single import line below (`from database.db import get_connection`)
      -- nothing else in this module needs to change, since all access goes
      through that one function.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# NOTE: psycopg2 and database.db.get_connection are imported LAZILY inside
# each method (rather than at module scope) on purpose. This keeps
# `import models.supplier_model` safe to do in unit tests for the Engine/
# Validator layers on a machine that does not have psycopg2 installed or a
# database/db.py present yet (e.g. this sandbox). In the real project, where
# both are always available, this has no behavioural difference -- Python
# caches the import after the first call.


def _get_connection():
    """Lazy import wrapper -- see module docstring for why."""
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    """Lazy import wrapper -- see module docstring for why."""
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class SupplierSearchFilters:
    """Filter parameters for supplier search/listing."""
    search_text: Optional[str] = None      # matches code, name, mobile, PAN/VAT
    status: Optional[str] = None           # 'Active' | 'Inactive' | None (=both)
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


class SupplierModel:
    """Data-access layer for the `supplier` table. SQL only, no business logic."""

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def insert(self, data: dict[str, Any]) -> int:
        """
        Insert a new supplier row. `data` must already contain every column
        this INSERT expects (the Engine is responsible for defaults,
        generated supplier_code, created_by/created_at_ad/created_at_bs).
        Returns the new supplier_id.
        """
        sql = """
            INSERT INTO supplier (
                supplier_code, supplier_name, contact_person, mobile_no,
                phone_no, email, address, city, pan_vat_no,
                opening_balance, balance_type, credit_limit, credit_days,
                status, remarks, company_id, photo_path,
                created_by, created_at_ad, created_at_bs
            ) VALUES (
                %(supplier_code)s, %(supplier_name)s, %(contact_person)s, %(mobile_no)s,
                %(phone_no)s, %(email)s, %(address)s, %(city)s, %(pan_vat_no)s,
                %(opening_balance)s, %(balance_type)s, %(credit_limit)s, %(credit_days)s,
                %(status)s, %(remarks)s, %(company_id)s, %(photo_path)s,
                %(created_by)s, %(created_at_ad)s, %(created_at_bs)s
            )
            RETURNING supplier_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()["supplier_id"]
                conn.commit()
                logger.info("Supplier inserted: id=%s code=%s", new_id, data.get("supplier_code"))
                return new_id

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update(self, supplier_id: int, data: dict[str, Any]) -> bool:
        """
        Update an existing, non-deleted supplier. `data` must contain
        updated_by/updated_at_ad/updated_at_bs plus every editable field.
        Returns True if a row was updated.
        """
        sql = """
            UPDATE supplier
            SET supplier_name   = %(supplier_name)s,
                contact_person  = %(contact_person)s,
                mobile_no       = %(mobile_no)s,
                phone_no        = %(phone_no)s,
                email           = %(email)s,
                address         = %(address)s,
                city            = %(city)s,
                pan_vat_no      = %(pan_vat_no)s,
                opening_balance = %(opening_balance)s,
                balance_type    = %(balance_type)s,
                credit_limit    = %(credit_limit)s,
                credit_days     = %(credit_days)s,
                status          = %(status)s,
                remarks         = %(remarks)s,
                company_id      = %(company_id)s,
                photo_path      = %(photo_path)s,
                updated_by      = %(updated_by)s,
                updated_at_ad   = %(updated_at_ad)s,
                updated_at_bs   = %(updated_at_bs)s
            WHERE supplier_id = %(supplier_id)s
              AND is_deleted = FALSE;
        """
        params = dict(data)
        params["supplier_id"] = supplier_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                if updated:
                    logger.info("Supplier updated: id=%s", supplier_id)
                return updated

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, supplier_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM supplier WHERE supplier_id = %(supplier_id)s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"supplier_id": supplier_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_name(self, supplier_name: str, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM supplier WHERE LOWER(supplier_name) = LOWER(%(name)s)"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"name": supplier_name})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_code(self, supplier_code: str, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM supplier WHERE LOWER(supplier_code) = LOWER(%(code)s)"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"code": supplier_code})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_by_name(self, supplier_name: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM supplier WHERE LOWER(supplier_name) = LOWER(%(name)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"name": supplier_name}
        if exclude_id is not None:
            sql += " AND supplier_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def exists_by_code(self, supplier_code: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM supplier WHERE LOWER(supplier_code) = LOWER(%(code)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"code": supplier_code}
        if exclude_id is not None:
            sql += " AND supplier_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def get_last_code_sequence(self, prefix: str) -> int:
        """
        Returns the highest numeric suffix currently used among ACTIVE-or-
        DELETED supplier codes starting with `prefix` (codes are never
        reused across the table's full history, even after a soft delete,
        so the sequence never collides). Returns 0 if none exist.
        """
        sql = """
            SELECT COALESCE(MAX(
                CAST(REGEXP_REPLACE(supplier_code, %(prefix_pattern)s, '') AS INTEGER)
            ), 0) AS max_seq
            FROM supplier
            WHERE supplier_code ~ %(pattern)s;
        """
        params = {
            "prefix_pattern": f"^{prefix}",
            "pattern": f"^{prefix}[0-9]+$",
        }
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()["max_seq"]

    def search(self, filters: SupplierSearchFilters) -> tuple[list[dict], int]:
        """Returns (rows, total_count) honoring search text, status filter and paging."""
        where = ["1=1"]
        params: dict[str, Any] = {}

        if not filters.include_deleted:
            where.append("is_deleted = FALSE")

        if filters.status:
            where.append("status = %(status)s")
            params["status"] = filters.status

        if filters.search_text:
            where.append("""(
                supplier_code ILIKE %(search)s OR
                supplier_name ILIKE %(search)s OR
                mobile_no ILIKE %(search)s OR
                pan_vat_no ILIKE %(search)s
            )""")
            params["search"] = f"%{filters.search_text}%"

        where_clause = " AND ".join(where)
        offset = max(filters.page - 1, 0) * filters.page_size

        count_sql = f"SELECT COUNT(*) FROM supplier WHERE {where_clause};"
        data_sql = f"""
            SELECT * FROM supplier
            WHERE {where_clause}
            ORDER BY supplier_name ASC
            LIMIT %(limit)s OFFSET %(offset)s;
        """

        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(count_sql, params)

                row = cur.fetchone()

                if row is None:
                    total_count = 0
                else:
                    total_count = row["count"]

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
    def soft_delete(self, supplier_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> bool:
        sql = """
            UPDATE supplier
            SET is_deleted = TRUE,
                deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s,
                deleted_at_bs = %(deleted_at_bs)s
            WHERE supplier_id = %(supplier_id)s
              AND is_deleted = FALSE;
        """
        params = {
            "supplier_id": supplier_id,
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
                    logger.info("Supplier soft-deleted: id=%s by=%s", supplier_id, deleted_by)
                return ok

    def restore(self, supplier_id: int, updated_by: int, updated_at_ad, updated_at_bs: str) -> bool:
        sql = """
            UPDATE supplier
            SET is_deleted = FALSE,
                deleted_by = NULL,
                deleted_at_ad = NULL,
                deleted_at_bs = NULL,
                updated_by = %(updated_by)s,
                updated_at_ad = %(updated_at_ad)s,
                updated_at_bs = %(updated_at_bs)s
            WHERE supplier_id = %(supplier_id)s
              AND is_deleted = TRUE;
        """
        params = {
            "supplier_id": supplier_id,
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
                    logger.info("Supplier restored: id=%s by=%s", supplier_id, updated_by)
                return ok
