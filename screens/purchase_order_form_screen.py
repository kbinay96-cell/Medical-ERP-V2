# screens/purchase_order_form_screen.py
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engines.exceptions import ValidationError
from engines.purchase_order_engine import PurchaseOrderEngine
from utils.searchable_combo_helper import populate_searchable_combo

logger = logging.getLogger(__name__)

# table columns
COL_CHECK = 0
COL_ITEM_NAME = 1
COL_CURRENT_STOCK = 2
COL_MIN_STOCK = 3
COL_SUGGESTED_QTY = 4
COL_RATE = 5
COL_WARNING = 6
COL_REMOVE = 7
COLUMN_COUNT = 8


class PurchaseOrderFormScreen(QDialog):
    """The starting point of the Purchase flow. Opens showing every
    low-stock item (live query) as a checked-by-default row; user can
    uncheck items, edit suggested qty, or search-and-add any other item
    manually. One PO = one supplier.

    No SQL, no business logic here — every save goes through
    PurchaseOrderEngine.create_purchase_order().
    """

    def __init__(
        self,
        parent,
        engine: PurchaseOrderEngine,
        supplier_engine,
        item_engine,
        current_user_id: int,
    ):
        super().__init__(parent)
        self._engine = engine
        self._supplier_engine = supplier_engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id
        self._saved_purchase_order_id: int | None = None

        self.setWindowTitle("New Purchase Order")
        self.setMinimumSize(900, 600)

        self._build_ui()
        self._connect_signals()
        self._populate_supplier_combo()
        self._load_low_stock_suggestions()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Supplier:"))
        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumWidth(280)
        header_row.addWidget(self.supplier_combo)
        header_row.addStretch()

        self.add_item_button = QPushButton("+ Add Item")
        header_row.addWidget(self.add_item_button)
        root.addLayout(header_row)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(
            ["", "Item", "Current Stock", "Min Stock", "Suggested Qty", "Rate", "", ""]
        )
        self.table.horizontalHeader().setSectionResizeMode(COL_ITEM_NAME, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table)

        footer_row = QHBoxLayout()
        footer_row.addStretch()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Close")
        footer_row.addWidget(self.save_button)
        footer_row.addWidget(self.cancel_button)
        root.addLayout(footer_row)

        # post-save "send now" row — hidden until a PO is actually saved
        self.send_row = QWidget()
        send_layout = QHBoxLayout(self.send_row)
        send_layout.addWidget(QLabel("Purchase order saved. Send it now:"))
        self.whatsapp_send_button = QPushButton("📱 Send via WhatsApp")
        self.email_send_button = QPushButton("✉ Send via Email")
        send_layout.addWidget(self.whatsapp_send_button)
        send_layout.addWidget(self.email_send_button)
        send_layout.addStretch()
        self.send_row.setVisible(False)
        root.addWidget(self.send_row)

    def _connect_signals(self) -> None:
        self.add_item_button.clicked.connect(self._on_add_item_manually_clicked)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.whatsapp_send_button.clicked.connect(self._on_whatsapp_send_clicked)
        self.email_send_button.clicked.connect(self._on_email_send_clicked)

    def _populate_supplier_combo(self) -> None:
        suppliers, _ = self._supplier_engine.search_suppliers(page=1, page_size=1000)
        populate_searchable_combo(
            self.supplier_combo,
            items=suppliers,
            display_attr="supplier_name",
            data_attr="supplier_id",
        )

    # -- data loading ---------------------------------------------------------

    def _load_low_stock_suggestions(self) -> None:
        suggestions = self._engine.get_low_stock_suggestions()
        self.table.setRowCount(0)
        for suggestion in suggestions:
            self._add_row(
                item_id=suggestion.item_id,
                item_name=suggestion.item_name,
                current_stock=suggestion.current_stock,
                minimum_stock=suggestion.minimum_stock,
                suggested_qty=suggestion.suggested_qty,
                is_auto_suggested=True,
                already_ordered_elsewhere=suggestion.already_ordered_elsewhere,
            )

    def _add_row(
        self,
        item_id: int,
        item_name: str,
        current_stock: float | None,
        minimum_stock: float | None,
        suggested_qty: float,
        is_auto_suggested: bool,
        already_ordered_elsewhere: list[dict] | None = None,
    ) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        check_box = QCheckBox()
        check_box.setChecked(True)
        check_box.toggled.connect(lambda checked, r=row: self._on_row_check_toggled(r))
        check_cell = QWidget()
        check_layout = QHBoxLayout(check_cell)
        check_layout.addWidget(check_box)
        check_layout.setAlignment(Qt.AlignCenter)
        check_layout.setContentsMargins(0, 0, 0, 0)
        self.table.setCellWidget(row, COL_CHECK, check_cell)

        name_item = QTableWidgetItem(item_name)
        name_item.setData(Qt.UserRole, item_id)
        name_item.setData(Qt.UserRole + 1, is_auto_suggested)
        self.table.setItem(row, COL_ITEM_NAME, name_item)

        self.table.setItem(
            row, COL_CURRENT_STOCK,
            QTableWidgetItem("" if current_stock is None else str(current_stock)),
        )
        self.table.setItem(
            row, COL_MIN_STOCK,
            QTableWidgetItem("" if minimum_stock is None else str(minimum_stock)),
        )

        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0, 10_000_000)
        qty_spin.setDecimals(2)
        qty_spin.setValue(suggested_qty)
        self.table.setCellWidget(row, COL_SUGGESTED_QTY, qty_spin)

        rate_spin = QDoubleSpinBox()
        rate_spin.setRange(0, 10_000_000)
        rate_spin.setDecimals(2)
        self.table.setCellWidget(row, COL_RATE, rate_spin)

        warning_text = ""
        if already_ordered_elsewhere:
            parts = [
                f"{o.get('po_number')} ({o.get('status')}) x{o.get('ordered_qty')}"
                for o in already_ordered_elsewhere
            ]
            warning_text = "Already ordered: " + "; ".join(parts)
        warning_item = QTableWidgetItem("⚠" if warning_text else "")
        warning_item.setToolTip(warning_text)
        self.table.setItem(row, COL_WARNING, warning_item)

        if is_auto_suggested:
            self.table.setItem(row, COL_REMOVE, QTableWidgetItem(""))
        else:
            remove_button = QPushButton("✕")
            remove_button.setToolTip("Remove this manually-added item")
            remove_button.clicked.connect(lambda _, r=row: self._on_remove_row_clicked(r))
            self.table.setCellWidget(row, COL_REMOVE, remove_button)

    # -- row interactions -------------------------------------------------

    def _on_add_item_manually_clicked(self) -> None:
        from screens.item_picker_dialog import search_and_pick_item

        item = search_and_pick_item(self, self._item_engine)
        if item is None:
            return

        existing_item_ids = {
            self.table.item(r, COL_ITEM_NAME).data(Qt.UserRole)
            for r in range(self.table.rowCount())
        }
        if item.item_id in existing_item_ids:
            QMessageBox.information(self, "Already Added", f"{item.item_name} is already in this order.")
            return

        self._add_row(
            item_id=item.item_id,
            item_name=item.item_name,
            current_stock=None,
            minimum_stock=None,
            suggested_qty=0.0,
            is_auto_suggested=False,
        )

    def _on_row_check_toggled(self, row_index: int) -> None:
        check_cell = self.table.cellWidget(row_index, COL_CHECK)
        checked = check_cell.findChild(QCheckBox).isChecked()
        for col in (COL_SUGGESTED_QTY, COL_RATE):
            widget = self.table.cellWidget(row_index, col)
            if widget is not None:
                widget.setEnabled(checked)

    def _on_remove_row_clicked(self, row_index: int) -> None:
        self.table.removeRow(row_index)

    # -- save ---------------------------------------------------------------

    def _collect_form_values(self) -> dict:
        supplier_id = self.supplier_combo.currentData()

        lines = []
        for row in range(self.table.rowCount()):
            check_cell = self.table.cellWidget(row, COL_CHECK)
            checked = check_cell.findChild(QCheckBox).isChecked()
            if not checked:
                continue

            name_item = self.table.item(row, COL_ITEM_NAME)
            item_id = name_item.data(Qt.UserRole)
            is_auto_suggested = bool(name_item.data(Qt.UserRole + 1))

            qty_spin = self.table.cellWidget(row, COL_SUGGESTED_QTY)
            rate_spin = self.table.cellWidget(row, COL_RATE)

            stock_text = self.table.item(row, COL_CURRENT_STOCK).text()
            min_text = self.table.item(row, COL_MIN_STOCK).text()

            lines.append(
                {
                    "item_id": item_id,
                    "ordered_qty": qty_spin.value(),
                    "rate": rate_spin.value(),
                    "is_auto_suggested": is_auto_suggested,
                    "stock_at_order_time": float(stock_text) if stock_text else None,
                    "minimum_stock_at_order_time": float(min_text) if min_text else None,
                }
            )

        from engines.date_engine import today_bs_string  # lazy import, mirrors other screens

        return {
            "supplier_id": supplier_id,
            "order_date_bs": today_bs_string(),
            "lines": lines,
        }

    def _on_save_clicked(self) -> None:
        payload = self._collect_form_values()

        if not payload["supplier_id"]:
            QMessageBox.warning(self, "Missing Supplier", "Please select a supplier.")
            return
        if not payload["lines"]:
            QMessageBox.warning(self, "No Items", "Please check at least one item to order.")
            return

        try:
            order_dto = self._engine.create_purchase_order(payload, self._current_user_id)
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot Save", str(exc))
            return
        except Exception:
            logger.exception("Failed to create purchase order")
            QMessageBox.critical(self, "Error", "Could not save the purchase order. Please try again.")
            return

        self._saved_purchase_order_id = order_dto.purchase_order_id
        self.save_button.setEnabled(False)
        self.supplier_combo.setEnabled(False)
        self.table.setEnabled(False)
        self.add_item_button.setEnabled(False)
        self.send_row.setVisible(True)

        QMessageBox.information(
            self, "Saved", f"Purchase order {order_dto.po_number} saved successfully."
        )

    # -- send now (reuses the same handlers as the List screen) -------------

    def _on_whatsapp_send_clicked(self) -> None:
        from screens.purchase_order_list_screen import send_purchase_order_via_whatsapp

        if self._saved_purchase_order_id is None:
            return
        send_purchase_order_via_whatsapp(
            parent=self,
            engine=self._engine,
            supplier_engine=self._supplier_engine,
            purchase_order_id=self._saved_purchase_order_id,
            current_user_id=self._current_user_id,
        )

    def _on_email_send_clicked(self) -> None:
        from screens.purchase_order_list_screen import send_purchase_order_via_email

        if self._saved_purchase_order_id is None:
            return
        send_purchase_order_via_email(
            parent=self,
            engine=self._engine,
            supplier_engine=self._supplier_engine,
            purchase_order_id=self._saved_purchase_order_id,
            current_user_id=self._current_user_id,
        )