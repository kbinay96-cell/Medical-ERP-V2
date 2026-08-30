# utils/searchable_combo_helper.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter


def populate_searchable_combo(
    combo: QComboBox,
    items: list,
    display_attr: str,
    data_attr: str,
    placeholder: str | None = None,
    keep_existing_items: bool = False,
) -> None:
    """Fills a QComboBox with (display_text, data) pairs from a list of
    objects, and makes it type-to-search via a QCompleter — a small,
    self-contained implementation kept deliberately independent of
    utils/combo_helpers.make_searchable(), since that function's real
    signature is not confirmed in this codebase (a previous guess at its
    keyword arguments caused a TypeError at runtime). Swap call sites
    back to the real combo_helpers.make_searchable() once its actual
    signature is confirmed, if consistency with the rest of the app is
    wanted.
    """
    if not keep_existing_items:
        combo.clear()
        if placeholder is not None:
            combo.addItem(placeholder, None)

    for item in items:
        text = getattr(item, display_attr)
        data = getattr(item, data_attr)
        combo.addItem(text, data)

    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)

    completer = QCompleter([combo.itemText(i) for i in range(combo.count())], combo)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    combo.setCompleter(completer)