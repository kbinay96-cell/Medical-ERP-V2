# screens/stock_ledger_screen.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.searchable_combo_helper import populate_searchable_combo


class StockLedgerScreen(QWidget):
    """Read-only stock_ledger history for one item. Data via ItemEngine."""

    def __init__(self, parent, item_engine):
        super().__init__(parent)
        self._item_engine = item_engine
        self.setWindowTitle("Stock Ledger")
        self.setMinimumSize(1000, 520)

        root = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Item:"))
        self.item_combo = QComboBox()
        items, _ = self._item_engine.search_items(page=1, page_size=5000)
        populate_searchable_combo(
            self.item_combo,
            items=items,
            display_attr="item_name",
            data_attr="item_id",
            placeholder="Select item...",
        )
        row.addWidget(self.item_combo, stretch=1)
        self.refresh_button = QPushButton("Load Ledger")
        row.addWidget(self.refresh_button)
        root.addLayout(row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["When (BS)", "Type", "Qty change", "Balance after", "Batch ID", "Ref type", "Remarks"]
        )
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        root.addWidget(self.table)

        self.refresh_button.clicked.connect(self.refresh)
        self.item_combo.currentIndexChanged.connect(lambda _: self.refresh())

    def refresh(self) -> None:
        item_id = self.item_combo.currentData()
        self.table.setRowCount(0)
        if not item_id:
            return
        rows = self._item_engine.get_stock_ledger(item_id)
        for entry in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                str(entry.get("created_at_bs") or ""),
                str(entry.get("transaction_type") or ""),
                f"{float(entry.get('quantity_change') or 0):.3f}",
                f"{float(entry.get('balance_after') or 0):.3f}",
                str(entry.get("item_batch_id") or ""),
                str(entry.get("reference_type") or ""),
                str(entry.get("remarks") or ""),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
