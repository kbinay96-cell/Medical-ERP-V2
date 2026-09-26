"""
engines/report_search_delegates.py

Report Search Delegates - Medical ERP V2

Thin ADAPTERS ONLY -- zero business logic, zero SQL. Each prior module's
Engine-layer search is reused untouched (Screen -> Engine -> Model is
preserved: this file calls engines.customer_engine / SupplierEngine /
ItemEngine, never a Model directly), but each has its own calling
convention and return shape:
    - engines.customer_engine.search_customers(...) -- module-level
      function, plain kwargs in, list[dict] out (already the exact
      shape ReportEngine needs).
    - SupplierEngine().search_suppliers(...) -- instance method,
      returns (list[SupplierDTO], int) -- a DTO list + a count.
    - ItemEngine() is already constructed once per app session (see
      DashboardScreen._init_purchase_engines -> self._item_engine) and
      passed in here rather than re-instantiated, since ItemEngine's
      constructor requires country_tax_lookup_fn/manufacturer_lookup_fn
      collaborators this module has no business rebuilding.
      .search_items(...) also returns (list[ItemDTO], int).

ReportEngine.get_master_search_results() needs ONE uniform convention
across every delegate: delegate(search_text: str) -> list[dict]. These
functions/factories exist only to bridge that gap -- DTOs are converted
to dicts via their own .to_dict(), never re-serialized by hand here.
"""

from __future__ import annotations

from typing import Any, Callable

# How many rows the Master Search dropdown shows per group -- kept small
# since it's a live-as-you-type dropdown, not a full report.
_MASTER_SEARCH_LIMIT = 20


def search_customers_delegate(search_text: str) -> list[dict[str, Any]]:
    from engines.customer_engine import search_customers
    return search_customers(search_text=search_text, is_active=True)


def make_supplier_search_delegate(supplier_engine) -> Callable[[str], list[dict[str, Any]]]:
    """
    Factory, not a bare function -- SupplierEngine is stateful (it's
    already constructed once in DashboardScreen._init_purchase_engines
    as self._supplier_engine) and must be reused, never re-instantiated
    here.
    """
    def _delegate(search_text: str) -> list[dict[str, Any]]:
        dtos, _total_count = supplier_engine.search_suppliers(
            search_text=search_text, page=1, page_size=_MASTER_SEARCH_LIMIT
        )
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_item_search_delegate(item_engine) -> Callable[[str], list[dict[str, Any]]]:
    """Same reasoning as make_supplier_search_delegate -- reuses the
    already-constructed self._item_engine, never rebuilds one."""
    def _delegate(search_text: str) -> list[dict[str, Any]]:
        dtos, _total_count = item_engine.search_items(
            search_text=search_text, page=1, page_size=_MASTER_SEARCH_LIMIT
        )
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_sale_invoice_search_delegate(sale_engine) -> Callable[[str], list[dict[str, Any]]]:
    """Reuses the already-constructed self._sale_engine."""
    def _delegate(search_text: str) -> list[dict[str, Any]]:
        dtos, _total_count = sale_engine.search_sale_invoices(
            search_text=search_text, page=1, page_size=_MASTER_SEARCH_LIMIT
        )
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_purchase_invoice_search_delegate(purchase_engine) -> Callable[[str], list[dict[str, Any]]]:
    """Reuses the already-constructed self._purchase_engine."""
    def _delegate(search_text: str) -> list[dict[str, Any]]:
        dtos, _total_count = purchase_engine.search_purchase_invoices(
            search_text=search_text, page=1, page_size=_MASTER_SEARCH_LIMIT
        )
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_receipt_search_delegate(receipt_engine) -> Callable[[str], list[dict[str, Any]]]:
    """Reuses the already-constructed self._receipt_engine."""
    from models.receipt_model import ReceiptSearchFilters

    def _delegate(search_text: str) -> list[dict[str, Any]]:
        filters = ReceiptSearchFilters(search_text=search_text, page_size=_MASTER_SEARCH_LIMIT)
        dtos = receipt_engine.search(filters)
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_payment_search_delegate(payment_engine) -> Callable[[str], list[dict[str, Any]]]:
    """Reuses the already-constructed self._payment_engine."""
    from models.payment_model import PaymentSearchFilters

    def _delegate(search_text: str) -> list[dict[str, Any]]:
        filters = PaymentSearchFilters(search_text=search_text, page_size=_MASTER_SEARCH_LIMIT)
        dtos = payment_engine.search(filters)
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_sale_return_search_delegate(sale_return_engine) -> Callable[[str], list[dict[str, Any]]]:
    """Reuses the already-constructed self._sale_return_engine."""
    from models.sale_return_model import SaleReturnSearchFilters

    def _delegate(search_text: str) -> list[dict[str, Any]]:
        filters = SaleReturnSearchFilters(search_text=search_text, page_size=_MASTER_SEARCH_LIMIT)
        dtos = sale_return_engine.search(filters)
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_purchase_order_search_delegate(purchase_order_engine) -> Callable[[str], list[dict[str, Any]]]:
    """Reuses the already-constructed self._purchase_order_engine."""
    def _delegate(search_text: str) -> list[dict[str, Any]]:
        dtos, _total_count = purchase_order_engine.search_purchase_orders(
            search_text=search_text, page=1, page_size=_MASTER_SEARCH_LIMIT
        )
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_purchase_return_search_delegate(purchase_invoice_model, item_engine) -> Callable[[str], list[dict[str, Any]]]:
    """
    Unlike Sale/Purchase/Receipt/Payment/SaleReturn, PurchaseReturnEngine
    is never kept as a persistent instance on DashboardScreen -- every
    other place that needs one constructs it fresh with the shared
    purchase_invoice_model/item_engine (its constructor requires both).
    This factory builds ONE instance, once, at wiring time, and reuses
    it for every Master Search call -- never re-constructed per keystroke.
    """
    from engines.purchase_return_engine import PurchaseReturnEngine
    from models.purchase_return_model import PurchaseReturnSearchFilters

    engine = PurchaseReturnEngine(purchase_invoice_model=purchase_invoice_model, item_engine=item_engine)

    def _delegate(search_text: str) -> list[dict[str, Any]]:
        filters = PurchaseReturnSearchFilters(search_text=search_text, page_size=_MASTER_SEARCH_LIMIT)
        dtos = engine.search(filters)
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_manufacturer_search_delegate() -> Callable[[str], list[dict[str, Any]]]:
    """
    ManufacturerEngine is likewise never kept as a persistent instance on
    DashboardScreen -- every form-opening method builds a bare
    ManufacturerEngine() on the spot (every constructor param is
    optional). Same pattern here: build ONE instance, once, reuse it.
    """
    from engines.manufacturer_engine import ManufacturerEngine

    engine = ManufacturerEngine()

    def _delegate(search_text: str) -> list[dict[str, Any]]:
        dtos, _total_count = engine.search_manufacturers(
            search_text=search_text, page=1, page_size=_MASTER_SEARCH_LIMIT
        )
        return [dto.to_dict() for dto in dtos]
    return _delegate


