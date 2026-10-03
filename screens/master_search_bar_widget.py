"""
screens/master_search_bar_widget.py

Master Search Bar Widget - Medical ERP V2 (RP10)

A single reusable search bar widget calling
ReportEngine.get_master_search_results(search_text) as the user types
(debounced), showing a grouped dropdown popup (Reports / Customers /
Items / Suppliers / Sales / Purchases / Receipts / Payments / Sale
Returns / Purchase Returns / Purchase Orders / Manufacturers -- keys
come straight from whatever search_delegates ReportEngine was
constructed with; this widget does not hardcode the group list, it
just renders whatever groups the Engine returns). On click:
    - A "reports" group result -> emits report_activated(report_code).
    - Any other group's result -> emits record_activated(group_key, row)
      so the parent decides which module's own View/Detail screen to
      open; this widget never builds a new detail view itself.

No SQL, no business logic -- purely a thin UI adapter over
ReportEngine.get_master_search_results(), matching the Reports module's
"Screen layer only" convention used throughout this module.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from utils.app_logger import get_logger

logger = get_logger()

_DEBOUNCE_MS = 300
_MIN_CHARS = 2

# Display label per group key. A key with no entry here falls back to
# its own name, Title Cased -- so a new delegate ReportEngine gains
# later still renders with a readable header instead of breaking.
_GROUP_LABELS = {
    "reports": "Reports",
    "customers": "Customers",
    "items": "Items",
    "suppliers": "Suppliers",
    "sale_invoices": "Sales",
    "purchase_invoices": "Purchases",
    "receipts": "Receipts",
    "payments": "Payments",
    "sale_returns": "Sale Returns",
    "purchase_returns": "Purchase Returns",
    "purchase_orders": "Purchase Orders",
    "manufacturers": "Manufacturers",
    "users": "Users",
    "country_tax": "Country Tax",
    "settings": "Settings",
}

# Per group, which key on each result row is shown as its label.
_ROW_LABEL_KEYS = {
    "customers": "customer_name",
    "items": "item_name",
    "suppliers": "supplier_name",
    "sale_invoices": "invoice_number",
    "purchase_invoices": "invoice_number",
    "receipts": "receipt_number",
    "payments": "payment_number",
    "sale_returns": "return_number",
    "purchase_returns": "return_number",
    "purchase_orders": "po_number",
    "manufacturers": "manufacturer_name",
    "users": "fullname",
    "country_tax": "country",
    "settings": "setting_key",
}


class MasterSearchBarWidget(QWidget):
    report_activated = Signal(str)            # report_code
    record_activated = Signal(str, dict)       # group_key, row

    def __init__(self, parent: Optional[QWidget], engine) -> None:
        super().__init__(parent)
        self._engine = engine
        self._last_results: dict[str, list[dict[str, Any]]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._search_bar = QLineEdit(self)
        self._search_bar.setObjectName("txtMasterSearch")
        self._search_bar.setPlaceholderText("Search any things")
        self._search_bar.setClearButtonEnabled(True)
        layout.addWidget(self._search_bar)

        # A real Qt::Popup window grabs keyboard/mouse input at the
        # platform level the instant it's shown -- WA_ShowWithoutActivating
        # does NOT override that grab, it only controls window activation,
        # a separate thing. That grab is exactly why a 3rd typed character
        # used to go nowhere: the popup silently ate it. Tool +
        # FramelessWindowHint + WindowDoesNotAcceptFocus instead gives an
        # independent floating window that is NEVER handed keyboard focus
        # at all, so the search bar keeps it throughout. The trade-off:
        # we lose Popup's automatic "close on outside click" -- that's
        # reimplemented by hand in eventFilter() below.
        self._popup = QFrame(self)
        self._popup.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self._popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._popup.setObjectName("frmMasterSearchPopup")
        self._popup.setFrameShape(QFrame.Shape.StyledPanel)
        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(4, 4, 4, 4)
        self._results_list = QListWidget(self._popup)
        self._results_list.setObjectName("lstMasterSearchResults")
        # NoFocus here is about KEYBOARD focus only -- mouse clicks on
        # list items still fire itemClicked perfectly fine without it.
        self._results_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        popup_layout.addWidget(self._results_list)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._run_search)

        self._search_bar.textChanged.connect(self._on_text_changed)
        self._results_list.itemClicked.connect(self._on_item_activated)

        # Replaces Popup's free close-on-outside-click/Escape behaviour.
        self._search_bar.installEventFilter(self)
        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------------ #
    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt override)
        if watched is self._search_bar and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape and self._popup.isVisible():
                self._popup.hide()
                return True
        elif event.type() == QEvent.Type.MouseButtonPress and self._popup.isVisible():
            click_pos = event.globalPosition().toPoint()
            inside_popup = self._popup.geometry().contains(click_pos)
            inside_search_bar = self._search_bar.rect().contains(
                self._search_bar.mapFromGlobal(click_pos)
            )
            if not inside_popup and not inside_search_bar:
                self._popup.hide()
        return super().eventFilter(watched, event)

    def _on_text_changed(self, text: str) -> None:
        if len(text.strip()) < _MIN_CHARS:
            self._popup.hide()
            self._debounce_timer.stop()
            return
        self._debounce_timer.start()

    def _run_search(self) -> None:
        search_text = self._search_bar.text().strip()
        if len(search_text) < _MIN_CHARS:
            return
        self._search_error = False
        try:
            self._last_results = self._engine.get_master_search_results(search_text)
        except Exception:
            logger.exception("Master Search failed.")
            self._search_error = True
            self._last_results = {}
        self._render_grouped_results(self._last_results)

    def _render_grouped_results(self, results: dict[str, list[dict]]) -> None:
        self._results_list.clear()
        if getattr(self, "_search_error", False):
            error_item = QListWidgetItem("Search unavailable. Check the application log.")
            error_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._results_list.addItem(error_item)
            self._show_popup()
            return
        any_rows = False
        for group_key, rows in results.items():
            if not rows:
                continue
            any_rows = True
            header_item = QListWidgetItem(_GROUP_LABELS.get(group_key, group_key.title()))
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            header_item.setForeground(self.palette().mid())
            self._results_list.addItem(header_item)
            for row in rows:
                label = self._row_label(group_key, row)
                item = QListWidgetItem(f"    {label}")
                item.setData(Qt.ItemDataRole.UserRole, (group_key, row))
                self._results_list.addItem(item)

        if not any_rows:
            empty_item = QListWidgetItem("No matches.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._results_list.addItem(empty_item)

        self._show_popup()

    def _row_label(self, group_key: str, row: dict[str, Any]) -> str:
        if group_key == "reports":
            return str(row.get("report_name") or row.get("report_code") or "")
        label_key = _ROW_LABEL_KEYS.get(group_key)
        if label_key and row.get(label_key):
            return str(row[label_key])
        # Fallback for a delegate group this widget doesn't know the
        # label key for yet -- first string-looking value in the row.
        for value in row.values():
            if isinstance(value, str) and value:
                return value
        return str(row)

    def _show_popup(self) -> None:
        bar_pos = self._search_bar.mapToGlobal(self._search_bar.rect().bottomLeft())
        self._popup.setFixedWidth(self._search_bar.width())
        self._popup.move(bar_pos)
        self._popup.show()

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.ItemDataRole.UserRole)
        if payload is None:
            return
        group_key, row = payload
        self._popup.hide()
        self._search_bar.clear()
        if group_key == "reports":
            report_code = row.get("report_code")
            if report_code:
                self.report_activated.emit(report_code)
        else:
            self.record_activated.emit(group_key, row)


__all__ = ["MasterSearchBarWidget"]