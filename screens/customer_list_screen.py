"""
=========================================================
Medical ERP V2
Customer List Screen
---------------------------------------------------------
UI event handling ONLY - no SQL, no business rules. Every
read/write goes through engines.customer_engine.

Workflow (per spec):
    Dashboard -> Customer List -> Add -> Customer Form -> Save
    (Edit uses the same form.)
=========================================================
"""

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
)

from utils.app_logger import get_logger
from utils.message import show_success, show_error, confirm
from engines import customer_engine
from screens.customer_form_screen import CustomerFormScreen

logger = get_logger()

ICON_DIR = "resources/icons"
SEARCH_DEBOUNCE_MS = 300

COLUMNS = ["Code", "Name", "Mobile", "City", "Area", "Route", "Price Level", "Balance", "Status", "Actions"]

STATUS_FILTER_OPTIONS = [("All", None), ("Active", True), ("Inactive", False)]


class CustomerListScreen(QMainWindow):

    def __init__(self, login_result, parent=None):
        super().__init__(parent)

        self.login_result = login_result
        self.lookup_data = customer_engine.get_lookup_data()

        self.setWindowTitle("Customers - Medical ERP")
        self.resize(1280, 760)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.reload)

        self._build_ui()
        self.reload()

    # -----------------------------------------------------
    # BUILD
    # -----------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        root.addWidget(self._build_header())
        root.addWidget(self._build_filter_bar())

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._handle_row_double_clicked)
        root.addWidget(self.table, 1)

        self.statusBar().showMessage(f"Signed in as {self.login_result.username}")

    def _build_header(self) -> QWidget:
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setPixmap(QIcon(f"{ICON_DIR}/customer.svg").pixmap(QSize(22, 22)))
        row.addWidget(icon_label)

        title = QLabel("Customers")
        title.setStyleSheet("font-size: 14pt; font-weight: 700;")
        row.addWidget(title)
        row.addStretch(1)

        self.btn_add = QPushButton()
        self.btn_add.setIcon(QIcon(f"{ICON_DIR}/plus.svg"))
        self.btn_add.setText(" Add Customer")
        self.btn_add.clicked.connect(lambda: self._open_form(None))
        row.addWidget(self.btn_add)

        return header

    def _build_filter_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        search_frame = QFrame()
        search_frame.setProperty("cssClass", "searchPill")
        search_row = QHBoxLayout(search_frame)
        search_row.setContentsMargins(12, 2, 8, 2)
        search_row.setSpacing(6)

        search_icon = QLabel()
        search_icon.setPixmap(QIcon(f"{ICON_DIR}/search.svg").pixmap(QSize(14, 14)))
        search_row.addWidget(search_icon)

        self.txt_search = QLineEdit()
        self.txt_search.setProperty("cssClass", "searchPillInput")
        self.txt_search.setPlaceholderText("Search by code, name, mobile, PAN, contact person\u2026")
        self.txt_search.setMinimumWidth(260)
        self.txt_search.textChanged.connect(lambda: self._search_timer.start(SEARCH_DEBOUNCE_MS))
        search_row.addWidget(self.txt_search)
        row.addWidget(search_frame)

        self.cmb_status_filter = QComboBox()
        for label, _value in STATUS_FILTER_OPTIONS:
            self.cmb_status_filter.addItem(label)
        self.cmb_status_filter.currentIndexChanged.connect(self.reload)
        row.addWidget(self.cmb_status_filter)

        self.cmb_area_filter = QComboBox()
        self.cmb_area_filter.addItem("All Areas", None)
        for area in self.lookup_data["areas"]:
            self.cmb_area_filter.addItem(area["area_name"], area["area_id"])
        self.cmb_area_filter.currentIndexChanged.connect(self.reload)
        row.addWidget(self.cmb_area_filter)

        self.cmb_route_filter = QComboBox()
        self.cmb_route_filter.addItem("All Routes", None)
        for route in self.lookup_data["routes"]:
            self.cmb_route_filter.addItem(route["route_name"], route["route_id"])
        self.cmb_route_filter.currentIndexChanged.connect(self.reload)
        row.addWidget(self.cmb_route_filter)

        self.cmb_price_level_filter = QComboBox()
        self.cmb_price_level_filter.addItem("All Price Levels", None)
        for level in self.lookup_data["price_levels"]:
            self.cmb_price_level_filter.addItem(level["price_level_name"], level["price_level_id"])
        self.cmb_price_level_filter.currentIndexChanged.connect(self.reload)
        row.addWidget(self.cmb_price_level_filter)

        row.addStretch(1)
        return bar

    # -----------------------------------------------------
    # LOAD
    # -----------------------------------------------------

    def reload(self):
        search_text = self.txt_search.text().strip() or None
        is_active = STATUS_FILTER_OPTIONS[self.cmb_status_filter.currentIndex()][1]
        area_id = self.cmb_area_filter.currentData()
        route_id = self.cmb_route_filter.currentData()
        price_level_id = self.cmb_price_level_filter.currentData()

        rows = customer_engine.search_customers(
            search_text=search_text, is_active=is_active,
            area_id=area_id, route_id=route_id, price_level_id=price_level_id,
        )

        self.table.setRowCount(0)
        for row_data in rows:
            self._add_table_row(row_data)

        self.statusBar().showMessage(f"{len(rows)} customer(s)", 3000)

    def _add_table_row(self, row_data: dict):
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)

        area_name = self._lookup_name(self.lookup_data["areas"], "area_id", row_data.get("area_id"), "area_name")
        route_name = self._lookup_name(self.lookup_data["routes"], "route_id", row_data.get("route_id"), "route_name")
        price_level_name = self._lookup_name(
            self.lookup_data["price_levels"], "price_level_id", row_data.get("price_level_id"), "price_level_name"
        )
        balance_text = f"{row_data.get('opening_balance', 0):,.2f} {row_data.get('balance_type', '')}"

        values = [
            row_data.get("customer_code", ""),
            row_data.get("customer_name", ""),
            row_data.get("mobile") or "",
            row_data.get("city") or "",
            area_name,
            route_name,
            price_level_name,
            balance_text,
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setData(Qt.ItemDataRole.UserRole, row_data["customer_id"])
            self.table.setItem(row_index, col, item)

        status_item = QTableWidgetItem("Active" if row_data.get("is_active") else "Inactive")
        status_item.setData(Qt.ItemDataRole.UserRole, row_data["customer_id"])
        self.table.setItem(row_index, len(values), status_item)

        self.table.setCellWidget(row_index, len(COLUMNS) - 1, self._build_actions_widget(row_data))

    def _build_actions_widget(self, row_data: dict) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        customer_id = row_data["customer_id"]
        is_active = bool(row_data.get("is_active"))

        btn_edit = QPushButton("Edit")
        btn_edit.setProperty("cssClass", "rowIconBtn")
        btn_edit.clicked.connect(lambda: self._open_form(customer_id))
        row.addWidget(btn_edit)

        btn_toggle = QPushButton("Deactivate" if is_active else "Activate")
        btn_toggle.setProperty("cssClass", "rowIconBtn")
        btn_toggle.clicked.connect(lambda: self._handle_toggle_active(customer_id, not is_active))
        row.addWidget(btn_toggle)

        btn_delete = QPushButton("Delete")
        btn_delete.setProperty("cssClass", "rowIconBtn")
        btn_delete.clicked.connect(lambda: self._handle_delete(customer_id))
        row.addWidget(btn_delete)

        return container

    @staticmethod
    def _lookup_name(rows: list[dict], id_key: str, value, name_key: str) -> str:
        if value is None:
            return ""
        for row in rows:
            if row[id_key] == value:
                return row[name_key]
        return ""

    # -----------------------------------------------------
    # ACTIONS
    # -----------------------------------------------------

    def _handle_row_double_clicked(self, row_index: int, column_index: int):
        item = self.table.item(row_index, 0)
        if item is None:
            return
        customer_id = item.data(Qt.ItemDataRole.UserRole)
        self._open_form(customer_id)

    def _open_form(self, customer_id: int | None):
        form = CustomerFormScreen(self.login_result, customer_id, parent=self)
        if form.exec():
            self.reload()

    def _handle_toggle_active(self, customer_id: int, activate: bool):
        action_word = "activate" if activate else "deactivate"
        if not confirm(f"Are you sure you want to {action_word} this customer?"):
            return

        success, message = customer_engine.set_active_status(customer_id, activate, self.login_result.username)
        if success:
            show_success(message)
            self.reload()
        else:
            show_error(message)

    def _handle_delete(self, customer_id: int):
        if not confirm("Delete this customer? This can be reversed only by a database administrator (soft delete)."):
            return

        success, message = customer_engine.soft_delete_customer(customer_id, self.login_result.username)
        if success:
            show_success(message)
            self.reload()
        else:
            show_error(message)
