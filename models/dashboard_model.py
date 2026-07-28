"""
=========================================================
Medical ERP V2
Dashboard Model
---------------------------------------------------------
Purpose:
    Raw data queries for Dashboard KPI cards.

NOTE: Purchase, Sales, and Stock modules have not been
built yet in V2 (only the Login/Dashboard foundation
exists so far). The functions below query the REAL tables
for those modules and will start returning real numbers
automatically once those modules are built - they do NOT
return fabricated/dummy figures. Until then, they safely
report 0 (with the failure logged) rather than crashing
the Dashboard.
=========================================================
"""

from datetime import date

from database.db import get_connection
from utils.app_logger import get_logger
from models.user_model import count_active_users

logger = get_logger()


def _safe_scalar_query(query: str, params: tuple = ()) -> float:
    """
    Runs a single-value query. Returns 0 (and logs) if the
    underlying table doesn't exist yet or any DB error occurs -
    this keeps the Dashboard usable even before every module
    has been built.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                if row is None:
                    return 0
                return list(row.values())[0] or 0
    except Exception as e:
        logger.info(f"Dashboard KPI query unavailable (module not built yet or DB issue): {e}")
        return 0


def get_today_sales_total(today_ad: date | None = None) -> float:
    today_ad = today_ad or date.today()
    return _safe_scalar_query(
        "SELECT COALESCE(SUM(netamount), 0) AS total FROM saleheader WHERE saledatead = %s",
        (today_ad,),
    )


def get_today_purchase_total(today_ad: date | None = None) -> float:
    today_ad = today_ad or date.today()
    return _safe_scalar_query(
        "SELECT COALESCE(SUM(netamount), 0) AS total FROM purchaseheader WHERE purchasedatead = %s",
        (today_ad,),
    )


def get_stock_value() -> float:
    return _safe_scalar_query(
        "SELECT COALESCE(SUM(availableqty * purchaserate), 0) AS total FROM stockmaster"
    )


def get_low_stock_count(threshold_qty: float = 10) -> float:
    return _safe_scalar_query(
        "SELECT COUNT(*) AS total FROM stockmaster WHERE availableqty <= %s",
        (threshold_qty,),
    )


def get_expiring_medicines_count(within_days: int = 90) -> float:
    return _safe_scalar_query(
        """
        SELECT COUNT(*) AS total FROM stockmaster
        WHERE expiryaddate IS NOT NULL
          AND expiryaddate <= (CURRENT_DATE + %s * INTERVAL '1 day')
        """,
        (within_days,),
    )


def get_pending_payments_total() -> float:
    return _safe_scalar_query(
        "SELECT COALESCE(SUM(balanceamount), 0) AS total FROM purchaseheader WHERE balanceamount > 0"
    )


def get_pending_receipts_total() -> float:
    return _safe_scalar_query(
        "SELECT COALESCE(SUM(balanceamount), 0) AS total FROM saleheader WHERE balanceamount > 0"
    )


def get_active_users_count() -> float:
    try:
        return count_active_users()
    except Exception as e:
        logger.info(f"get_active_users_count unavailable: {e}")
        return 0
