"""
models/item_model.py

Item Model - Medical ERP V2

Project rule: "No SQL outside the Model." Every statement touching `item`
or `item_batch` lives here and nowhere else. This class has NO business
rules, NO validation, NO decisions -- it only executes SQL and returns
data. All business logic belongs in engines/item_engine.py.

Stock is BATCH-LEVEL (confirmed decision) -- `item` itself carries no
quantity column. Total stock for an item is always the sum of its
item_batch rows' batch_qty. Zero-batch items (0 total stock) are a
perfectly valid, expected state (an item created before its first
Purchase/Opening Stock entry).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    """Lazy import -- see models/supplier_model.py for why this pattern is
    used throughout the project (keeps unit tests importable without a
    live database/db.py)."""
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class ItemSearchFilters:
    """Filter parameters for item search/listing."""
    search_text: Optional[str] = None       # matches item_code, item_name
    category_id: Optional[int] = None
    manufacturer_id: Optional[int] = None
    item_group_id: Optional[int] = None
    status: Optional[str] = None            # 'Active' | 'Inactive' | None (=both)
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


ITEM_COLUMNS = (
    "item_code", "item_name",
    "category_id", "sub_category_id", "item_group_id", "manufacturer_id", "generic_id",
    "unit_id", "purchase_unit_id",
    "purchase_rate", "sale_rate", "mrp",
    "minimum_stock",
    "tax_mode", "item_vat_checked", "item_vat_percent", "item_custom_checked", "item_custom_percent",
    "status", "remarks", "photo_path",
    "super_discount_percent",
)


class ItemModel:
    """Data-access layer for the `item` table. SQL only, no business logic."""

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def insert(self, data: dict[str, Any]) -> int:
        """
        `data` must contain every column in ITEM_COLUMNS plus
        created_by/created_at_ad/created_at_bs. Returns the new item_id.
        """
        columns = list(ITEM_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        col_sql = ", ".join(columns)
        placeholder_sql = ", ".join(f"%({c})s" for c in columns)

        sql = f"""
            INSERT INTO item ({col_sql})
            VALUES ({placeholder_sql})
            RETURNING item_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()["item_id"]
                conn.commit()
                logger.info("Item inserted: id=%s code=%s", new_id, data.get("item_code"))
                return new_id

    def update_mrp(self, item_id: int, mrp: float) -> bool:
        """Lightweight, single-column MRP update -- used by Purchase Invoice
        to remember the last-entered MRP per item without touching any
        other Item Master field or running full update() validation."""
        sql = """
            UPDATE item
            SET mrp = %(mrp)s
            WHERE item_id = %(item_id)s
              AND is_deleted = FALSE;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"mrp": mrp, "item_id": item_id})
                updated = cur.rowcount > 0
                conn.commit()
                return updated

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update(self, item_id: int, data: dict[str, Any]) -> bool:
        """
        Updates an existing, non-deleted item. `data` must contain every
        column in ITEM_COLUMNS plus updated_by/updated_at_ad/updated_at_bs.
        """
        set_parts = [f"{c} = %({c})s" for c in ITEM_COLUMNS]
        set_parts += ["updated_by = %(updated_by)s", "updated_at_ad = %(updated_at_ad)s", "updated_at_bs = %(updated_at_bs)s"]

        params = dict(data)
        params["item_id"] = item_id

        sql = f"""
            UPDATE item
            SET {", ".join(set_parts)}
            WHERE item_id = %(item_id)s
              AND is_deleted = FALSE;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                if updated:
                    logger.info("Item updated: id=%s", item_id)
                return updated

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, item_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM item WHERE item_id = %(item_id)s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_id": item_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_by_name(self, item_name: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM item WHERE LOWER(item_name) = LOWER(%(name)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"name": item_name}
        if exclude_id is not None:
            sql += " AND item_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def exists_by_code(self, item_code: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM item WHERE LOWER(item_code) = LOWER(%(code)s) AND is_deleted = FALSE"
        params: dict[str, Any] = {"code": item_code}
        if exclude_id is not None:
            sql += " AND item_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def get_last_code_sequence(self, prefix: str) -> int:
        """Highest numeric suffix among ACTIVE-or-DELETED item codes starting
        with `prefix` (codes are never reused, even after soft delete)."""
        sql = """
            SELECT COALESCE(MAX(
                CAST(REGEXP_REPLACE(item_code, %(prefix_pattern)s, '') AS INTEGER)
            ), 0) AS max_seq
            FROM item
            WHERE item_code ~ %(pattern)s;
        """
        params = {"prefix_pattern": f"^{prefix}", "pattern": f"^{prefix}[0-9]+$"}
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchone()["max_seq"]

    def search(self, filters: ItemSearchFilters) -> tuple[list[dict], int]:
        """
        Returns (rows, total_count). Each row is enriched with
        total_stock (SUM of its item_batch.batch_qty, 0 if no batches)
        via a correlated subquery -- computed here since it is pure
        aggregation, not a business decision.
        """
        where = ["1=1"]
        params: dict[str, Any] = {}

        if not filters.include_deleted:
            where.append("i.is_deleted = FALSE")
        if filters.status:
            where.append("i.status = %(status)s")
            params["status"] = filters.status
        if filters.category_id:
            where.append("i.category_id = %(category_id)s")
            params["category_id"] = filters.category_id
        if filters.manufacturer_id:
            where.append("i.manufacturer_id = %(manufacturer_id)s")
            params["manufacturer_id"] = filters.manufacturer_id
        if filters.item_group_id:
            where.append("i.item_group_id = %(item_group_id)s")
            params["item_group_id"] = filters.item_group_id
        if filters.search_text:
            where.append("(i.item_code ILIKE %(search)s OR i.item_name ILIKE %(search)s)")
            params["search"] = f"%{filters.search_text}%"

        where_clause = " AND ".join(where)
        offset = max(filters.page - 1, 0) * filters.page_size

        count_sql = f"SELECT COUNT(*) AS total FROM item i WHERE {where_clause};"
        data_sql = f"""
            SELECT i.*,
                   COALESCE((SELECT SUM(b.batch_qty) FROM item_batch b WHERE b.item_id = i.item_id), 0) AS total_stock,
                   (
                       SELECT b.batch_no FROM item_batch b
                       WHERE b.item_id = i.item_id AND b.batch_qty > 0
                       ORDER BY b.expiry_year ASC, b.expiry_month ASC
                       LIMIT 1
                   ) AS nearest_batch_no,
                   (
                       SELECT b.expiry_display FROM item_batch b
                       WHERE b.item_id = i.item_id AND b.batch_qty > 0
                       ORDER BY b.expiry_year ASC, b.expiry_month ASC
                       LIMIT 1
                   ) AS nearest_expiry_display
            FROM item i
            WHERE {where_clause}
            ORDER BY i.item_name ASC
            LIMIT %(limit)s OFFSET %(offset)s;
        """

        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(count_sql, params)
                total_count = cur.fetchone()["total"]

                data_params = dict(params)
                data_params["limit"] = filters.page_size
                data_params["offset"] = offset
                cur.execute(data_sql, data_params)
                rows = [dict(r) for r in cur.fetchall()]

        return rows, total_count

    def get_total_stock(self, item_id: int) -> float:
        sql = "SELECT COALESCE(SUM(batch_qty), 0) AS total FROM item_batch WHERE item_id = %(item_id)s;"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_id": item_id})
                return float(cur.fetchone()["total"])

    def get_low_stock_items(self) -> list[dict]:
        """
        Returns active, non-deleted items where total_stock <= minimum_stock.
        Each returned row is a dict with keys:
        - item_id
        - item_name
        - current_stock
        - minimum_stock

        Live query — no caching. Caller should snapshot stock_at_order_time/minimum_stock_at_order_time
        from the returned rows if they want to persist why an item was suggested.
        """
        # Use the file's _get_connection() which returns a psycopg2 connection (context manager)
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                sql = """
                    SELECT i.item_id,
                        i.item_name,
                        COALESCE(SUM(b.batch_qty), 0) AS current_stock,
                        i.minimum_stock
                    FROM item i
                    LEFT JOIN item_batch b ON i.item_id = b.item_id
                    WHERE i.is_deleted = FALSE
                    AND i.status = 'Active'
                    GROUP BY i.item_id, i.item_name, i.minimum_stock
                    HAVING COALESCE(SUM(b.batch_qty), 0) <= i.minimum_stock
                    ORDER BY (i.minimum_stock - COALESCE(SUM(b.batch_qty),0)) DESC
                """
                cur.execute(sql)
                rows = cur.fetchall()
                # RealDictCursor => each row is already a dict
                return rows

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def soft_delete(self, item_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: Optional[str]) -> bool:
        sql = """
            UPDATE item
            SET is_deleted = TRUE, deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s, deleted_at_bs = %(deleted_at_bs)s
            WHERE item_id = %(item_id)s AND is_deleted = FALSE;
        """
        params = {"item_id": item_id, "deleted_by": deleted_by, "deleted_at_ad": deleted_at_ad, "deleted_at_bs": deleted_at_bs}
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                if ok:
                    logger.info("Item soft-deleted: id=%s by=%s", item_id, deleted_by)
                return ok

    def restore(self, item_id: int, updated_by: int, updated_at_ad, updated_at_bs: Optional[str]) -> bool:
        sql = """
            UPDATE item
            SET is_deleted = FALSE, deleted_by = NULL, deleted_at_ad = NULL, deleted_at_bs = NULL,
                updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE item_id = %(item_id)s AND is_deleted = TRUE;
        """
        params = {"item_id": item_id, "updated_by": updated_by, "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs}
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                if ok:
                    logger.info("Item restored: id=%s by=%s", item_id, updated_by)
                return ok


class ItemBatchModel:
    """Data-access layer for the `item_batch` table. SQL only."""

    def insert(self, data: dict[str, Any]) -> int:
        """
        `data` keys: item_id, batch_no, expiry_year, expiry_month, batch_qty,
        batch_purchase_rate, remarks, created_by, created_at_ad, created_at_bs.

        NOTE: this is the plain, non-ledger insert -- kept for callers that
        genuinely don't need a stock_ledger row (there are none in the
        Engine layer today; every real caller should go through
        insert_with_ledger() below instead, so batch_qty and stock_ledger
        never drift apart). Left in place only as a low-level primitive.
        """
        columns = [
            "item_id", "batch_no", "expiry_year", "expiry_month",
            "batch_qty", "batch_purchase_rate", "remarks",
            "created_by", "created_at_ad", "created_at_bs",
        ]
        col_sql = ", ".join(columns)
        placeholder_sql = ", ".join(f"%({c})s" for c in columns)
        sql = f"""
            INSERT INTO item_batch ({col_sql})
            VALUES ({placeholder_sql})
            RETURNING item_batch_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()["item_batch_id"]
                conn.commit()
                logger.info("Item batch inserted: id=%s item_id=%s batch_no=%s", new_id, data.get("item_id"), data.get("batch_no"))
                return new_id

    def insert_with_ledger(self, batch_data: dict[str, Any], ledger_data: dict[str, Any]) -> tuple[int, int]:
        """
        Creates a brand-new item_batch row AND its matching stock_ledger
        entry in ONE database transaction -- either both are saved or
        neither is, so batch_qty and the ledger can never disagree.

        Used for: Opening Stock (today) and the first lot of a future
        Purchase (transaction_type='PURCHASE' in ledger_data instead of
        'OPENING' -- everything else about this call stays the same).

        `batch_data`: same keys as insert() above.
        `ledger_data`: item_id, item_batch_id (filled in here once the
        batch's id is known), transaction_type, quantity_change,
        balance_after, reference_type, reference_id, remarks,
        created_by, created_at_ad, created_at_bs.

        Returns (new_item_batch_id, new_stock_ledger_id).
        """
        batch_columns = [
            "item_id", "batch_no", "expiry_year", "expiry_month",
            "batch_qty", "batch_purchase_rate", "remarks",
            "created_by", "created_at_ad", "created_at_bs",
        ]
        batch_col_sql = ", ".join(batch_columns)
        batch_placeholder_sql = ", ".join(f"%({c})s" for c in batch_columns)
        batch_sql = f"""
            INSERT INTO item_batch ({batch_col_sql})
            VALUES ({batch_placeholder_sql})
            RETURNING item_batch_id;
        """

        ledger_columns = [
            "item_id", "item_batch_id", "transaction_type", "quantity_change",
            "balance_after", "reference_type", "reference_id", "remarks",
            "created_by", "created_at_ad", "created_at_bs",
        ]
        ledger_col_sql = ", ".join(ledger_columns)
        ledger_placeholder_sql = ", ".join(f"%({c})s" for c in ledger_columns)
        ledger_sql = f"""
            INSERT INTO stock_ledger ({ledger_col_sql})
            VALUES ({ledger_placeholder_sql})
            RETURNING stock_ledger_id;
        """

        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(batch_sql, batch_data)
                new_batch_id = cur.fetchone()["item_batch_id"]

                ledger_data = dict(ledger_data)
                ledger_data["item_batch_id"] = new_batch_id
                cur.execute(ledger_sql, ledger_data)
                new_ledger_id = cur.fetchone()["stock_ledger_id"]

            conn.commit()
            logger.info(
                "Item batch + ledger inserted atomically: batch_id=%s ledger_id=%s item_id=%s type=%s",
                new_batch_id, new_ledger_id, batch_data.get("item_id"), ledger_data.get("transaction_type"),
            )
            return new_batch_id, new_ledger_id

    def update_qty_with_ledger(self, item_batch_id: int, quantity_change: float, ledger_data: dict[str, Any]) -> int:
        """
        Adjusts an EXISTING batch's balance (up for Purchase/Sale Return,
        down for Sale/Purchase Return/a downward Adjustment) and writes
        the matching stock_ledger row, atomically. Not called anywhere
        yet (Purchase/Sale modules don't exist in this repo), but built
        now so ItemEngine.post_stock_movement() has a real Model method
        to call the day they land -- see its docstring in
        engines/item_engine.py.

        `ledger_data` must NOT include balance_after -- this method
        computes it from the batch's current balance_after locking the
        row (SELECT ... FOR UPDATE) to stay correct under concurrent
        writes, then sets it before inserting.
        """
        ledger_columns = [
            "item_id", "item_batch_id", "transaction_type", "quantity_change",
            "balance_after", "reference_type", "reference_id", "remarks",
            "created_by", "created_at_ad", "created_at_bs",
        ]
        ledger_col_sql = ", ".join(ledger_columns)
        ledger_placeholder_sql = ", ".join(f"%({c})s" for c in ledger_columns)
        ledger_sql = f"""
            INSERT INTO stock_ledger ({ledger_col_sql})
            VALUES ({ledger_placeholder_sql})
            RETURNING stock_ledger_id;
        """

        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT batch_qty FROM item_batch WHERE item_batch_id = %(id)s FOR UPDATE;",
                    {"id": item_batch_id},
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"item_batch {item_batch_id} not found.")
                new_balance = float(row["batch_qty"]) + quantity_change

                cur.execute(
                    "UPDATE item_batch SET batch_qty = %(new_qty)s WHERE item_batch_id = %(id)s;",
                    {"new_qty": new_balance, "id": item_batch_id},
                )

                data = dict(ledger_data)
                data["item_batch_id"] = item_batch_id
                data["quantity_change"] = quantity_change
                data["balance_after"] = new_balance
                cur.execute(ledger_sql, data)
                new_ledger_id = cur.fetchone()["stock_ledger_id"]

            conn.commit()
            logger.info(
                "Item batch %s qty adjusted by %s (new balance %s); ledger_id=%s",
                item_batch_id, quantity_change, new_balance, new_ledger_id,
            )
            return new_ledger_id

    def get_by_item(self, item_id: int) -> list[dict]:
        sql = """
            SELECT * FROM item_batch
            WHERE item_id = %(item_id)s
            ORDER BY expiry_year ASC, expiry_month ASC, batch_no ASC;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_id": item_id})
                return [dict(r) for r in cur.fetchall()]

    def get_by_id(self, item_batch_id: int) -> Optional[dict]:
        sql = "SELECT * FROM item_batch WHERE item_batch_id = %(id)s;"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": item_batch_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_item_and_batch_no(self, item_id: int, batch_no: str) -> Optional[dict]:
        """Finds an existing batch for this item by exact batch_no (case-
        insensitive) -- used by Purchase Invoice to decide whether a
        re-supplied batch should add stock to the existing row instead of
        creating a duplicate. Returns None if no such batch exists."""
        sql = """
            SELECT * FROM item_batch
            WHERE item_id = %(item_id)s AND LOWER(batch_no) = LOWER(%(batch_no)s)
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_id": item_id, "batch_no": batch_no})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_batch_no(self, item_id: int, batch_no: str, exclude_batch_id: Optional[int] = None) -> bool:
        sql = """
            SELECT 1 FROM item_batch
            WHERE item_id = %(item_id)s AND LOWER(batch_no) = LOWER(%(batch_no)s)
        """
        params: dict[str, Any] = {"item_id": item_id, "batch_no": batch_no}
        if exclude_batch_id is not None:
            sql += " AND item_batch_id != %(exclude_id)s"
            params["exclude_id"] = exclude_batch_id
        sql += ";"
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def exists_expiry(
        self, item_id: int, expiry_year: int, expiry_month: int, exclude_batch_id: Optional[int] = None
    ) -> bool:
        """True if another batch of this item already has this exact expiry
        (month+year). Used to enforce: one expiry date can't be split across
        two different batch numbers."""
        sql = """
            SELECT 1 FROM item_batch
            WHERE item_id = %(item_id)s
              AND expiry_year = %(expiry_year)s
              AND expiry_month = %(expiry_month)s
        """
        params: dict[str, Any] = {
            "item_id": item_id, "expiry_year": expiry_year, "expiry_month": expiry_month,
        }
        if exclude_batch_id is not None:
            sql += " AND item_batch_id != %(exclude_id)s"
            params["exclude_id"] = exclude_batch_id
        sql += ";"
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def update(self, item_batch_id: int, data: dict[str, Any]) -> bool:
        """
        Updates an existing batch's own fields (batch_no, expiry, purchase
        rate, remarks, batch_qty). Deliberately does NOT touch stock_ledger --
        this is for correcting batch details via Item Master, not for real
        stock movements. Any actual stock transaction (Purchase/Sale/Return)
        must keep going through insert_with_ledger()/update_qty_with_ledger()
        so batch_qty and the ledger never drift apart.
        """
        columns = ["batch_no", "expiry_year", "expiry_month", "batch_qty", "batch_purchase_rate", "remarks"]
        set_sql = ", ".join(f"{c} = %({c})s" for c in columns)
        params = {c: data.get(c) for c in columns}
        params["item_batch_id"] = item_batch_id
        sql = f"""
            UPDATE item_batch
            SET {set_sql}
            WHERE item_batch_id = %(item_batch_id)s;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                if updated:
                    logger.info("Item batch updated: id=%s", item_batch_id)
                return updated


class StockLedgerModel:
    """
    Data-access layer for the `stock_ledger` table. Append-only -- there
    is deliberately no update() or delete() here (see
    database/schema_stock_ledger.sql's design notes). Most inserts
    happen via ItemBatchModel.insert_with_ledger()/update_qty_with_ledger()
    above (same transaction as the batch change); this class's own
    insert() exists for the rare case of logging a movement against an
    EXISTING batch with NO quantity change of its own tracked elsewhere
    (not used by ItemEngine today, kept for completeness/future modules).
    """

    def insert(self, data: dict[str, Any]) -> int:
        columns = [
            "item_id", "item_batch_id", "transaction_type", "quantity_change",
            "balance_after", "reference_type", "reference_id", "remarks",
            "created_by", "created_at_ad", "created_at_bs",
        ]
        col_sql = ", ".join(columns)
        placeholder_sql = ", ".join(f"%({c})s" for c in columns)
        sql = f"""
            INSERT INTO stock_ledger ({col_sql})
            VALUES ({placeholder_sql})
            RETURNING stock_ledger_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()["stock_ledger_id"]
                conn.commit()
                return new_id

    def get_by_item(self, item_id: int) -> list[dict]:
        sql = """
            SELECT * FROM stock_ledger
            WHERE item_id = %(item_id)s
            ORDER BY created_at_ad DESC;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_id": item_id})
                return [dict(r) for r in cur.fetchall()]

    def get_by_batch(self, item_batch_id: int) -> list[dict]:
        sql = """
            SELECT * FROM stock_ledger
            WHERE item_batch_id = %(item_batch_id)s
            ORDER BY created_at_ad ASC;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_batch_id": item_batch_id})
                return [dict(r) for r in cur.fetchall()]


__all__ = ["ItemModel", "ItemBatchModel", "StockLedgerModel", "ItemSearchFilters", "ITEM_COLUMNS"]
