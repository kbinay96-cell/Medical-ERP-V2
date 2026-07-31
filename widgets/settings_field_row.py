"""
=========================================================
Medical ERP V2
Settings Field Row Widget
---------------------------------------------------------
Renders ONE setting (one row from `settings`) as an
editable control appropriate to its data_type, plus small
icon buttons for Apply (instant preview), Reset to default,
and History. Used on both the Group Detail page and the
Search Results page of the Settings Screen.

This widget never talks to the database or the Settings
Engine directly - it only emits signals; the Settings
Screen decides what to do with them. That keeps this file
pure UI, consistent with the rest of the app's screens-call-
engines-only convention.
=========================================================
"""

import json

from PySide6.QtCore import Qt, Signal, QDate, QTime, QSize
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QDateEdit, QTimeEdit,
    QPlainTextEdit, QPushButton, QFileDialog, QColorDialog, QFontDialog,
    QSizePolicy,
)

from utils.settings_ui_helpers import (
    humanize_setting_key, parse_enum_options, is_file_path_setting, is_image_path_setting,
)

ICON_DIR = "resources/icons"

try:
    from PySide6.QtPrintSupport import QPrinterInfo
    _PRINT_SUPPORT_AVAILABLE = True
except ImportError:
    _PRINT_SUPPORT_AVAILABLE = False


