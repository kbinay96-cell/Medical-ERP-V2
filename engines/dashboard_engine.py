
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
from typing import Optional

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
    today_sales: Optional[float] = 0
    today_purchase: Optional[float] = 0
    stock_value: Optional[float] = 0
    low_stock_count: Optional[float] = 0
    expiring_count: Optional[float] = 0
    pending_payments: Optional[float] = 0
    pending_receipts: Optional[float] = 0
    active_users: Optional[float] = 0
    alerts: list = field(default_factory=list)
    accessible_menus: list = field(default_factory=list)


# Default sidebar structure (per Blueprint Part-4). A module
# only appears if the logged-in role has View access to it
# (per get_accessible_menus) OR is Administrator (sees all).
SIDEBAR_MODULES = {
    "Masters": ["Company", "Supplier", "Manufacturer", "Customer", "Item", "Supplier-Mfg Discount", "Country Tax"],
    "Purchase": ["Purchase", "Purchase Order", "Purchase Invoice List", "Purchase Return"],
    "Sales": ["New Sale", "Sale List", "Sale Free Scheme", "Sale Return"],
    "Inventory": ["Stock Ledger", "Stock Master"],
    "Accounts": [
        "Payment",
        "Receipt",
        "Chart of Accounts",
        "Journal Voucher",
        "Account Ledger",
        "Period Lock",
        "Bank Reconciliation",
    ],
    "Reports": ["Management Dashboard", "Reports", "Audit Log"],
    "Settings": ["Settings", "User Master", "Password Reset Requests", "Change Password"],
}

_SIDEBAR_PERMISSION_ALIASES = {
    "Company": ("Company",),
    "Supplier": ("Supplier",),
    "Manufacturer": ("Manufacturer",),
    "Customer": ("Customer",),
    "Item": ("Item",),
    "Supplier-Mfg Discount": ("Supplier-Mfg Discount", "Supplier Manufacturer Discount"),
    "Country Tax": ("Country Tax",),
    "Purchase": ("Purchase",),
    "Purchase Order": ("Purchase Order",),
    "Purchase Invoice List": ("Purchase Invoice List",),
    "Purchase Return": ("Purchase Return",),
    "New Sale": ("Sale", "New Sale"),
    "Sale List": ("Sale", "Sale List"),
    "Sale Free Scheme": ("Sale Free Scheme", "Sale"),
    "Sale Return": ("Sale Return", "Sale"),
    "Stock Ledger": ("Stock Ledger", "Item"),
    "Stock Master": ("Stock Master", "Item"),
    "Payment": ("Payment",),
    "Receipt": ("Receipt",),
    "Chart of Accounts": ("Chart of Accounts",),
    "Journal Voucher": ("Journal Voucher",),
    "Account Ledger": ("Account Ledger",),
    "Period Lock": ("Period Lock",),
    "Bank Reconciliation": ("Bank Reconciliation",),
    "Management Dashboard": ("Management Dashboard", "Reports"),
    "Reports": ("Reports",),
    "Audit Log": ("Audit Log",),
    "Settings": ("Settings",),
    "User Master": ("User Master",),
    "Password Reset Requests": ("Password Reset Requests",),
    "Change Password": ("Change Password",),
}


def filter_sidebar_modules(
    accessible_menus: list[str] | None,
    is_admin: bool = False,
) -> dict[str, list[str]]:
    """Return only module entries for which the role has a view permission."""
    if is_admin:
        return {module: list(screens) for module, screens in SIDEBAR_MODULES.items()}

    accessible = {name.strip().casefold() for name in (accessible_menus or [])}
    visible_modules = {}
    for module, screens in SIDEBAR_MODULES.items():
        visible_screens = [
            screen for screen in screens
            if screen in {"Settings", "Change Password"}
            or (
                screen not in {"Audit Log", "Password Reset Requests"}
                and any(
                    alias.casefold() in accessible
                    for alias in _SIDEBAR_PERMISSION_ALIASES.get(screen, (screen,))
                )
            )
        ]
        if visible_screens:
            visible_modules[module] = visible_screens
    return visible_modules


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
    if any(value is None for value in (
        data.today_sales,
        data.today_purchase,
        data.stock_value,
        data.low_stock_count,
        data.expiring_count,
        data.pending_payments,
        data.pending_receipts,
        data.active_users,
    )):
        data.alerts.append("Some dashboard data could not be loaded. Check the application log.")

    return data


def _all_menu_names() -> list[str]:
    names = []
    for module, screens in SIDEBAR_MODULES.items():
        names.append(module)
        names.extend(screens)
    return names


def _build_alerts(data: DashboardData) -> list[str]:
    alerts = []

    if data.low_stock_count is not None and data.low_stock_count > 0:
        alerts.append(f"{int(data.low_stock_count)} item(s) are low on stock.")

    if data.expiring_count is not None and data.expiring_count > 0:
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
