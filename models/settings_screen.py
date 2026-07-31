"""
=========================================================
Medical ERP V2
Settings Screen
---------------------------------------------------------
UI event handling ONLY - no SQL here, no business rules.
Everything goes through engines.settings_engine, exactly
like every other screen in this app goes through its own
engine (see screens/dashboard_screen.py).

Visual language: a landing page of clickable group "tiles"
with a centered search bar - loosely inspired by a browser's
New Tab page, but built with this app's own dark/violet
design system (resources/dark_style.qss / style.qss) so it
stays consistent with Login and Dashboard rather than being
a copy of anything external.

Built as plain Python widgets (no .ui/Designer file) since
every value on this screen is driven by data the Settings
Engine returns at runtime - group list, per-group counts,
and search results all vary, so a static Designer layout
would need to be rebuilt in code anyway. This mirrors how
dashboard_engine.SIDEBAR_MODULES already drives dynamic UI
inside a Designer-built shell.
=========================================================
"""

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QStackedWidget, QFrame, QFileDialog,
    QDialog, QListWidget, QListWidgetItem,
)

from utils.app_logger import get_logger
from utils.message import show_success, show_warning, show_error, confirm
from utils.settings_ui_helpers import group_icon_name
from engines import settings_engine
from engines.theme_engine import toggle_theme, get_current_theme
from widgets.settings_tile import SettingsTile
from widgets.settings_field_row import SettingsFieldRow

logger = get_logger()

ICON_DIR = "resources/icons"
SEARCH_DEBOUNCE_MS = 300
RECENT_CHANGES_LIMIT = 8

PAGE_LANDING = 0
PAGE_GROUP_DETAIL = 1
PAGE_SEARCH_RESULTS = 2


