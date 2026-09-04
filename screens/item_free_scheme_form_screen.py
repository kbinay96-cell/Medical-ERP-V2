"""
screens/item_free_scheme_form_screen.py

Item Free Scheme Add/Edit Dialog - Medical ERP V2

Same shape as screens/master_manage_screen.py's MasterManageDialog, but
item-scoped rather than a plain code/name master (needs a searchable Item
combo + two numeric fields instead of Code/Name), so it is its own small
dialog rather than being forced through MasterManageDialog/SimpleMasterEngine
-- mirrors how Manufacturer got its own dedicated screen for the same reason
(per engines/item_lookup_registry.py's documented reasoning).

Responsibilities ("No SQL. No business logic."): collect Item + Buy Qty +
Free Qty + Active + Remarks, call ItemFreeSchemeEngine.create_scheme() /
update_scheme(), and render whatever ValidationError/DuplicateRecordError/
RecordNotFoundError comes back -- same error-surfacing pattern as
MasterManageDialog._on_save_clicked().
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.sale_item_free_scheme_engine import SaleItemFreeSchemeEngine
from utils.searchable_combo_helper import populate_searchable_combo

logger = logging.getLogger(__name__)


class ItemFreeSchemeFormScreen(QDialog):
    """Add/Edit dialog for a single item's Free Scheme."""

    def __init__(
        self,
        parent,
        item_free_scheme_id: Optional[int],
        engine: SaleItemFreeSchemeEngine,
        item_engine,
        current_user_id: int,
    ) -> None:
        super().__init__(parent)
        if current_user_id is None:
            raise ValueError(
                "ItemFreeSchemeFormScreen requires current_user_id explicitly -- "
                "it does not look this up itself."
            )
        self._engine = engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id
        self._item_free_scheme_id = item_free_scheme_id
        self._is_editing = item_free_scheme_id is not None

        # One-time cache, same reasoning as PurchaseInvoiceFormScreen's
        # self._all_items -- avoids re-querying the DB per keystroke in the
        # searchable combo.
        self._all_items, _ = self._item_engine.search_items(page=1, page_size=5000)

        self.setWindowTitle("Edit Free Scheme" if self._is_editing else "New Free Scheme")
        self.resize(420, 340)

        self._build_ui()
        self._connect_signals()

        if self._is_editing:
            self._load_existing()

        self._update_preview_label()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(240)
        populate_searchable_combo(
            self.item_combo,
            items=self._all_items,
            display_attr="item_name",
            data_attr="item_id",
            placeholder="Select item...",
        )
        form.addRow("Item:", self.item_combo)

        self.buy_qty_input = QDoubleSpinBox()
        self.buy_qty_input.setRange(0.01, 100000)
        self.buy_qty_input.setDecimals(2)
        self.buy_qty_input.setValue(1)
        form.addRow("Buy Qty:", self.buy_qty_input)

        self.free_qty_input = QDoubleSpinBox()
        self.free_qty_input.setRange(0.01, 100000)
        self.free_qty_input.setDecimals(2)
        self.free_qty_input.setValue(1)
        form.addRow("Free Qty:", self.free_qty_input)

        self.preview_label = QLabel("Reads as: 1+1")
        self.preview_label.setStyleSheet("color: gray; font-style: italic;")
        form.addRow("", self.preview_label)

        self.is_active_checkbox = QCheckBox("Active")
        self.is_active_checkbox.setChecked(True)
        form.addRow("", self.is_active_checkbox)

        self.remarks_input = QPlainTextEdit()
        self.remarks_input.setMaximumHeight(60)
        form.addRow("Remarks:", self.remarks_input)

        root.addLayout(form)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #b00020;")
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        btn_row.addWidget(self.save_button)
        btn_row.addWidget(self.cancel_button)
        root.addLayout(btn_row)

    def _connect_signals(self) -> None:
        self.buy_qty_input.valueChanged.connect(self._update_preview_label)
        self.free_qty_input.valueChanged.connect(self._update_preview_label)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _update_preview_label(self) -> None:
        buy = self.buy_qty_input.value()
        free = self.free_qty_input.value()
        self.preview_label.setText(f"Reads as: {buy:g}+{free:g}")

    # ------------------------------------------------------------------ #
    def _load_existing(self) -> None:
        dto = self._engine.get_scheme(self._item_free_scheme_id)
        idx = self.item_combo.findData(dto.item_id)
        if idx >= 0:
            self.item_combo.setCurrentIndex(idx)
        # Item cannot be changed once a scheme exists -- one active scheme
        # per item is enforced by the DB's partial unique index; editing
        # the ratio is fine, re-pointing at a different item is not.
        self.item_combo.setEnabled(False)
        self.buy_qty_input.setValue(dto.scheme_qty)
        self.free_qty_input.setValue(dto.scheme_free)
        self.is_active_checkbox.setChecked(dto.is_active)
        self.remarks_input.setPlainText(dto.remarks or "")

    def _on_save_clicked(self) -> None:
        self.validation_label.setText("")

        item_id = self.item_combo.currentData()
        if item_id is None:
            self.validation_label.setText("Item is mandatory.")
            return

        payload = {
            "item_id": item_id,
            "scheme_qty": self.buy_qty_input.value(),
            "scheme_free": self.free_qty_input.value(),
            "is_active": self.is_active_checkbox.isChecked(),
            "remarks": self.remarks_input.toPlainText().strip(),
        }

        try:
            if self._is_editing:
                self._engine.update_scheme(self._item_free_scheme_id, payload, self._current_user_id)
            else:
                self._engine.create_scheme(payload, self._current_user_id)
        except ValidationError as exc:
            self.validation_label.setText("\n".join(exc.errors))
            return
        except DuplicateRecordError as exc:
            self.validation_label.setText(str(exc))
            return
        except RecordNotFoundError as exc:
            self.validation_label.setText(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error saving Item Free Scheme.")
            self.validation_label.setText(f"Unexpected error: {exc}")
            return

        self.accept()


__all__ = ["ItemFreeSchemeFormScreen"]