class SettingsFieldRow(QFrame):
    """
    Signals (all pass the setting_key so the screen knows which
    row they came from):
        apply_requested(key, new_value_str)
        reset_requested(key)
        history_requested(key)
    """

    apply_requested = Signal(str, str)
    reset_requested = Signal(str)
    history_requested = Signal(str)
    changed = Signal(str)

    def __init__(self, setting_row: dict, show_group_tag: bool = False, parent=None):
        super().__init__(parent)

        self.setting_row = setting_row
        self.setting_key = setting_row["setting_key"]
        self.data_type = setting_row["data_type"]
        self._original_value = setting_row.get("setting_value")
        self._input_widget = None

        self.setProperty("cssClass", "settingsRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._build_ui(show_group_tag)

    # -----------------------------------------------------
    # BUILD
    # -----------------------------------------------------

    def _build_ui(self, show_group_tag: bool):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 12, 12, 12)
        outer.setSpacing(14)

        # ---- left: label + description ----
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_label = QLabel(humanize_setting_key(self.setting_key))
        title_label.setProperty("cssClass", "rowTitle")
        title_row.addWidget(title_label)

        if show_group_tag:
            tag_label = QLabel(self.setting_row.get("setting_group", ""))
            tag_label.setProperty("cssClass", "tileBadge")
            title_row.addWidget(tag_label)

        if not self.setting_row.get("is_editable", True):
            lock_label = QLabel()
            lock_label.setPixmap(QIcon(f"{ICON_DIR}/lock.svg").pixmap(QSize(12, 12)))
            lock_label.setToolTip("This setting is not editable.")
            title_row.addWidget(lock_label)

        title_row.addStretch(1)
        text_col.addLayout(title_row)

        description = self.setting_row.get("description") or ""
        if description:
            desc_label = QLabel(description)
            desc_label.setProperty("cssClass", "rowDescription")
            desc_label.setWordWrap(True)
            text_col.addWidget(desc_label)

        outer.addLayout(text_col, 3)

        # ---- middle: the input control itself ----
        input_container = self._build_input_widget()
        self._connect_change_signal()
        outer.addWidget(input_container, 2)

        # ---- right: action icon buttons ----
        actions_row = QHBoxLayout()
        actions_row.setSpacing(4)

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setToolTip("Preview this value instantly (not saved to the database yet).")
        self.btn_apply.setProperty("cssClass", "rowIconBtn")
        self.btn_apply.clicked.connect(self._handle_apply_clicked)
        actions_row.addWidget(self.btn_apply)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setToolTip("Reset to default value")
        self.btn_reset.setProperty("cssClass", "rowIconBtn")
        self.btn_reset.clicked.connect(lambda: self.reset_requested.emit(self.setting_key))
        actions_row.addWidget(self.btn_reset)

        self.btn_history = QPushButton()
        self.btn_history.setIcon(QIcon(f"{ICON_DIR}/clock.svg"))
        self.btn_history.setToolTip("View change history")
        self.btn_history.setProperty("cssClass", "rowIconBtn")
        self.btn_history.clicked.connect(lambda: self.history_requested.emit(self.setting_key))
        actions_row.addWidget(self.btn_history)

        outer.addLayout(actions_row, 0)

        if not self.setting_row.get("is_editable", True):
            self._set_input_enabled(False)

    def _set_input_enabled(self, enabled: bool):
        if self._input_widget is not None:
            self._input_widget.setEnabled(enabled)
        self.btn_apply.setEnabled(enabled)
        self.btn_reset.setEnabled(enabled)

    def _connect_change_signal(self):
        """
        Hooks whichever control type _build_input_widget created
        so any edit re-emits this row's `changed` signal - this is
        how the Settings Screen knows to enable "Save Changes"
        without waiting for the user to press Apply first.
        """
        widget = self._input_widget
        emit = lambda *_: self.changed.emit(self.setting_key)

        if isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(emit)
        elif isinstance(widget, QCheckBox):
            widget.stateChanged.connect(emit)
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(emit)
        elif isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(emit)
        elif isinstance(widget, QDateEdit):
            widget.dateChanged.connect(emit)
        elif isinstance(widget, QTimeEdit):
            widget.timeChanged.connect(emit)
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(emit)
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(emit)

    def _build_input_widget(self):
        value = self.setting_row.get("setting_value") or ""
        description = self.setting_row.get("description") or ""

        enum_options = parse_enum_options(description) if self.data_type == "string" else None

        if enum_options:
            combo = QComboBox()
            combo.addItems(enum_options)
            if value in enum_options:
                combo.setCurrentText(value)
            elif value:
                combo.addItem(value)
                combo.setCurrentText(value)
            self._input_widget = combo
            return combo

        if self.data_type == "boolean":
            check = QCheckBox("Enabled")
            check.setChecked(str(value).strip().lower() == "true")
            self._input_widget = check
            return check

        if self.data_type == "integer":
            spin = QSpinBox()
            spin.setRange(-1_000_000_000, 1_000_000_000)
            try:
                spin.setValue(int(value))
            except (TypeError, ValueError):
                spin.setValue(0)
            self._input_widget = spin
            return spin

        if self.data_type == "decimal":
            dspin = QDoubleSpinBox()
            dspin.setRange(-1_000_000_000, 1_000_000_000)
            dspin.setDecimals(2)
            try:
                dspin.setValue(float(value))
            except (TypeError, ValueError):
                dspin.setValue(0.0)
            self._input_widget = dspin
            return dspin

        if self.data_type == "date":
            date_edit = QDateEdit()
            date_edit.setCalendarPopup(True)
            qd = QDate.fromString(value, "yyyy-MM-dd")
            date_edit.setDate(qd if qd.isValid() else QDate.currentDate())
            self._input_widget = date_edit
            return date_edit

        if self.data_type == "time":
            time_edit = QTimeEdit()
            qt_val = QTime.fromString(value, "HH:mm")
            time_edit.setTime(qt_val if qt_val.isValid() else QTime(0, 0))
            self._input_widget = time_edit
            return time_edit

        if self.data_type == "json":
            text_edit = QPlainTextEdit(value)
            text_edit.setMaximumHeight(70)
            text_edit.setPlaceholderText("{ }")
            self._input_widget = text_edit
            return text_edit

        if self.data_type == "color":
            return self._build_color_picker(value)

        if self.data_type == "path":
            return self._build_path_picker(value, description)

        if self.data_type == "font":
            return self._build_font_picker(value)

        if self.data_type == "printer":
            return self._build_printer_picker(value)

        # string (no enum) and any unrecognised type fall back to
        # a plain text box rather than blocking the row entirely.
        line = QLineEdit(str(value))
        self._input_widget = line
        return line

    def _build_color_picker(self, value: str):
        container = QFrame()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)

        line = QLineEdit(value)
        row.addWidget(line)

        swatch_btn = QPushButton()
        swatch_btn.setFixedSize(28, 28)
        swatch_btn.setToolTip("Pick a colour")

        def _refresh_swatch():
            colour = QColor(line.text()) if QColor.isValidColorName(line.text()) else QColor("#7C4DFF")
            swatch_btn.setStyleSheet(f"background-color: {colour.name()}; border-radius: 6px;")

        def _open_picker():
            initial = QColor(line.text()) if QColor.isValidColorName(line.text()) else QColor("#7C4DFF")
            chosen = QColorDialog.getColor(initial, self, "Pick a colour")
            if chosen.isValid():
                line.setText(chosen.name().upper())
                _refresh_swatch()

        swatch_btn.clicked.connect(_open_picker)
        _refresh_swatch()
        row.addWidget(swatch_btn)

        self._input_widget = line
        return container

    def _build_path_picker(self, value: str, description: str):
        container = QFrame()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)

        line = QLineEdit(value)
        row.addWidget(line)

        browse_btn = QPushButton("Browse\u2026")

        def _open_browser():
            if is_file_path_setting(self.setting_key, description):
                if is_image_path_setting(self.setting_key, description):
                    chosen, _ = QFileDialog.getOpenFileName(
                        self, "Choose file", line.text(), "Images (*.png *.jpg *.jpeg *.bmp *.svg)"
                    )
                else:
                    chosen, _ = QFileDialog.getOpenFileName(self, "Choose file", line.text())
            else:
                chosen = QFileDialog.getExistingDirectory(self, "Choose folder", line.text())

            if chosen:
                line.setText(chosen)

        browse_btn.clicked.connect(_open_browser)
        row.addWidget(browse_btn)

        self._input_widget = line
        return container

    def _build_font_picker(self, value: str):
        container = QFrame()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)

        line = QLineEdit(value)
        row.addWidget(line)

        choose_btn = QPushButton("Choose\u2026")

        def _open_font_dialog():
            ok, font = QFontDialog.getFont(self)
            if ok:
                line.setText(font.family())

        choose_btn.clicked.connect(_open_font_dialog)
        row.addWidget(choose_btn)

        self._input_widget = line
        return container

    def _build_printer_picker(self, value: str):
        combo = QComboBox()
        combo.setEditable(True)

        printer_names = []
        if _PRINT_SUPPORT_AVAILABLE:
            try:
                printer_names = [p.printerName() for p in QPrinterInfo.availablePrinters()]
            except Exception:
                printer_names = []

        combo.addItems(printer_names)
        combo.setCurrentText(value)
        self._input_widget = combo
        return combo

    # -----------------------------------------------------
    # VALUE EXTRACTION / DIRTY STATE
    # -----------------------------------------------------

    def current_value_str(self) -> str | None:
        """
        Serializes the input control's current value back into
        the string form the database/validator expects.
        Returns None (and shows no error itself) only for
        the JSON case when the text isn't valid JSON - the
        caller decides how to surface that.
        """
        widget = self._input_widget

        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QCheckBox):
            return "true" if widget.isChecked() else "false"
        if isinstance(widget, QSpinBox):
            return str(widget.value())
        if isinstance(widget, QDoubleSpinBox):
            return str(widget.value())
        if isinstance(widget, QDateEdit):
            return widget.date().toString("yyyy-MM-dd")
        if isinstance(widget, QTimeEdit):
            return widget.time().toString("HH:mm")
        if isinstance(widget, QPlainTextEdit):
            text = widget.toPlainText().strip()
            if self.data_type == "json" and text:
                try:
                    json.loads(text)
                except json.JSONDecodeError:
                    return None
            return text
        if isinstance(widget, QLineEdit):
            return widget.text()

        return None

    def is_dirty(self) -> bool:
        current = self.current_value_str()
        return current is not None and current != (self._original_value or "")

    def mark_saved(self, new_value: str):
        """Called after a successful Apply/Save/Reset so dirty-tracking resets."""
        self._original_value = new_value
        self.setting_row["setting_value"] = new_value

    def _handle_apply_clicked(self):
        value = self.current_value_str()
        if value is None:
            self.btn_apply.setToolTip("Invalid JSON - fix the value before applying.")
            return
        self.apply_requested.emit(self.setting_key, value)
