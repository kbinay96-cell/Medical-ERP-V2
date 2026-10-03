"""
Raw data queries for the Dashboard KPIs, using the current ERP schemas.
"""

from datetime import date
from typing import Optional

from database.db import get_connection
from utils.app_logger import get_logger
from models.user_model import count_active_users

logger = get_logger()


def _safe_scalar_query(query: str, params: tuple = ()) -> Optional[float]:
    """Return None on a database error so the UI can distinguish failure from zero."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                if row is None:
                    return 0
                return list(row.values())[0] or 0
    except Exception:
        logger.exception("Dashboard KPI query failed.")
        return None


def get_today_sales_total(today_ad: date | None = None) -> Optional[float]:
    today_ad = today_ad or date.today()
    return _safe_scalar_query(
        """
        SELECT COALESCE(SUM(grand_total), 0) AS total
        FROM sale_invoice
        WHERE invoice_date_ad = %s
          AND status = 'Posted'
          AND is_deleted = FALSE
        """,
        (today_ad,),
    )


def get_today_purchase_total(today_ad: date | None = None) -> Optional[float]:
    today_ad = today_ad or date.today()
    return _safe_scalar_query(
        """
        SELECT COALESCE(SUM(grand_total), 0) AS total
        FROM purchase_invoice
        WHERE invoice_date_ad = %s
          AND status = 'Posted'
          AND is_deleted = FALSE
        """,
        (today_ad,),
    )


def get_stock_value() -> Optional[float]:
    return _safe_scalar_query(
        """
        SELECT COALESCE(SUM(batch_qty * batch_purchase_rate), 0) AS total
        FROM item_batch
        WHERE batch_qty > 0
        """
    )


def get_low_stock_count(threshold_qty: float = 10) -> Optional[float]:
    return _safe_scalar_query(
        """
        SELECT COUNT(*) AS total
        FROM item i
        LEFT JOIN (
            SELECT item_id, SUM(batch_qty) AS available_qty
            FROM item_batch
            GROUP BY item_id
        ) stock ON stock.item_id = i.item_id
        WHERE i.is_deleted = FALSE
          AND i.status = 'Active'
          AND COALESCE(stock.available_qty, 0)
              <= COALESCE(NULLIF(i.minimum_stock, 0), %s)
        """,
        (threshold_qty,),
    )


def get_expiring_medicines_count(within_days: int = 90) -> Optional[float]:
    return _safe_scalar_query(
        """
        SELECT COUNT(*) AS total
        FROM item_batch
        WHERE batch_qty > 0
          AND make_date(expiry_year, expiry_month, 1) + INTERVAL '1 month' > CURRENT_DATE
          AND make_date(expiry_year, expiry_month, 1) + INTERVAL '1 month'
              <= (CURRENT_DATE + %s * INTERVAL '1 day')
        """,
        (within_days,),
    )


def get_pending_payments_total() -> Optional[float]:
    return _safe_scalar_query(
        """
        SELECT COALESCE(SUM(GREATEST(
            pi.grand_total
            - COALESCE(payments.total_allocated, 0)
            - COALESCE(returns.total_adjusted, 0),
            0
        )), 0) AS total
        FROM purchase_invoice pi
        LEFT JOIN (
            SELECT pa.purchase_invoice_id, SUM(pa.allocated_amount) AS total_allocated
            FROM payment_allocation pa
            JOIN payment p ON p.payment_id = pa.payment_id
            WHERE p.status != 'Cancelled' AND p.is_deleted = FALSE
            GROUP BY pa.purchase_invoice_id
        ) payments ON payments.purchase_invoice_id = pi.purchase_invoice_id
        LEFT JOIN (
            SELECT purchase_invoice_id, SUM(grand_total) AS total_adjusted
            FROM purchase_return
            WHERE settlement_mode = 'Adjust Against Payable'
              AND status != 'Cancelled'
              AND is_deleted = FALSE
            GROUP BY purchase_invoice_id
        ) returns ON returns.purchase_invoice_id = pi.purchase_invoice_id
        WHERE pi.status = 'Posted' AND pi.is_deleted = FALSE
        """
    )


def get_pending_receipts_total() -> Optional[float]:
    return _safe_scalar_query(
        """
        SELECT COALESCE(SUM(GREATEST(
            si.balance_amount
            - COALESCE(receipts.total_allocated, 0)
            - COALESCE(returns.total_adjusted, 0),
            0
        )), 0) AS total
        FROM sale_invoice si
        LEFT JOIN (
            SELECT ra.sale_invoice_id, SUM(ra.allocated_amount) AS total_allocated
            FROM receipt_allocation ra
            JOIN receipt r ON r.receipt_id = ra.receipt_id
            WHERE r.status != 'Cancelled' AND r.is_deleted = FALSE
            GROUP BY ra.sale_invoice_id
        ) receipts ON receipts.sale_invoice_id = si.sale_invoice_id
        LEFT JOIN (
            SELECT sale_invoice_id, SUM(grand_total) AS total_adjusted
            FROM sale_return
            WHERE refund_mode = 'Adjust Against Invoice'
              AND status != 'Cancelled'
              AND is_deleted = FALSE
            GROUP BY sale_invoice_id
        ) returns ON returns.sale_invoice_id = si.sale_invoice_id
        WHERE si.status = 'Posted' AND si.is_deleted = FALSE
        """
    )


def get_active_users_count() -> Optional[float]:
    try:
        return count_active_users()
    except Exception:
        logger.exception("Dashboard active-user KPI query failed.")
        return None
