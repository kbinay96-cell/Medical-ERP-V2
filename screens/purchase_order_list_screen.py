# screens/purchase_order_list_screen.py
from __future__ import annotations

import logging
import webbrowser
from urllib.parse import quote

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.purchase_order_engine import PurchaseOrderEngine

logger = logging.getLogger(__name__)

STATUS_OPTIONS = ["All", "Draft", "Sent", "Received", "Cancelled"]

COL_PO_NUMBER = 0
COL_SUPPLIER = 1
COL_ORDER_DATE = 2
COL_STATUS = 3
COL_WHATSAPP = 4
COL_EMAIL = 5
COL_VIEW = 6
COL_CANCEL = 7
COLUMN_COUNT = 8


# ---------------------------------------------------------------------------
# Shared send handlers — used by both this screen and the "send now" buttons
# on PurchaseOrderFormScreen right after a save.
# ---------------------------------------------------------------------------

def send_purchase_order_via_whatsapp(
    parent, engine: PurchaseOrderEngine, supplier_engine, purchase_order_id: int, current_user_id: int
) -> None:
    """1. text_map = engine.build_supplier_message(purchase_order_id)
    2. supplier = supplier_engine.get_supplier(...) -> mobile_no
    3. url = https://wa.me/{normalized_mobile_no}?text={urlencoded}
    4. webbrowser.open(url)
    5. engine.mark_sent(purchase_order_id, sent_via='whatsapp', current_user_id)
    If supplier.mobile_no is blank, show a warning instead of opening a
    broken link — never silently fail."""
    try:
        order = engine.get_purchase_order(purchase_order_id)
        text_map = engine.build_supplier_message(purchase_order_id)
        supplier = supplier_engine.get_supplier(order.supplier_id)
    except (RecordNotFoundError, ValidationError) as exc:
        QMessageBox.warning(parent, "Cannot Send", str(exc))
        return
    except Exception:
        logger.exception("Failed to prepare WhatsApp message for PO %s", purchase_order_id)
        QMessageBox.critical(parent, "Error", "Could not prepare the WhatsApp message.")
        return

    mobile_no = getattr(supplier, "mobile_no", None)
    if not mobile_no or not str(mobile_no).strip():
        QMessageBox.warning(
            parent, "No Mobile Number", "This supplier has no mobile number on file."
        )
        return

    normalized_mobile_no = "".join(ch for ch in str(mobile_no) if ch.isdigit())
    url = f"https://wa.me/{normalized_mobile_no}?text={quote(text_map['whatsapp_text'])}"
    webbrowser.open(url)

    try:
        engine.mark_sent(purchase_order_id, sent_via="whatsapp", current_user_id=current_user_id)
    except Exception:
        logger.exception("Failed to mark PO %s as sent (whatsapp)", purchase_order_id)


def send_purchase_order_via_email(
    parent, engine: PurchaseOrderEngine, supplier_engine, purchase_order_id: int, current_user_id: int
) -> None:
    """1. text_map = engine.build_supplier_message(purchase_order_id)
    2. supplier = supplier_engine.get_supplier(...) -> email
    3. url = mailto:{email}?subject={...}&body={...}
    4. webbrowser.open(url)
    5. engine.mark_sent(purchase_order_id, sent_via='email', current_user_id)
    If supplier.email is blank, show a warning instead."""
    try:
        order = engine.get_purchase_order(purchase_order_id)
        text_map = engine.build_supplier_message(purchase_order_id)
        supplier = supplier_engine.get_supplier(order.supplier_id)
    except (RecordNotFoundError, ValidationError) as exc:
        QMessageBox.warning(parent, "Cannot Send", str(exc))
        return
    except Exception:
        logger.exception("Failed to prepare email message for PO %s", purchase_order_id)
        QMessageBox.critical(parent, "Error", "Could not prepare the email message.")
        return

    email = getattr(supplier, "email", None)
    if not email or not str(email).strip():
        QMessageBox.warning(parent, "No Email Address", "This supplier has no email address on file.")
        return

    url = (
        f"mailto:{email}"
        f"?subject={quote(text_map['email_subject'])}"
        f"&body={quote(text_map['email_body'])}"
    )
    webbrowser.open(url)

    try:
        engine.mark_sent(purchase_order_id, sent_via="email", current_user_id=current_user_id)
    except Exception:
        logger.exception("Failed to mark PO %s as sent (email)", purchase_order_id)


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