def make_user_search_delegate() -> Callable[[str], list[dict[str, Any]]]:
    """
    UserEngine has no __init__ of its own and no persistent instance on
    DashboardScreen -- screens/user_list_screen.py builds a bare
    UserEngine() the same way. Same build-once-and-reuse pattern as
    Manufacturer/PurchaseReturn/CountryTax above. UserDTO carries no
    password hash/salt or any other sensitive field (confirmed against
    models/user_model.py -- those never leave the raw model layer), so
    every field is safe to expose to Master Search as-is.
    """
    from dataclasses import asdict
    from engines.user_engine import UserEngine

    engine = UserEngine()

    def _delegate(search_text: str) -> list[dict[str, Any]]:
        dtos, _total_count = engine.search_users(
            search_text=search_text, page=1, page_size=_MASTER_SEARCH_LIMIT
        )
        return [asdict(dto) for dto in dtos]
    return _delegate


def make_country_tax_search_delegate() -> Callable[[str], list[dict[str, Any]]]:
    """Same build-once-and-reuse pattern -- CountryTaxEngine's own model/
    date_engine defaults make it safe to construct bare, exactly as
    screens/country_tax_list_screen.py already does."""
    from engines.country_tax_engine import CountryTaxEngine

    engine = CountryTaxEngine()

    def _delegate(search_text: str) -> list[dict[str, Any]]:
        dtos, _total_count = engine.search_taxes(
            search_text=search_text, page=1, page_size=_MASTER_SEARCH_LIMIT
        )
        return [dto.to_dict() for dto in dtos]
    return _delegate


def settings_search_delegate(search_text: str) -> list[dict[str, Any]]:
    """
    engines.settings_engine.search_settings() is a plain module-level
    function (no engine class, no dataclass) that already backs the
    Settings screen's own internal search box -- reused untouched here,
    just capped to the same dropdown-sized limit every other delegate
    uses.
    """
    from engines.settings_engine import search_settings
    return search_settings(search_text)[:_MASTER_SEARCH_LIMIT]


__all__ = [
    "search_customers_delegate",
    "make_supplier_search_delegate",
    "make_item_search_delegate",
    "make_sale_invoice_search_delegate",
    "make_purchase_invoice_search_delegate",
    "make_receipt_search_delegate",
    "make_payment_search_delegate",
    "make_sale_return_search_delegate",
    "make_purchase_order_search_delegate",
    "make_purchase_return_search_delegate",
    "make_manufacturer_search_delegate",
    "make_user_search_delegate",
    "make_country_tax_search_delegate",
    "settings_search_delegate",
]