# screens/stock_master_screen.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class StockMasterScreen(QWidget):
    """Current batch-level stock (item_batch). Read-only inventory master."""

    def __init__(self, parent, item_engine):
        super().__init__(parent)
        self._item_engine = item_engine
        self.setWindowTitle("Stock Master")
        self.setMinimumSize(1100, 560)

        root = QVBoxLayout(self)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search item:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Item name or code...")
        filters.addWidget(self.search_input)
        self.search_button = QPushButton("Search")
        filters.addWidget(self.search_button)
        root.addLayout(filters)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Item Code", "Item Name", "Batch", "Expiry", "Qty", "Purchase Rate", "Stock Value"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        root.addWidget(self.table)

        self.search_button.clicked.connect(self.refresh)
        self.search_input.returnPressed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        items, _ = self._item_engine.search_items(
            search_text=self.search_input.text().strip() or None,
            page=1,
            page_size=500,
        )
        self.table.setRowCount(0)
        for item in items:
            batches = self._item_engine.get_batches(item.item_id)
            if not batches:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._set_row(row, item.item_code, item.item_name, "—", "—", 0, 0, 0)
                continue
            for batch in batches:
                qty = float(batch.batch_qty)
                rate = float(batch.batch_purchase_rate)
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._set_row(
                    row,
                    item.item_code,
                    item.item_name,
                    batch.batch_no,
                    batch.expiry_display,
                    qty,
                    rate,
                    qty * rate,
                )

    def _set_row(self, row, code, name, batch_no, expiry, qty, rate, value) -> None:
        values = [
            str(code),
            str(name),
            str(batch_no),
            str(expiry),
            f"{float(qty):.3f}",
            f"{float(rate):.2f}",
            f"{float(value):.2f}",
        ]
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))