class PurchaseOrderListScreen(QWidget):
    """List/search/filter — mirrors screens/supplier_list_screen.py.
    Filters: Supplier, Status (Draft/Sent/Received/Cancelled), Date range."""

    def __init__(self, parent, engine: PurchaseOrderEngine, supplier_engine, item_engine, current_user_id: int):
        super().__init__(parent)
        self._engine = engine
        self._supplier_engine = supplier_engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id

        self._build_ui()
        self._connect_signals()
        self._populate_supplier_filter()
        self.refresh()

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("PO number...")
        filter_row.addWidget(self.search_input)

        filter_row.addWidget(QLabel("Supplier:"))
        self.supplier_filter_combo = QComboBox()
        filter_row.addWidget(self.supplier_filter_combo)

        filter_row.addWidget(QLabel("Status:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(STATUS_OPTIONS)
        filter_row.addWidget(self.status_filter_combo)

        filter_row.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        filter_row.addWidget(self.date_from)

        filter_row.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        filter_row.addWidget(self.date_to)

        self.search_button = QPushButton("Filter")
        filter_row.addWidget(self.search_button)

        self.new_button = QPushButton("+ New Purchase Order")
        filter_row.addStretch()
        filter_row.addWidget(self.new_button)

        root.addLayout(filter_row)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(
            ["PO Number", "Supplier", "Order Date", "Status", "", "", "", ""]
        )
        self.table.horizontalHeader().setSectionResizeMode(COL_SUPPLIER, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table)

    def _connect_signals(self) -> None:
        self.search_button.clicked.connect(self.refresh)
        self.new_button.clicked.connect(self._on_new_purchase_order_clicked)

    def _populate_supplier_filter(self) -> None:
        from utils.searchable_combo_helper import populate_searchable_combo

        suppliers, _ = self._supplier_engine.search_suppliers(page=1, page_size=1000)
        self.supplier_filter_combo.addItem("All Suppliers", None)
        populate_searchable_combo(
            self.supplier_filter_combo,
            items=suppliers,
            display_attr="supplier_name",
            data_attr="supplier_id",
            keep_existing_items=True,
        )

    # -- data ---------------------------------------------------------------

    def refresh(self) -> None:
        status = self.status_filter_combo.currentText()
        status_filter = None if status == "All" else status

        orders, _total_count = self._engine.search_purchase_orders(
            search_text=self.search_input.text().strip() or None,
            supplier_id=self.supplier_filter_combo.currentData(),
            status=status_filter,
            include_deleted=False,
            page=1,
            page_size=500,
        )

        self.table.setRowCount(0)
        for order in orders:
            self._add_row(order)

    def _add_row(self, order) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        po_item = QTableWidgetItem(order.po_number)
        po_item.setData(Qt.UserRole, order.purchase_order_id)
        self.table.setItem(row, COL_PO_NUMBER, po_item)

        supplier_name = self._supplier_engine.get_supplier_name(order.supplier_id)
        self.table.setItem(row, COL_SUPPLIER, QTableWidgetItem(supplier_name))
        self.table.setItem(row, COL_ORDER_DATE, QTableWidgetItem(order.order_date_bs))
        self.table.setItem(row, COL_STATUS, QTableWidgetItem(order.status))

        whatsapp_button = QPushButton("📱")
        whatsapp_button.setToolTip("Send via WhatsApp")
        whatsapp_button.clicked.connect(
            lambda _, poid=order.purchase_order_id: self._on_whatsapp_clicked(poid)
        )
        self.table.setCellWidget(row, COL_WHATSAPP, whatsapp_button)

        email_button = QPushButton("✉")
        email_button.setToolTip("Send via Email")
        email_button.clicked.connect(
            lambda _, poid=order.purchase_order_id: self._on_email_clicked(poid)
        )
        self.table.setCellWidget(row, COL_EMAIL, email_button)

        view_button = QPushButton("View")
        view_button.clicked.connect(lambda _, poid=order.purchase_order_id: self._on_view_clicked(poid))
        self.table.setCellWidget(row, COL_VIEW, view_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setEnabled(order.status in ("Draft", "Sent"))
        cancel_button.clicked.connect(
            lambda _, poid=order.purchase_order_id: self._on_cancel_clicked(poid)
        )
        self.table.setCellWidget(row, COL_CANCEL, cancel_button)

    # -- actions --------------------------------------------------------------

    def _on_new_purchase_order_clicked(self) -> None:
        from screens.purchase_order_form_screen import PurchaseOrderFormScreen
        dialog = PurchaseOrderFormScreen(
            parent=self,
            engine=self._engine,
            supplier_engine=self._supplier_engine,
            item_engine=self._item_engine,
            current_user_id=self._current_user_id,
        )
        dialog.exec()
        self.refresh()

    def _on_whatsapp_clicked(self, purchase_order_id: int) -> None:
        send_purchase_order_via_whatsapp(
            parent=self,
            engine=self._engine,
            supplier_engine=self._supplier_engine,
            purchase_order_id=purchase_order_id,
            current_user_id=self._current_user_id,
        )
        self.refresh()

    def _on_email_clicked(self, purchase_order_id: int) -> None:
        send_purchase_order_via_email(
            parent=self,
            engine=self._engine,
            supplier_engine=self._supplier_engine,
            purchase_order_id=purchase_order_id,
            current_user_id=self._current_user_id,
        )
        self.refresh()

    def _on_view_clicked(self, purchase_order_id: int) -> None:
        """Read-only detail. Kept as a simple summary popup here rather than
        a dedicated dialog file, since the blueprint doesn't specify one —
        promote this to its own screens/purchase_order_view_dialog.py later
        if a richer detail view is needed."""
        try:
            order = self._engine.get_purchase_order(purchase_order_id)
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
            return

        supplier_name = self._supplier_engine.get_supplier_name(order.supplier_id)
        lines_text = "\n".join(
            f"  Item #{line.item_id}: qty={line.ordered_qty}, rate={line.rate}"
            for line in order.lines
        )
        QMessageBox.information(
            self,
            f"Purchase Order {order.po_number}",
            f"Supplier: {supplier_name}\n"
            f"Order Date: {order.order_date_bs}\n"
            f"Status: {order.status}\n"
            f"Sent Via: {order.sent_via or '-'}\n\n"
            f"Lines:\n{lines_text or '  (none)'}",
        )

    def _on_cancel_clicked(self, purchase_order_id: int) -> None:
        confirm = QMessageBox.question(
            self,
            "Cancel Purchase Order",
            "Are you sure you want to cancel this purchase order?",
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self._engine.cancel_purchase_order(purchase_order_id, self._current_user_id)
        except (RecordNotFoundError, ValidationError) as exc:
            QMessageBox.warning(self, "Cannot Cancel", str(exc))
            return
        except Exception:
            logger.exception("Failed to cancel purchase order %s", purchase_order_id)
            QMessageBox.critical(self, "Error", "Could not cancel the purchase order.")
            return

        self.refresh()