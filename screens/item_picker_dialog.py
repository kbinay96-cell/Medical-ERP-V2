# screens/item_picker_dialog.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from engines.item_engine import ItemEngine, ItemDTO


class ItemPickerDialog(QDialog):
    """Small search-and-pick dialog for choosing a single Item. Backed by
    ItemEngine.search_items() — the real, confirmed method (item_lookup_
    registry.py has no item-picker of its own; it only wires Manufacturer/
    Category/etc. master lookups)."""

    def __init__(self, parent, item_engine: ItemEngine):
        super().__init__(parent)
        self._item_engine = item_engine
        self.selected_item: ItemDTO | None = None

        self.setWindowTitle("Select Item")
        self.setMinimumSize(420, 480)

        root = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search items...")
        root.addWidget(self.search_input)

        self.list_widget = QListWidget()
        root.addWidget(self.list_widget)

        self.select_button = QPushButton("Select")
        root.addWidget(self.select_button)

        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._on_select_clicked())
        self.select_button.clicked.connect(self._on_select_clicked)

        self._refresh_results("")

    def _on_search_text_changed(self, text: str) -> None:
        self._refresh_results(text)

    def _refresh_results(self, search_text: str) -> None:
        self.list_widget.clear()
        items, _total = self._item_engine.search_items(
            search_text=search_text or None,
            status="Active",
            page=1,
            page_size=100,
        )
        for item in items:
            list_item = QListWidgetItem(f"{item.item_code} — {item.item_name}")
            list_item.setData(1000, item.item_id)
            self.list_widget.addItem(list_item)

    def _on_select_clicked(self) -> None:
        current = self.list_widget.currentItem()
        if current is None:
            return
        item_id = current.data(1000)
        self.selected_item = self._item_engine.get_item(item_id)
        self.accept()


def search_and_pick_item(parent, item_engine: ItemEngine) -> ItemDTO | None:
    """Convenience wrapper — opens ItemPickerDialog and returns the chosen
    ItemDTO, or None if the user cancelled."""
    dialog = ItemPickerDialog(parent, item_engine)
    if dialog.exec() == QDialog.Accepted:
        return dialog.selected_item
    return None