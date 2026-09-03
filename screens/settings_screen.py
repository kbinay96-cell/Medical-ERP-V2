"""
=========================================================
Medical ERP V2
Settings Screen
---------------------------------------------------------
Screen layer for the Settings module. Builds one editable
row per setting at runtime (based on each setting's
data_type), and wires Save / Apply / Restore Default /
Import / Export / Close / Search against the Settings
Engine — the ONLY sanctioned read/write path for settings.

=========================================================
ASSUMED INTERFACES — VERIFY AGAINST YOUR REAL SOURCE FILES
=========================================================
This screen was written without access to the real source
of settings_engine.py / session_manager.py / message.py
(built in separate chat sessions). The exact interfaces
below are ASSUMED. If your real files differ, this file
will raise AttributeError/TypeError at the matching call
site — tell Claude the real signature and it will be
patched in one edit, same as the SupplierEngine/date_engine
mismatch that was found and fixed earlier in this project.

engines/settings_engine.py — CONFIRMED against the real file.
It is a function-based module (like date_engine.py), not a
class. Called as settings_engine.<function>(...) directly:

    load_all_settings() -> None
    refresh_cache() -> None
    get_setting(key: str, default=None)
    get_settings_grouped() -> dict[str, list[dict]]
        Keys = setting_group. Each dict has:
        setting_key, setting_value, setting_group, data_type,
        default_value, description, is_editable, display_order.
    search_settings(search_text: str) -> list[dict]
    save_setting(key: str, new_value: str, updated_by: str,
                 reason: str = "") -> tuple[bool, str]
        Does NOT raise on invalid input — returns (success, message).
    apply_setting_temporarily(key: str, new_value: str) -> tuple[bool, str]
    reset_setting_to_default(key: str, updated_by: str) -> tuple[bool, str]
    requires_restart(setting_group: str) -> bool
        Per GROUP, not per individual setting key.
    export_settings(file_path: str) -> tuple[bool, str]
        Always exports everything — no per-group filtering.
    import_settings(file_path: str, updated_by: str) -> tuple[bool, str]
    get_setting_history(key: str) -> list[dict]
    get_recent_changes(limit: int = 10) -> list[dict]

session_manager (engines/session_manager.py):
    get_current_session() -> dict | None   (CONFIRMED)
    (Dict key names for username/role are still being verified —
    see _get_current_username()/_is_admin_user() below.)

utils/message.py (CONFIRMED against the real file — no parent argument):
    show_info(message: str, title: str = APP_TITLE) -> None
    show_success(message: str, title: str = APP_TITLE) -> None
    show_warning(message: str, title: str = APP_TITLE) -> None
    show_error(message: str, title: str = APP_TITLE) -> None
    confirm(message: str, title: str = APP_TITLE) -> bool
=========================================================
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpacerItem,
    QSpinBox,
    QSizePolicy,
    QTimeEdit,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engines import settings_engine
from engines import theme_engine
from utils import language_manager
from ui.ui_settings import Ui_SettingsScreen
from utils import message
from utils.app_logger import get_logger

logger = get_logger()

# Setting keys that need screen-level side effects beyond a normal
# save/apply (they affect the running application immediately).
THEME_SETTING_KEY = "general.theme"
UI_CONTROL_HEIGHT_KEY = "ui.control_height"
UI_FONT_SIZE_KEY = "ui.font_size"
UI_FONT_FAMILY_KEY = "ui.font_family"

# Setting keys with a fixed set of valid choices, rendered as a
# QComboBox regardless of their declared data_type.
FIXED_CHOICE_SETTINGS: dict[str, list[str]] = {
    "general.business_type": [
        "Retail", "Wholesale",
    ],
    "date.primary_calendar": ["BS", "AD"],
    "date.week_start_day": [
        "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
    ],
    "print.default_paper_size": ["A4", "A5", "Letter", "Thermal58", "Thermal80"],
    UI_FONT_FAMILY_KEY: [
        "Segoe UI", "Calibri", "Tahoma", "Verdana", "Arial",
        "Trebuchet MS", "Century Gothic", "Open Sans", "Noto Sans", "Roboto",
    ],
}

# Settings that get a dropdown of common values but still allow a
# custom typed value (editable QComboBox).
EDITABLE_CHOICE_SETTINGS: dict[str, list[str]] = {
    "general.currency_symbol": ["Rs.", "$", "\u20ac", "\u00a3", "\u00a5"],
}

# data_type values that map to a live-editable value on a single line,
# vs. those needing dedicated Qt widgets. Anything not listed here
# falls back to a plain QLineEdit.
_NUMERIC_INTEGER = "integer"
_NUMERIC_DECIMAL = "decimal"
_BOOLEAN = "boolean"
_DATE = "date"
_TIME = "time"
_JSON = "json"
_PATH = "path"


class SettingsScreen(QMainWindow, Ui_SettingsScreen):
    """
    Settings screen: left category tree, right dynamic settings
    panel, search, and Save/Apply/Restore/Import/Export/Close.
    """

    def __init__(
        self,
        current_username: str,
        is_admin: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        current_username / is_admin must be supplied by the caller
        (Dashboard) — the session dict only carries userid/companyid/
        financialyear/machinename, not username or role, so this
        screen cannot resolve them on its own. Dashboard already has
        both values (it receives them to build its own menu/permissions),
        so it should pass them straight through, e.g.:
            SettingsScreen(current_username=..., is_admin=..., parent=self)
        """
        super().__init__(parent)
        self.setupUi(self)

        self._current_username: str = current_username
        self._is_admin: bool = is_admin

        # group_name -> list[setting dict]
        self._settings_by_group: dict[str, list[dict[str, Any]]] = {}
        # setting_key -> (widget, data_type, original_value, setting_group)
        self._row_widgets: dict[str, tuple[QWidget, str, str, str]] = {}
        # setting_key -> staged (not-yet-saved) string value
        self._pending_changes: dict[str, str] = {}

        self._current_group: Optional[str] = None
        self._is_search_view: bool = False

        self._connect_signals()
        self._apply_permission_lock()
        self._load_categories()

    # -----------------------------------------------------------
    # Setup / permissions
    # -----------------------------------------------------------
    def _connect_signals(self) -> None:
        self.treeCategories.currentItemChanged.connect(self._on_category_selected)
        self.txtSearch.textChanged.connect(self._on_search_text_changed)
        self.btnRestoreDefault.clicked.connect(self._on_btn_restore_default_clicked)
        self.btnApply.clicked.connect(self._on_btn_apply_clicked)
        self.btnSave.clicked.connect(self._on_btn_save_clicked)
        self.btnImport.clicked.connect(self._on_btn_import_clicked)
        self.btnExport.clicked.connect(self._on_btn_export_clicked)
        self.btnClose.clicked.connect(self._on_btn_close_clicked)

    def _apply_permission_lock(self) -> None:
        """Import/Export are Admin-only per the Settings blueprint."""
        self.btnImport.setEnabled(self._is_admin)
        self.btnExport.setEnabled(self._is_admin)
        if not self._is_admin:
            self.btnImport.setToolTip("Only an Administrator can import settings.")
            self.btnExport.setToolTip("Only an Administrator can export settings.")

    # -----------------------------------------------------------
    # Category tree
    # -----------------------------------------------------------
    def _load_categories(self) -> None:
        try:
            self._settings_by_group = settings_engine.get_settings_grouped()
        except Exception as e:  # noqa: BLE001
            logger.error(f"SettingsScreen: get_settings_grouped() failed: {e}")
            message.show_error(
                "Could not load settings from the database. Please try again.",
                "Settings",
            )
            self._settings_by_group = {}

        self.treeCategories.clear()
        for group_name in self._settings_by_group.keys():
            item = QTreeWidgetItem([group_name])
            self.treeCategories.addTopLevelItem(item)

        if self.treeCategories.topLevelItemCount() > 0:
            self.treeCategories.setCurrentItem(self.treeCategories.topLevelItem(0))

    def _on_category_selected(
        self, current: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]
    ) -> None:
        if current is None:
            return
        if not self._confirm_discard_if_unsaved():
            # Re-select the previous item since the user cancelled navigation.
            self.treeCategories.blockSignals(True)
            if previous is not None:
                self.treeCategories.setCurrentItem(previous)
            self.treeCategories.blockSignals(False)
            return

        self._is_search_view = False
        self.txtSearch.blockSignals(True)
        self.txtSearch.clear()
        self.txtSearch.blockSignals(False)

        group_name = current.text(0)
        self._render_settings(group_name, self._settings_by_group.get(group_name, []))

    # -----------------------------------------------------------
    # Search
    # -----------------------------------------------------------
    def _on_search_text_changed(self, text: str) -> None:
        text = text.strip()
        if not text:
            self._is_search_view = False
            current_item = self.treeCategories.currentItem()
            if current_item is not None:
                group_name = current_item.text(0)
                self._render_settings(
                    group_name, self._settings_by_group.get(group_name, [])
                )
            return

        try:
            results = settings_engine.search_settings(text)
        except Exception as e:  # noqa: BLE001
            logger.error(f"SettingsScreen: search_settings() failed: {e}")
            results = []

        self._is_search_view = True
        self.treeCategories.blockSignals(True)
        self.treeCategories.clearSelection()
        self.treeCategories.blockSignals(False)
        self._render_settings(f"Search results for \"{text}\"", results)

    # -----------------------------------------------------------
    # Dynamic row rendering
    # -----------------------------------------------------------
    def _render_settings(self, title: str, settings: list[dict[str, Any]]) -> None:
        self._clear_dynamic_layout()
        self._row_widgets.clear()
        self._pending_changes.clear()
        self._mark_unsaved(False)

        self._current_group = title
        self.lblCategoryTitle.setText(title)
        self.btnRestoreDefault.setEnabled(not self._is_search_view and bool(settings))

        ordered = sorted(settings, key=lambda s: s.get("display_order", 0))
        for setting in ordered:
            row = self._build_setting_row(setting)
            self.dynamicSettingsLayout.addWidget(row)

        self.dynamicSettingsLayout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

    def _clear_dynamic_layout(self) -> None:
        while self.dynamicSettingsLayout.count():
            item = self.dynamicSettingsLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_setting_row(self, setting: dict[str, Any]) -> QFrame:
        setting_key: str = setting["setting_key"]
        data_type: str = setting.get("data_type", "string")
        current_value: str = setting.get("setting_value") or ""
        description: str = setting.get("description") or ""
        is_editable: bool = setting.get("is_editable", True)
        setting_group: str = setting.get("setting_group", "")

        row = QFrame()
        row.setProperty("cssClass", "settingRow")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(4)

        top_row = QHBoxLayout()
        label = QLabel(self._humanize_key(setting_key))
        label.setProperty("cssClass", "settingLabel")
        top_row.addWidget(label)
        top_row.addStretch()

        input_widget = self._make_input_widget(setting_key, data_type, current_value)
        input_widget.setEnabled(is_editable)
        top_row.addWidget(input_widget)
        row_layout.addLayout(top_row)

        if description:
            desc_label = QLabel(description)
            desc_label.setProperty("cssClass", "settingDescription")
            desc_label.setWordWrap(True)
            row_layout.addWidget(desc_label)

        self._row_widgets[setting_key] = (input_widget, data_type, current_value, setting_group)
        return row

    @staticmethod
    def _humanize_key(setting_key: str) -> str:
        """'security.max_login_attempts' -> 'Max Login Attempts'"""
        tail = setting_key.split(".")[-1]
        return tail.replace("_", " ").title()

    def _make_input_widget(
        self, setting_key: str, data_type: str, current_value: str
    ) -> QWidget:
        # Special case: the theme setting always gets a themed dropdown,
        # regardless of its declared data_type, since its valid values
        # are defined by theme_engine, not free text.
        if setting_key == THEME_SETTING_KEY:
            combo = QComboBox()
            combo.addItems(theme_engine.get_available_themes())
            if current_value in theme_engine.get_available_themes():
                combo.setCurrentText(current_value)
                combo.currentTextChanged.connect(
                    lambda _text, key=setting_key: self._on_setting_changed(key)
                )
                return combo

        # Special case: adjustable control height, a ranged spinbox
        # instead of the unranged default integer QSpinBox.
        if setting_key == UI_CONTROL_HEIGHT_KEY:
            spin = QSpinBox()
            spin.setRange(24, 48)
            spin.setSuffix(" px")
            try:
                spin.setValue(int(current_value))
            except (TypeError, ValueError):
                spin.setValue(34)
            spin.valueChanged.connect(
                lambda _value, key=setting_key: self._on_setting_changed(key)
            )
            return spin

        # Special case: adjustable base font size, a ranged spinbox
        # instead of the unranged default decimal QDoubleSpinBox.
        if setting_key == UI_FONT_SIZE_KEY:
            dspin = QDoubleSpinBox()
            dspin.setRange(8.0, 16.0)
            dspin.setDecimals(1)
            dspin.setSingleStep(0.5)
            dspin.setSuffix(" pt")
            try:
                dspin.setValue(float(current_value))
            except (TypeError, ValueError):
                dspin.setValue(10.5)
            dspin.valueChanged.connect(
                lambda _value, key=setting_key: self._on_setting_changed(key)
            )
            return dspin

        if setting_key == "general.language":
            combo = QComboBox()
            for code, display_name in language_manager.get_available_languages():
                combo.addItem(display_name, code)
            index = combo.findData(current_value)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.currentTextChanged.connect(
                lambda _text, key=setting_key: self._on_setting_changed(key)
            )
            return combo

        # Settings with a fixed, non-editable set of choices.
        if setting_key in FIXED_CHOICE_SETTINGS:
            options = FIXED_CHOICE_SETTINGS[setting_key]
            combo = QComboBox()
            combo.addItems(options)
            if current_value in options:
                combo.setCurrentText(current_value)
            combo.currentTextChanged.connect(
                lambda _text, key=setting_key: self._on_setting_changed(key)
            )
            return combo

        # Settings with common suggested choices, but a custom value
        # is still allowed (editable combo box).
        if setting_key in EDITABLE_CHOICE_SETTINGS:
            options = EDITABLE_CHOICE_SETTINGS[setting_key]
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(options)
            combo.setCurrentText(current_value)
            combo.setMinimumWidth(80)
            combo.currentTextChanged.connect(
                lambda _text, key=setting_key: self._on_setting_changed(key)
            )
            return combo

        if data_type == _BOOLEAN:
            checkbox = QCheckBox()
            checkbox.setChecked(str(current_value).strip().lower() == "true")
            checkbox.stateChanged.connect(
                lambda _state, key=setting_key: self._on_setting_changed(key)
            )
            return checkbox

        if data_type == _NUMERIC_INTEGER:
            spin = QSpinBox()
            spin.setRange(-2_147_483_648, 2_147_483_647)
            try:
                spin.setValue(int(current_value))
            except (TypeError, ValueError):
                spin.setValue(0)
            spin.valueChanged.connect(
                lambda _value, key=setting_key: self._on_setting_changed(key)
            )
            return spin

        if data_type == _NUMERIC_DECIMAL:
            dspin = QDoubleSpinBox()
            dspin.setRange(-1_000_000_000.0, 1_000_000_000.0)
            dspin.setDecimals(4)
            try:
                dspin.setValue(float(current_value))
            except (TypeError, ValueError):
                dspin.setValue(0.0)
            dspin.valueChanged.connect(
                lambda _value, key=setting_key: self._on_setting_changed(key)
            )
            return dspin

        if data_type == _DATE:
            date_edit = QDateEdit()
            date_edit.setCalendarPopup(True)
            date_edit.setDisplayFormat("yyyy-MM-dd")
            from PySide6.QtCore import QDate

            parsed = QDate.fromString(current_value, "yyyy-MM-dd")
            date_edit.setDate(parsed if parsed.isValid() else QDate.currentDate())
            date_edit.dateChanged.connect(
                lambda _date, key=setting_key: self._on_setting_changed(key)
            )
            return date_edit

        if data_type == _TIME:
            time_edit = QTimeEdit()
            time_edit.setDisplayFormat("HH:mm")
            from PySide6.QtCore import QTime

            parsed = QTime.fromString(current_value, "HH:mm")
            time_edit.setTime(parsed if parsed.isValid() else QTime.currentTime())
            time_edit.timeChanged.connect(
                lambda _time, key=setting_key: self._on_setting_changed(key)
            )
            return time_edit

        if data_type == _JSON:
            text_edit = QPlainTextEdit()
            text_edit.setPlainText(current_value)
            text_edit.setMaximumHeight(80)
            text_edit.textChanged.connect(
                lambda key=setting_key: self._on_setting_changed(key)
            )
            return text_edit

        if data_type == _PATH:
            return self._make_path_widget(setting_key, current_value)

        # Fallback: plain string.
        line_edit = QLineEdit()
        line_edit.setText(current_value)
        line_edit.textChanged.connect(
            lambda _text, key=setting_key: self._on_setting_changed(key)
        )
        return line_edit

    def _make_path_widget(self, setting_key: str, current_value: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        line_edit = QLineEdit()
        line_edit.setText(current_value)
        line_edit.textChanged.connect(
            lambda _text, key=setting_key: self._on_setting_changed(key)
        )
        layout.addWidget(line_edit)

        browse_btn = QPushButton("Browse")

        def _browse() -> None:
            chosen_dir = QFileDialog.getExistingDirectory(
                self, "Select Folder", line_edit.text()
            )
            if chosen_dir:
                line_edit.setText(chosen_dir)

        browse_btn.clicked.connect(_browse)
        layout.addWidget(browse_btn)

        # Keep a reference so _get_widget_value can find the QLineEdit.
        container.setProperty("pathLineEdit", line_edit)
        return container

    # -----------------------------------------------------------
    # Change tracking
    # -----------------------------------------------------------
    def _on_setting_changed(self, setting_key: str) -> None:
        widget, data_type, original_value, _setting_group = self._row_widgets[setting_key]
        new_value = self._get_widget_value(widget, data_type)
        if new_value == original_value:
            self._pending_changes.pop(setting_key, None)
        else:
            self._pending_changes[setting_key] = new_value
        self._mark_unsaved(bool(self._pending_changes))

    def _get_widget_value(self, widget: QWidget, data_type: str) -> str:
        if isinstance(widget, QComboBox):
            data = widget.currentData()
            return data if data is not None else widget.currentText()
            
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
            return widget.toPlainText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if data_type == _PATH:
            line_edit = widget.property("pathLineEdit")
            if isinstance(line_edit, QLineEdit):
                return line_edit.text()
        logger.warning(
            f"SettingsScreen: unrecognized widget type for data_type "
            f"'{data_type}'; returning empty string."
        )
        return ""

    def _mark_unsaved(self, has_changes: bool) -> None:
        self.lblUnsavedIndicator.setText("\u25CF Unsaved changes" if has_changes else "")

    def _confirm_discard_if_unsaved(self) -> bool:
        """Returns True if it is safe to proceed (no unsaved changes, or
        the user confirmed discarding them)."""
        if not self._pending_changes:
            return True
        return message.confirm(
            "You have unsaved changes. Discard them and continue?",
            "Unsaved Changes",
        )

    # -----------------------------------------------------------
    # Apply / Save / Restore
    # -----------------------------------------------------------
    def _on_btn_apply_clicked(self) -> None:
        if not self._pending_changes:
            self.statusbar.showMessage("No changes to apply.", 3000)
            return

        for setting_key, value in self._pending_changes.items():
            success, msg = settings_engine.apply_setting_temporarily(setting_key, value)
            if not success:
                logger.error(
                    f"SettingsScreen: apply_setting_temporarily('{setting_key}') "
                    f"failed: {msg}"
                )
                message.show_error(msg, "Apply Setting")
                return
            self._apply_screen_side_effects(setting_key, value)

        self.statusbar.showMessage("Applied (not saved).", 3000)

    def _on_btn_save_clicked(self) -> None:
        if not self._pending_changes:
            self.statusbar.showMessage("No changes to save.", 3000)
            return

        changed_groups: set[str] = set()
        for setting_key, value in list(self._pending_changes.items()):
            success, msg = settings_engine.save_setting(
                setting_key, value, updated_by=self._current_username
            )
            if not success:
                logger.error(f"SettingsScreen: save_setting('{setting_key}') failed: {msg}")
                message.show_error(
                    f"Could not save '{self._humanize_key(setting_key)}':\n{msg}",
                    "Save Setting",
                )
                return  # Stop on first failure; already-saved settings remain saved.

            self._apply_screen_side_effects(setting_key, value)
            _widget, _data_type, _original, setting_group = self._row_widgets[setting_key]
            changed_groups.add(setting_group)

        self._pending_changes.clear()
        self._mark_unsaved(False)
        self._load_categories()  # Refresh tree/values from the (now-updated) cache.

        saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.statusbar.showMessage(
            f"Saved by {self._current_username} at {saved_at}.", 5000
        )

        restart_groups = [g for g in changed_groups if g and settings_engine.requires_restart(g)]
        if restart_groups:
            readable = ", ".join(restart_groups)
            message.show_info(
                f"Changes in the following section(s) take effect after "
                f"restarting the application: {readable}.",
                "Restart Required",
            )

    def _apply_screen_side_effects(self, setting_key: str, value: str) -> None:
        """Handles settings whose effect is a UI-level action rather than
        something the Settings Engine itself performs (e.g. swapping the
        live stylesheet). Extend this as more such settings are added."""
        if setting_key == THEME_SETTING_KEY:
            theme_engine.apply_theme(value)
        elif setting_key in (UI_CONTROL_HEIGHT_KEY, UI_FONT_SIZE_KEY, UI_FONT_FAMILY_KEY):
            theme_engine.apply_theme(theme_engine.get_current_theme())

    def _on_btn_restore_default_clicked(self) -> None:
        if self._is_search_view or not self._row_widgets:
            return

        if not message.confirm(
            f"Restore all settings in \"{self._current_group}\" to their "
            f"default values?",
            "Restore Default",
        ):
            return

        for setting_key in list(self._row_widgets.keys()):
            success, msg = settings_engine.reset_setting_to_default(
                setting_key, updated_by=self._current_username
            )
            if not success:
                logger.error(
                    f"SettingsScreen: reset_setting_to_default('{setting_key}') "
                    f"failed: {msg}"
                )
                message.show_error(msg, "Restore Default")
                return

        self._load_categories()
        current_item = self.treeCategories.currentItem()
        if current_item is not None:
            group_name = current_item.text(0)
            self._render_settings(
                group_name, self._settings_by_group.get(group_name, [])
            )
        self.statusbar.showMessage("Restored to defaults.", 3000)

    # -----------------------------------------------------------
    # Import / Export
    # -----------------------------------------------------------
    def _on_btn_import_clicked(self) -> None:
        if not self._is_admin:
            message.show_error(
                "Only an Administrator can import settings.", "Import Settings"
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Settings", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        success, msg = settings_engine.import_settings(
            file_path, updated_by=self._current_username
        )
        if not success:
            logger.error(f"SettingsScreen: import_settings() failed: {msg}")
            message.show_error(msg, "Import Settings")
            return

        self._load_categories()
        current_item = self.treeCategories.currentItem()
        if current_item is not None:
            group_name = current_item.text(0)
            self._render_settings(
                group_name, self._settings_by_group.get(group_name, [])
            )
        message.show_info("Settings imported successfully.", "Import Settings")

    def _on_btn_export_clicked(self) -> None:
        if not self._is_admin:
            message.show_error(
                "Only an Administrator can export settings.", "Export Settings"
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Settings", "settings.json", "JSON Files (*.json)"
        )
        if not file_path:
            return

        # NOTE: the real export_settings() has no per-group filter — it
        # always exports every setting, regardless of which category is
        # currently open.
        success, msg = settings_engine.export_settings(file_path)
        if not success:
            logger.error(f"SettingsScreen: export_settings() failed: {msg}")
            message.show_error(msg, "Export Settings")
            return

        message.show_info(f"Settings exported to:\n{file_path}", "Export Settings")

    # -----------------------------------------------------------
    # Close
    # -----------------------------------------------------------
    def _on_btn_close_clicked(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if self._pending_changes and not message.confirm(
            "You have unsaved changes. Discard them and close?",
            "Unsaved Changes",
        ):
            event.ignore()
            return
        event.accept()
