"""
utils/combo_helpers.py

Searchable Combo Box Helper - Medical ERP V2

Separate from utils/item_form_helpers.py on purpose: that file is
deliberately zero-PySide6 so it stays unit-testable without Qt. Anything
that touches a QComboBox/QCompleter directly lives here instead.

Use `make_searchable(combo)` on any lookup dropdown that can grow to a long
list (Category, Sub Category, Manufacturer, Generic, ...). Skip it for
short, fixed-size dropdowns (Item Group ~7 values, Status Active/Inactive,
Tax Mode) -- a search box on a 2-7 item list is noise, not a feature.

How it works:
    - combo.setEditable(True) turns the QComboBox into a type-and-filter
      field while keeping it a strict picker (see NoInsert below) --
      the user cannot free-type a value that isn't in the list.
    - A QCompleter in PopupCompletion mode with MatchContains shows every
      option whose name CONTAINS the typed text anywhere (not just at the
      start) -- e.g. typing "phar" matches "Sun Pharma" and "GSK Pharma"
      both, since neither starts with "phar".
    - setInsertPolicy(NoInsert) + a currentIndexChanged-based re-sync
      guarantees the combo's actual value (and therefore .currentData())
      stays one of the real registered items -- typing something that
      matches nothing and clicking away reverts to the last valid
      selection, it never silently creates a blank/invalid entry.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter, QFormLayout, QHBoxLayout, QPushButton, QWidget


def make_searchable(combo: QComboBox) -> None:
    """
    Turns an already-populated QComboBox into a type-ahead filterable
    dropdown. Call this AFTER the combo has been filled with its items
    (addItem(...) calls) -- it reads the combo's own model for the
    completer, so it does not need to know the lookup engine or the
    data source at all.
    """
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    # Editable combos default to inheriting the line edit's own completer
    # config; we replace it with one that filters by substring instead of
    # prefix, since "type-ahead narrows the list" is the actual ask here.
    completer = QCompleter(combo.model(), combo)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    combo.setCompleter(completer)

    # If the user types something that matches nothing and moves focus
    # away, snap back to whatever was last actually selected rather than
    # leaving the line edit showing free text that doesn't correspond to
    # any real row (currentData() would otherwise return the last valid
    # id while the visible text lies about it).
    def _revert_if_no_match() -> None:
        text = combo.currentText()
        index = combo.findText(text, Qt.MatchFixedString | Qt.MatchCaseSensitive)
        if index == -1:
            # No exact match typed -- restore the previously selected item's
            # display text so the visible text and .currentData() agree again.
            current_index = combo.currentIndex()
            if current_index >= 0:
                combo.setCurrentIndex(current_index)

    combo.lineEdit().editingFinished.connect(_revert_if_no_match)


def make_searchable_many(*combos: QComboBox) -> None:
    """Convenience: apply make_searchable to several combos in one call."""
    for combo in combos:
        make_searchable(combo)


def attach_manage_button(form_layout: QFormLayout, combo: QComboBox, on_click: Callable[[], None]) -> None:
    """
    Inserts a small "Manage..." button next to an existing combo box inside
    a QFormLayout, WITHOUT editing the hand-written ui_*.py file's row
    structure -- it finds the combo's existing row, lifts it out, and
    re-inserts a [combo | button] container in its place.

    Call this once, after setupUi() and after the combo has already been
    populated -- it only rearranges layout, it never touches the combo's
    items/data. `on_click` is the Screen's own handler that opens
    MasterManageDialog and calls the combo's refresh function afterward
    (see screens/item_form_screen.py for the concrete wiring).
    """
    row, _role = form_layout.getWidgetPosition(combo)
    if row == -1:
        raise ValueError("Combo box not found in the given QFormLayout -- check it was added via addRow().")

    label_item = form_layout.itemAt(row, QFormLayout.LabelRole)
    label_widget = label_item.widget() if label_item is not None else None

    form_layout.takeRow(row)

    container = QWidget(combo.parentWidget())
    row_layout = QHBoxLayout(container)
    row_layout.setContentsMargins(0, 0, 0, 0)
    combo.setParent(container)
    row_layout.addWidget(combo, 1)
    btn_manage = QPushButton("Manage...", container)
    btn_manage.setToolTip("Add, edit, or remove entries in this list.")
    btn_manage.clicked.connect(on_click)
    row_layout.addWidget(btn_manage)

    if label_widget is not None:
        form_layout.insertRow(row, label_widget, container)
    else:
        form_layout.insertRow(row, container)


__all__ = ["make_searchable", "make_searchable_many", "attach_manage_button"]
