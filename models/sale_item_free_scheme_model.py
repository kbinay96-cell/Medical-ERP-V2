# models/sale_item_free_scheme_model.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class SaleItemFreeSchemeSearchFilters:
    search_text: Optional[str] = None
    item_id: Optional[int] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


class SaleItemFreeSchemeModel:
    """Data-access layer for `sale_item_free_scheme`. SQL only, no business logic.

    One active scheme per item. Mirrors the shape of
    models/supplier_manufacturer_discount_model.py (already in the repo).
    """

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def insert(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO sale_item_free_scheme
                (item_id, scheme_qty, scheme_free, is_active, remarks,
                 created_by, created_at_ad, created_at_bs)
            VALUES
                (%(item_id)s, %(scheme_qty)s, %(scheme_free)s, %(is_active)s, %(remarks)s,
                 %(created_by)s, %(created_at_ad)s, %(created_at_bs)s)
            RETURNING sale_item_free_scheme_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()[0]
                conn.commit()
                logger.info("Sale item free scheme inserted: id=%s item_id=%s %s+%s",
                            new_id, data.get("item_id"), data.get("scheme_qty"), data.get("scheme_free"))
                return new_id

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update(self, sale_item_free_scheme_id: int, data: dict[str, Any]) -> bool:
        sql = """
            UPDATE sale_item_free_scheme
               SET scheme_qty = %(scheme_qty)s,
                   scheme_free = %(scheme_free)s,
                   is_active = %(is_active)s,
                   remarks = %(remarks)s,
                   updated_by = %(updated_by)s,
                   updated_at_ad = %(updated_at_ad)s,
                   updated_at_bs = %(updated_at_bs)s
             WHERE sale_item_free_scheme_id = %(id)s
               AND is_deleted = FALSE;
        """
        params = dict(data)
        params["id"] = sale_item_free_scheme_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                return updated

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, sale_item_free_scheme_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM sale_item_free_scheme WHERE sale_item_free_scheme_id = %(id)s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": sale_item_free_scheme_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_active_by_item(self, item_id: int) -> Optional[dict]:
        """The ONE currently-active scheme for this item, or None if the
        item has no free scheme configured -- used live by SaleEngine
        every time an item is added to a Sale Invoice line."""
        sql = """
            SELECT * FROM sale_item_free_scheme
             WHERE item_id = %(item_id)s
               AND is_deleted = FALSE
               AND is_active = TRUE
             LIMIT 1;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_id": item_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_active_for_item(self, item_id: int, exclude_id: Optional[int] = None) -> bool:
        sql = """
            SELECT 1 FROM sale_item_free_scheme
             WHERE item_id = %(item_id)s
               AND is_deleted = FALSE
               AND is_active = TRUE
        """
        params: dict[str, Any] = {"item_id": item_id}
        if exclude_id is not None:
            sql += " AND sale_item_free_scheme_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def search(self, filters: SaleItemFreeSchemeSearchFilters) -> tuple[list[dict], int]:
        """Joined with item for display -- item name/code."""
        where = ["1=1"]
        params: dict[str, Any] = {}

        if not filters.include_deleted:
            where.append("fs.is_deleted = FALSE")
        if filters.item_id:
            where.append("fs.item_id = %(item_id)s")
            params["item_id"] = filters.item_id
        if filters.search_text:
            where.append("i.item_name ILIKE %(search)s")
            params["search"] = f"%{filters.search_text}%"

        where_sql = " AND ".join(where)

        count_sql = (
            "SELECT COUNT(*) AS total FROM sale_item_free_scheme fs "
            "JOIN item i ON fs.item_id = i.item_id "
            f"WHERE {where_sql}"
        )

        query_sql = (
            "SELECT fs.*, i.item_name, i.item_code "
            "FROM sale_item_free_scheme fs "
            "JOIN item i ON fs.item_id = i.item_id "
            f"WHERE {where_sql} "
            "ORDER BY i.item_name ASC "
            "LIMIT %(limit)s OFFSET %(offset)s"
        )

        limit = filters.page_size or 50
        offset = (max(1, filters.page) - 1) * limit
        params["limit"] = limit
        params["offset"] = offset

        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(count_sql, {k: v for k, v in params.items() if k not in ("limit", "offset")})
                total = int(cur.fetchone()["total"] or 0)
                cur.execute(query_sql, params)
                rows = [dict(r) for r in cur.fetchall()]
                return rows, total

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def soft_delete(self, sale_item_free_scheme_id: int, deleted_by: int,
                    deleted_at_ad, deleted_at_bs: str) -> bool:
        sql = """
            UPDATE sale_item_free_scheme
               SET is_deleted = TRUE,
                   is_active = FALSE,
                   deleted_by = %(deleted_by)s,
                   deleted_at_ad = %(deleted_at_ad)s,
                   deleted_at_bs = %(deleted_at_bs)s
             WHERE sale_item_free_scheme_id = %(id)s
               AND is_deleted = FALSE;
        """
        params = {
            "id": sale_item_free_scheme_id,
            "deleted_by": deleted_by,
            "deleted_at_ad": deleted_at_ad,
            "deleted_at_bs": deleted_at_bs,
        }
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                return ok

    def restore(self, sale_item_free_scheme_id: int, updated_by: int,
                updated_at_ad, updated_at_bs: str) -> bool:
        sql = """
            UPDATE sale_item_free_scheme
               SET is_deleted = FALSE,
                   is_active = TRUE,
                   deleted_by = NULL,
                   deleted_at_ad = NULL,
                   deleted_at_bs = NULL,
                   updated_by = %(updated_by)s,
                   updated_at_ad = %(updated_at_ad)s,
                   updated_at_bs = %(updated_at_bs)s
             WHERE sale_item_free_scheme_id = %(id)s
               AND is_deleted = TRUE;
        """
        params = {
            "id": sale_item_free_scheme_id,
            "updated_by": updated_by,
            "updated_at_ad": updated_at_ad,
            "updated_at_bs": updated_at_bs,
        }
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                return ok


__all__ = ["SaleItemFreeSchemeModel", "SaleItemFreeSchemeSearchFilters"]


