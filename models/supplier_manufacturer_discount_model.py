"""
models/supplier_manufacturer_discount_model.py

Supplier-Manufacturer Discount Model - Medical ERP V2

Project rule: "No SQL outside the Model." Every statement that touches the
`supplier_manufacturer_discount` table lives in this file and nowhere else.
This class has NO business rules, NO validation, and NO decisions -- it
only executes SQL and returns data. All business logic belongs in
engines/supplier_manufacturer_discount_engine.py.

Mirrors models/manufacturer_model.py's shape, plus LEFT JOINs to `supplier`
and `manufacturer` so the List screen can display supplier_name /
manufacturer_name without a second round trip per row -- the same reasoning
already used by models/item_model.py's search() (a correlated subquery for
total_stock is pure aggregation, not a business decision; a join for
display names here is the same kind of read-only convenience).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    """Lazy import wrapper -- see models/supplier_model.py for why this
    pattern is used throughout the project."""
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class SupplierManufacturerDiscountSearchFilters:
    """Filter parameters for search/listing."""
    search_text: Optional[str] = None      # matches supplier_name, manufacturer_name, remarks
    supplier_id: Optional[int] = None
    manufacturer_id: Optional[int] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


# Shared SELECT list so every read method (get_by_id/search) returns the
# exact same shape, including the joined display names the Screen needs.
_SELECT_WITH_JOINS = """
    SELECT
        d.*,
        s.supplier_name AS supplier_name,
        m.manufacturer_name AS manufacturer_name
    FROM supplier_manufacturer_discount d
    LEFT JOIN supplier s ON s.supplier_id = d.supplier_id
    LEFT JOIN manufacturer m ON m.manufacturer_id = d.manufacturer_id
"""


class SupplierManufacturerDiscountModel:
    """Data-access layer for `supplier_manufacturer_discount`. SQL only, no business logic."""

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def insert(self, data: dict[str, Any]) -> int:
        """
        Insert a new mapping row. `data` must already contain every column
        this INSERT expects (the Engine is responsible for defaults,
        created_by/created_at_ad/created_at_bs). Returns the new id.
        """
        sql = """
            INSERT INTO supplier_manufacturer_discount (
                supplier_id, manufacturer_id, discount_percent, remarks,
                created_by, created_at_ad, created_at_bs
            ) VALUES (
                %(supplier_id)s, %(manufacturer_id)s, %(discount_percent)s, %(remarks)s,
                %(created_by)s, %(created_at_ad)s, %(created_at_bs)s
            )
            RETURNING id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()["id"]
                conn.commit()
                logger.info(
                    "Supplier-Manufacturer Discount inserted: id=%s supplier_id=%s manufacturer_id=%s",
                    new_id, data.get("supplier_id"), data.get("manufacturer_id"),
                )
                return new_id

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update(self, record_id: int, data: dict[str, Any]) -> bool:
        """
        Update an existing, non-deleted row. `data` must contain
        updated_by/updated_at_ad/updated_at_bs plus every editable field
        (supplier_id, manufacturer_id, discount_percent, remarks).
        Returns True if a row was updated.
        """
        sql = """
            UPDATE supplier_manufacturer_discount
            SET supplier_id       = %(supplier_id)s,
                manufacturer_id   = %(manufacturer_id)s,
                discount_percent  = %(discount_percent)s,
                remarks           = %(remarks)s,
                updated_by        = %(updated_by)s,
                updated_at_ad     = %(updated_at_ad)s,
                updated_at_bs     = %(updated_at_bs)s
            WHERE id = %(record_id)s
              AND is_deleted = FALSE;
        """
        params = dict(data)
        params["record_id"] = record_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                if updated:
                    logger.info("Supplier-Manufacturer Discount updated: id=%s", record_id)
                return updated

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, record_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = _SELECT_WITH_JOINS + " WHERE d.id = %(record_id)s"
        if not include_deleted:
            sql += " AND d.is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"record_id": record_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_pair(
        self, supplier_id: int, manufacturer_id: int, include_deleted: bool = False
    ) -> Optional[dict]:
        sql = _SELECT_WITH_JOINS + " WHERE d.supplier_id = %(supplier_id)s AND d.manufacturer_id = %(manufacturer_id)s"
        if not include_deleted:
            sql += " AND d.is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"supplier_id": supplier_id, "manufacturer_id": manufacturer_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_by_pair(
        self, supplier_id: int, manufacturer_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        sql = (
            "SELECT 1 FROM supplier_manufacturer_discount "
            "WHERE supplier_id = %(supplier_id)s AND manufacturer_id = %(manufacturer_id)s "
            "AND is_deleted = FALSE"
        )
        params: dict[str, Any] = {"supplier_id": supplier_id, "manufacturer_id": manufacturer_id}
        if exclude_id is not None:
            sql += " AND id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def search(self, filters: SupplierManufacturerDiscountSearchFilters) -> tuple[list[dict], int]:
        """Returns (rows, total_count) honoring search text, supplier/manufacturer filters, and paging."""
        where = ["1=1"]
        params: dict[str, Any] = {}

        if not filters.include_deleted:
            where.append("d.is_deleted = FALSE")

        if filters.supplier_id:
            where.append("d.supplier_id = %(supplier_id)s")
            params["supplier_id"] = filters.supplier_id

        if filters.manufacturer_id:
            where.append("d.manufacturer_id = %(manufacturer_id)s")
            params["manufacturer_id"] = filters.manufacturer_id

        if filters.search_text:
            where.append("""(
                s.supplier_name ILIKE %(search)s OR
                m.manufacturer_name ILIKE %(search)s OR
                d.remarks ILIKE %(search)s
            )""")
            params["search"] = f"%{filters.search_text}%"

        where_clause = " AND ".join(where)
        offset = max(filters.page - 1, 0) * filters.page_size

        count_sql = f"""
            SELECT COUNT(*)
            FROM supplier_manufacturer_discount d
            LEFT JOIN supplier s ON s.supplier_id = d.supplier_id
            LEFT JOIN manufacturer m ON m.manufacturer_id = d.manufacturer_id
            WHERE {where_clause};
        """
        data_sql = f"""
            {_SELECT_WITH_JOINS}
            WHERE {where_clause}
            ORDER BY s.supplier_name ASC, m.manufacturer_name ASC
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
    def soft_delete(self, record_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> bool:
        sql = """
            UPDATE supplier_manufacturer_discount
            SET is_deleted = TRUE,
                deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s,
                deleted_at_bs = %(deleted_at_bs)s
            WHERE id = %(record_id)s
              AND is_deleted = FALSE;
        """
        params = {
            "record_id": record_id,
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
                    logger.info("Supplier-Manufacturer Discount soft-deleted: id=%s by=%s", record_id, deleted_by)
                return ok

    def restore(self, record_id: int, updated_by: int, updated_at_ad, updated_at_bs: str) -> bool:
        sql = """
            UPDATE supplier_manufacturer_discount
            SET is_deleted = FALSE,
                deleted_by = NULL,
                deleted_at_ad = NULL,
                deleted_at_bs = NULL,
                updated_by = %(updated_by)s,
                updated_at_ad = %(updated_at_ad)s,
                updated_at_bs = %(updated_at_bs)s
            WHERE id = %(record_id)s
              AND is_deleted = TRUE;
        """
        params = {
            "record_id": record_id,
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
                    logger.info("Supplier-Manufacturer Discount restored: id=%s by=%s", record_id, updated_by)
                return ok


__all__ = ["SupplierManufacturerDiscountModel", "SupplierManufacturerDiscountSearchFilters"]