class SettingsScreen(QMainWindow):

    def __init__(self, login_result, parent=None):
        super().__init__(parent)

        self.login_result = login_result
        self.current_group = None
        self.group_rows: dict[str, SettingsFieldRow] = {}
        self.search_rows: dict[str, SettingsFieldRow] = {}
        self.tiles: dict[str, SettingsTile] = {}
        self._pending_restart_groups: set[str] = set()

        self.setWindowTitle("Settings - Medical ERP")
        self.resize(1366, 800)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._run_search)

        self._build_ui()
        self._setup_shortcuts()
        self.reload_landing()

    # -----------------------------------------------------
    # BUILD
    # -----------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralwidget")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_landing_page())
        self.stack.addWidget(self._build_group_detail_page())
        self.stack.addWidget(self._build_search_results_page())
        root.addWidget(self.stack, 1)

        self.statusBar().showMessage(f"Signed in as {self.login_result.username}")

    def _build_header(self):
        header = QFrame()
        header.setObjectName("frmTopHeader")
        header.setFixedHeight(72)

        row = QHBoxLayout(header)
        row.setContentsMargins(20, 10, 20, 10)
        row.setSpacing(14)

        icon_label = QLabel()
        icon_label.setPixmap(QIcon(f"{ICON_DIR}/settings.svg").pixmap(QSize(22, 22)))
        row.addWidget(icon_label)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 14pt; font-weight: 700;")
        row.addWidget(title)

        self.btn_back = QPushButton("\u2190 All Settings")
        self.btn_back.setProperty("flat", "true")
        self.btn_back.clicked.connect(self.reload_landing)
        self.btn_back.hide()
        row.addWidget(self.btn_back)

        row.addStretch(1)

        # ---- centered search bar ----
        search_frame = QFrame()
        search_frame.setObjectName("frmSettingsSearchBar")
        search_frame.setFixedWidth(420)
        search_row = QHBoxLayout(search_frame)
        search_row.setContentsMargins(14, 4, 10, 4)
        search_row.setSpacing(6)

        search_icon = QLabel()
        search_icon.setPixmap(QIcon(f"{ICON_DIR}/search.svg").pixmap(QSize(16, 16)))
        search_row.addWidget(search_icon)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("txtSettingsSearch")
        self.txt_search.setPlaceholderText("Search settings\u2026")
        self.txt_search.textChanged.connect(self._handle_search_text_changed)
        search_row.addWidget(self.txt_search)
        row.addWidget(search_frame)

        row.addStretch(1)

        self.btn_theme = QPushButton()
        self.btn_theme.setToolTip("Switch between Light and Dark theme")
        self._refresh_theme_icon()
        self.btn_theme.clicked.connect(self._handle_theme_toggle)
        row.addWidget(self.btn_theme)

        self.btn_export = QPushButton("Export")
        self.btn_export.setToolTip("Export all settings to a JSON file")
        self.btn_export.clicked.connect(self._handle_export)
        row.addWidget(self.btn_export)

        self.btn_import = QPushButton("Import")
        self.btn_import.setToolTip("Import settings from a previously exported JSON file")
        self.btn_import.clicked.connect(self._handle_import)
        row.addWidget(self.btn_import)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        row.addWidget(self.btn_close)

        return header

    def _build_landing_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)

        self.lbl_restart_banner = QLabel()
        self.lbl_restart_banner.setStyleSheet(
            "background-color: #E0B84D; color: #1A1A22; border-radius: 8px; padding: 8px 14px; font-weight: 600;"
        )
        self.lbl_restart_banner.hide()
        layout.addWidget(self.lbl_restart_banner)

        recent_label = QLabel("Recently changed")
        recent_label.setStyleSheet("font-size: 11pt; font-weight: 700;")
        layout.addWidget(recent_label)

        self.recent_list = QListWidget()
        self.recent_list.setFixedHeight(110)
        self.recent_list.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.recent_list)

        groups_label = QLabel("All settings")
        groups_label.setStyleSheet("font-size: 11pt; font-weight: 700; margin-top: 6px;")
        layout.addWidget(groups_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.tiles_grid = QGridLayout(scroll_content)
        self.tiles_grid.setSpacing(16)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        return page

    def _build_group_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        self.lbl_group_icon = QLabel()
        header_row.addWidget(self.lbl_group_icon)

        self.lbl_group_title = QLabel()
        self.lbl_group_title.setStyleSheet("font-size: 14pt; font-weight: 700;")
        header_row.addWidget(self.lbl_group_title)

        self.lbl_group_restart_badge = QLabel("Restart required")
        self.lbl_group_restart_badge.setProperty("cssClass", "tileRestartBadge")
        self.lbl_group_restart_badge.hide()
        header_row.addWidget(self.lbl_group_restart_badge)

        header_row.addStretch(1)

        self.btn_discard_group = QPushButton("Discard")
        self.btn_discard_group.setProperty("flat", "true")
        self.btn_discard_group.clicked.connect(self._handle_discard_group)
        header_row.addWidget(self.btn_discard_group)

        self.btn_save_group = QPushButton("Save Changes")
        self.btn_save_group.clicked.connect(self._handle_save_group)
        self.btn_save_group.setEnabled(False)
        header_row.addWidget(self.btn_save_group)

        layout.addLayout(header_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.group_rows_container = QWidget()
        self.group_rows_layout = QVBoxLayout(self.group_rows_container)
        self.group_rows_layout.setSpacing(10)
        self.group_rows_layout.addStretch(1)
        scroll.setWidget(self.group_rows_container)
        layout.addWidget(scroll, 1)

        return page

    def _build_search_results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        self.lbl_search_summary = QLabel()
        self.lbl_search_summary.setStyleSheet("font-size: 11pt; font-weight: 700;")
        layout.addWidget(self.lbl_search_summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.search_rows_container = QWidget()
        self.search_rows_layout = QVBoxLayout(self.search_rows_container)
        self.search_rows_layout.setSpacing(10)
        self.search_rows_layout.addStretch(1)
        scroll.setWidget(self.search_rows_container)
        layout.addWidget(scroll, 1)

        return page

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.txt_search.setFocus)
        QShortcut(QKeySequence("Ctrl+W"), self, activated=self.close)
        QShortcut(QKeySequence("Escape"), self, activated=self._handle_escape)

    def _handle_escape(self):
        if self.stack.currentIndex() != PAGE_LANDING:
            self.reload_landing()

    # -----------------------------------------------------
    # THEME
    # -----------------------------------------------------

    def _refresh_theme_icon(self):
        theme_icon = "moon" if get_current_theme() == "Light" else "sun"
        self.btn_theme.setIcon(QIcon(f"{ICON_DIR}/{theme_icon}.svg"))

    def _handle_theme_toggle(self):
        new_theme = toggle_theme()
        self._refresh_theme_icon()
        self.statusBar().showMessage(f"Theme switched to {new_theme}", 3000)

    # -----------------------------------------------------
    # LANDING PAGE
    # -----------------------------------------------------

    def reload_landing(self):
        self.stack.setCurrentIndex(PAGE_LANDING)
        self.btn_back.hide()
        self.txt_search.blockSignals(True)
        self.txt_search.clear()
        self.txt_search.blockSignals(False)

        self._load_recent_changes()
        self._load_tiles()
        self._refresh_restart_banner()

    def _load_recent_changes(self):
        self.recent_list.clear()
        try:
            recent = settings_engine.get_recent_changes(RECENT_CHANGES_LIMIT)
        except Exception as e:
            logger.exception(f"SettingsScreen: could not load recent changes: {e}")
            recent = []

        if not recent:
            item = QListWidgetItem("No changes recorded yet.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recent_list.addItem(item)
            return

        for entry in recent:
            changed_at = entry.get("changed_at")
            when_text = changed_at.strftime("%Y-%m-%d %H:%M") if changed_at else ""
            key_label = entry.get("setting_key", "")
            group_label = entry.get("setting_group") or ""
            by_whom = entry.get("changed_by") or "unknown"
            text = f"{key_label}  ({group_label})  \u2192  {entry.get('new_value')}   \u2014 {by_whom}, {when_text}"
            self.recent_list.addItem(QListWidgetItem(text))

    def _load_tiles(self):
        # clear existing grid
        while self.tiles_grid.count():
            child = self.tiles_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.tiles.clear()

        try:
            grouped = settings_engine.get_settings_grouped()
        except Exception as e:
            logger.exception(f"SettingsScreen: could not load settings groups: {e}")
            show_error("Could not load settings from the database. Please check your connection.")
            return

        columns = 3
        for index, (group_name, rows) in enumerate(sorted(grouped.items())):
            tile = SettingsTile(
                group_name, len(rows), settings_engine.requires_restart(group_name)
            )
            tile.clicked.connect(self.open_group)
            self.tiles[group_name] = tile
            self.tiles_grid.addWidget(tile, index // columns, index % columns)

    def _refresh_restart_banner(self):
        if self._pending_restart_groups:
            names = ", ".join(sorted(self._pending_restart_groups))
            self.lbl_restart_banner.setText(
                f"You changed settings in: {names}. Restart the app for these to fully take effect."
            )
            self.lbl_restart_banner.show()
        else:
            self.lbl_restart_banner.hide()

    # -----------------------------------------------------
    # GROUP DETAIL PAGE
    # -----------------------------------------------------

    def open_group(self, group_name: str):
        self.current_group = group_name
        self.stack.setCurrentIndex(PAGE_GROUP_DETAIL)
        self.btn_back.show()

        try:
            grouped = settings_engine.get_settings_grouped()
        except Exception as e:
            logger.exception(f"SettingsScreen: could not load group '{group_name}': {e}")
            show_error("Could not load this settings group.")
            self.reload_landing()
            return

        rows = grouped.get(group_name, [])

        self.lbl_group_title.setText(group_name)
        self.lbl_group_icon.setPixmap(QIcon(f"{ICON_DIR}/{group_icon_name(group_name)}.svg").pixmap(QSize(24, 24)))
        self.lbl_group_restart_badge.setVisible(settings_engine.requires_restart(group_name))

        # clear previous rows
        while self.group_rows_layout.count():
            child = self.group_rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.group_rows.clear()

        for row in rows:
            field_row = SettingsFieldRow(row)
            field_row.apply_requested.connect(self._handle_apply)
            field_row.reset_requested.connect(self._handle_reset)
            field_row.history_requested.connect(self._handle_history)
            field_row.changed.connect(lambda _key: self._handle_field_dirty_check())
            self.group_rows[row["setting_key"]] = field_row
            self.group_rows_layout.addWidget(field_row)

        self.group_rows_layout.addStretch(1)
        self.btn_save_group.setEnabled(False)

    def _handle_discard_group(self):
        if self.current_group:
            self.open_group(self.current_group)

    def _handle_save_group(self):
        dirty_rows = [row for row in self.group_rows.values() if row.is_dirty()]

        if not dirty_rows:
            show_warning("No changes to save.")
            return

        saved, failed = 0, []
        for row in dirty_rows:
            value = row.current_value_str()
            if value is None:
                failed.append(f"{row.setting_key} (invalid value)")
                continue

            success, message = settings_engine.save_setting(
                row.setting_key, value, self.login_result.username
            )
            if success:
                row.mark_saved(value)
                saved += 1
            else:
                failed.append(f"{row.setting_key} ({message})")

        if saved and settings_engine.requires_restart(self.current_group):
            self._pending_restart_groups.add(self.current_group)

        if failed:
            show_warning(f"Saved {saved} setting(s). Could not save: {', '.join(failed)}")
        else:
            show_success(f"Saved {saved} setting(s).")

        self.btn_save_group.setEnabled(False)
        if self.current_group in self.tiles:
            try:
                grouped = settings_engine.get_settings_grouped()
                self.tiles[self.current_group].update_count(len(grouped.get(self.current_group, [])))
            except Exception:
                pass

    def _handle_field_dirty_check(self):
        any_dirty = any(row.is_dirty() for row in self.group_rows.values())
        self.btn_save_group.setEnabled(any_dirty)

    def _handle_apply(self, key: str, value: str):
        success, message = settings_engine.apply_setting_temporarily(key, value)
        if success:
            self.statusBar().showMessage(f"Applied '{key}' (preview only, not saved). Use Save Changes to persist.", 4000)
        else:
            show_warning(message)
        self._handle_field_dirty_check()

    def _handle_reset(self, key: str):
        if not confirm(f"Reset '{key}' to its default value?"):
            return

        success, message = settings_engine.reset_setting_to_default(key, self.login_result.username)
        if not success:
            show_error(message)
            return

        row = self.group_rows.get(key) or self.search_rows.get(key)
        if row:
            fresh = next(
                (r for r in settings_engine.get_settings_grouped().get(row.setting_row.get("setting_group"), [])
                 if r["setting_key"] == key),
                None,
            )
            default_value = fresh["setting_value"] if fresh else row.setting_row.get("default_value", "")
            row.mark_saved(default_value)

        self.statusBar().showMessage(f"'{key}' reset to default.", 3000)
        if self.current_group:
            self.open_group(self.current_group)

    def _handle_history(self, key: str):
        history = settings_engine.get_setting_history(key)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"History - {key}")
        dialog.resize(560, 380)
        layout = QVBoxLayout(dialog)

        list_widget = QListWidget()
        if not history:
            item = QListWidgetItem("No changes recorded for this setting yet.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            list_widget.addItem(item)
        else:
            for entry in history:
                changed_at = entry.get("changed_at")
                when_text = changed_at.strftime("%Y-%m-%d %H:%M") if changed_at else ""
                text = (
                    f"{entry.get('old_value')}  \u2192  {entry.get('new_value')}\n"
                    f"by {entry.get('changed_by') or 'unknown'} on {when_text}"
                    + (f"  \u2014 {entry.get('reason')}" if entry.get("reason") else "")
                )
                list_widget.addItem(QListWidgetItem(text))

        layout.addWidget(list_widget)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    def _handle_search_text_changed(self, text: str):
        if text.strip():
            self._search_timer.start(SEARCH_DEBOUNCE_MS)
        else:
            self.reload_landing()

    def _run_search(self):
        text = self.txt_search.text().strip()
        if not text:
            return

        self.stack.setCurrentIndex(PAGE_SEARCH_RESULTS)
        self.btn_back.show()

        try:
            results = settings_engine.search_settings(text)
        except Exception as e:
            logger.exception(f"SettingsScreen: search failed: {e}")
            results = []

        while self.search_rows_layout.count():
            child = self.search_rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.search_rows.clear()

        self.lbl_search_summary.setText(f"{len(results)} result(s) for \u201c{text}\u201d")

        for row in results:
            field_row = SettingsFieldRow(row, show_group_tag=True)
            field_row.apply_requested.connect(self._handle_search_apply)
            field_row.reset_requested.connect(self._handle_reset)
            field_row.history_requested.connect(self._handle_history)
            self.search_rows[row["setting_key"]] = field_row
            self.search_rows_layout.addWidget(field_row)

        self.search_rows_layout.addStretch(1)

    def _handle_search_apply(self, key: str, value: str):
        success, message = settings_engine.apply_setting_temporarily(key, value)
        if success:
            self.statusBar().showMessage(f"Applied '{key}' (preview only, not saved).", 4000)
        else:
            show_warning(message)

    # -----------------------------------------------------
    # EXPORT / IMPORT
    # -----------------------------------------------------

    def _handle_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Settings", "settings_export.json", "JSON (*.json)")
        if not path:
            return

        success, message = settings_engine.export_settings(path)
        if success:
            show_success(message)
        else:
            show_error(message)

    def _handle_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Settings", "", "JSON (*.json)")
        if not path:
            return

        if not confirm("Importing will overwrite existing setting values with those in the file. Continue?"):
            return

        success, message = settings_engine.import_settings(path, self.login_result.username)
        if success:
            show_success(message)
            self.reload_landing()
        else:
            show_error(message)
