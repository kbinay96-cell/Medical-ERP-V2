
"""
=========================================================
Medical ERP V2
Dashboard Engine
---------------------------------------------------------
Purpose:
    Business logic for the Dashboard - combines KPI data,
    permission-based menu visibility, and alert generation.
    No SQL here directly - delegates to models/dashboard_model.
=========================================================
"""

from dataclasses import dataclass, field

from utils.app_logger import get_logger
from models import dashboard_model
from engines.authorization_engine import get_accessible_menus
from engines.license_manager import validate_license
from engines.subscription_manager import validate_subscription

logger = get_logger()

LOW_STOCK_ALERT_THRESHOLD = 10
EXPIRY_ALERT_WINDOW_DAYS = 90


@dataclass
class DashboardData:
    today_sales: float = 0
    today_purchase: float = 0
    stock_value: float = 0
    low_stock_count: float = 0
    expiring_count: float = 0
    pending_payments: float = 0
    pending_receipts: float = 0
    active_users: float = 0
    alerts: list = field(default_factory=list)
    accessible_menus: list = field(default_factory=list)


# Default sidebar structure (per Blueprint Part-4). A module
# only appears if the logged-in role has View access to it
# (per get_accessible_menus) OR is Administrator (sees all).
SIDEBAR_MODULES = {
    "Masters": ["Company", "Supplier", "Manufacturer", "Customer", "Item", "Supplier-Mfg Discount", "Country Tax"],
    "Purchase": ["New Purchase", "Purchase List"],
    "Sales": ["New Sale", "Sale List"],
    "Inventory": ["Stock Ledger", "Stock Master"],
    "Accounts": ["Payment", "Receipt"],
    "Reports": ["Reports"],
    "Settings": ["Settings", "User Master"],
}


def build_dashboard(roleid: int, is_admin: bool) -> DashboardData:
    """
    Loads everything the Dashboard Screen needs to display.
    Never raises - any individual piece failing degrades
    gracefully rather than blocking the whole Dashboard.
    """
    try:
        accessible_menus = get_accessible_menus(roleid) if not is_admin else _all_menu_names()
    except Exception as e:
        logger.exception(f"build_dashboard: could not load accessible menus: {e}")
        accessible_menus = []

    data = DashboardData(
        today_sales=dashboard_model.get_today_sales_total(),
        today_purchase=dashboard_model.get_today_purchase_total(),
        stock_value=dashboard_model.get_stock_value(),
        low_stock_count=dashboard_model.get_low_stock_count(LOW_STOCK_ALERT_THRESHOLD),
        expiring_count=dashboard_model.get_expiring_medicines_count(EXPIRY_ALERT_WINDOW_DAYS),
        pending_payments=dashboard_model.get_pending_payments_total(),
        pending_receipts=dashboard_model.get_pending_receipts_total(),
        active_users=dashboard_model.get_active_users_count(),
        accessible_menus=accessible_menus,
    )

    data.alerts = _build_alerts(data)

    return data


def _all_menu_names() -> list[str]:
    names = []
    for module, screens in SIDEBAR_MODULES.items():
        names.append(module)
        names.extend(screens)
    return names


def _build_alerts(data: DashboardData) -> list[str]:
    alerts = []

    if data.low_stock_count > 0:
        alerts.append(f"{int(data.low_stock_count)} item(s) are low on stock.")

    if data.expiring_count > 0:
        alerts.append(f"{int(data.expiring_count)} batch(es) are expiring within {EXPIRY_ALERT_WINDOW_DAYS} days.")

    try:
        license_ok, license_message = validate_license()
        if not license_ok:
            alerts.append(f"License: {license_message}")
    except Exception as e:
        logger.exception(f"_build_alerts: license check failed: {e}")

    try:
        subscription_ok, subscription_message = validate_subscription()
        if not subscription_ok:
            alerts.append(f"Subscription: {subscription_message}")
    except Exception as e:
        logger.exception(f"_build_alerts: subscription check failed: {e}")

    return alerts



