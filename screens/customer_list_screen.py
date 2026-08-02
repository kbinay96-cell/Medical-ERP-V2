"""
=========================================================
Medical ERP V2
Customer List Screen
---------------------------------------------------------
UI event handling ONLY - no SQL, no business rules. Every
read/write goes through engines.customer_engine.

Workflow (per spec):
    Dashboard -> Customer List -> Add -> Customer Form -> Save
    (Edit uses the same form, opened via double-click or the
    row's Edit button.)

Selecting a row (single click) shows a read-only Detail Panel
on the right, including the customer's photo - kept separate
from Edit, which still requires an explicit action (double-
click or the Edit button) so a stray click never opens the
form unexpectedly.
=========================================================
"""

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QSplitter, QScrollArea
)

from utils.app_logger import get_logger
from utils.message import show_success, show_error, confirm
from engines import customer_engine
from screens.customer_form_screen import CustomerFormScreen

logger = get_logger()

ICON_DIR = "resources/icons"
SEARCH_DEBOUNCE_MS = 300
DETAIL_PHOTO_SIZE = 120

COLUMNS = ["Code", "Name", "Mobile", "City", "Area", "Route", "Price Level", "Balance", "Status", "Actions"]

STATUS_FILTER_OPTIONS = [("All", None), ("Active", True), ("Inactive", False)]


class CustomerListScreen(QMainWindow):

    def __init__(self, login_result, parent=None):
        super().__init__(parent)

        self.login_result = login_result
        self.lookup_data = customer_engine.get_lookup_data()
        self._rows: list[dict] = []

        self.setWindowTitle("Customers - Medical ERP")
        self.resize(1360, 760)

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

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._handle_row_double_clicked)
        self.table.itemSelectionChanged.connect(self._handle_selection_changed)
        splitter.addWidget(self.table)

        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)

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
        self.btn_add.setToolTip("Add a new customer")
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
        self.txt_search.setMinimumWidth(240)
        self.txt_search.textChanged.connect(lambda: self._search_timer.start(SEARCH_DEBOUNCE_MS))
        search_row.addWidget(self.txt_search)
        row.addWidget(search_frame)

        self.cmb_status_filter = QComboBox()
        for label, _value in STATUS_FILTER_OPTIONS:
            self.cmb_status_filter.addItem(label)
        self.cmb_status_filter.setToolTip("Filter by Active/Inactive status")
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

        self.chk_show_deleted = QCheckBox("Show Deleted")
        self.chk_show_deleted.setToolTip("Include soft-deleted customers (needed to Restore one)")
        self.chk_show_deleted.toggled.connect(self.reload)
        row.addWidget(self.chk_show_deleted)

        row.addStretch(1)
        return bar

    def _build_detail_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(260)
        scroll.setMaximumWidth(340)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lbl_detail_photo = QLabel()
        self.lbl_detail_photo.setFixedSize(QSize(DETAIL_PHOTO_SIZE, DETAIL_PHOTO_SIZE))
        self.lbl_detail_photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_detail_photo, 0, Qt.AlignmentFlag.AlignHCenter)

        self.lbl_detail_name = QLabel("Select a customer")
        self.lbl_detail_name.setStyleSheet("font-size: 12pt; font-weight: 700;")
        self.lbl_detail_name.setWordWrap(True)
        self.lbl_detail_name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.lbl_detail_name)

        self.lbl_detail_code = QLabel("")
        self.lbl_detail_code.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.lbl_detail_code.setStyleSheet("color: #7A8599;")
        layout.addWidget(self.lbl_detail_code)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        self.lbl_detail_mobile = self._detail_field_row(layout, "Mobile:")
        self.lbl_detail_phone = self._detail_field_row(layout, "Phone:")
        self.lbl_detail_address = self._detail_field_row(layout, "Address:")
        self.lbl_detail_city = self._detail_field_row(layout, "City:")
        self.lbl_detail_area = self._detail_field_row(layout, "Area:")
        self.lbl_detail_route = self._detail_field_row(layout, "Route:")
        self.lbl_detail_price_level = self._detail_field_row(layout, "Price Level:")
        self.lbl_detail_balance = self._detail_field_row(layout, "Balance:")
        self.lbl_detail_credit_limit = self._detail_field_row(layout, "Credit Limit:")
        self.lbl_detail_status = self._detail_field_row(layout, "Status:")
       
        audit_divider = QFrame()
        audit_divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(audit_divider)

        audit_title = QLabel("Audit Trail")
        audit_title.setStyleSheet("color: #7A8599; font-weight: 700; font-size: 9pt;")
        layout.addWidget(audit_title)

        self.lbl_detail_created = self._detail_field_row(layout, "Created:")
        self.lbl_detail_updated = self._detail_field_row(layout, "Last Updated:")
        self.lbl_detail_deleted = self._detail_field_row(layout, "Deleted:")

        layout.addStretch(1)

        scroll.setWidget(panel)
        self._show_detail_placeholder()
        return scroll

    @staticmethod
    def _detail_field_row(parent_layout: QVBoxLayout, label_text: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(6)

        caption = QLabel(label_text)
        caption.setStyleSheet("color: #7A8599; font-weight: 600;")
        caption.setFixedWidth(90)
        row.addWidget(caption)

        value_label = QLabel("-")
        value_label.setWordWrap(True)
        row.addWidget(value_label, 1)

        parent_layout.addLayout(row)
        return value_label

    # -----------------------------------------------------
    # LOAD
    # -----------------------------------------------------

    def reload(self):
        self.lookup_data = customer_engine.get_lookup_data()
        self._refresh_filter_lookup_combos()

        search_text = self.txt_search.text().strip() or None
        is_active = STATUS_FILTER_OPTIONS[self.cmb_status_filter.currentIndex()][1]
        area_id = self.cmb_area_filter.currentData()
        route_id = self.cmb_route_filter.currentData()
        price_level_id = self.cmb_price_level_filter.currentData()
        include_deleted = self.chk_show_deleted.isChecked()

        rows = customer_engine.search_customers(
            search_text=search_text, is_active=is_active,
            area_id=area_id, route_id=route_id, price_level_id=price_level_id,
            include_deleted=include_deleted,
        )

        self._rows = rows
        self.table.setRowCount(0)
        for row_data in rows:
            self._add_table_row(row_data)

        self.statusBar().showMessage(f"{len(rows)} customer(s)", 3000)
        self._show_detail_placeholder()

    def _refresh_filter_lookup_combos(self):
        """Repopulates the Area/Route/Price Level filter dropdowns from fresh
        data, so a value just added via the Customer Form (an editable Area/
        Route combo can grow those tables) shows up immediately - without
        needing to close and reopen this List screen."""
        self._repopulate_lookup_combo(self.cmb_area_filter, self.lookup_data["areas"], "area_id", "area_name", "All Areas")
        self._repopulate_lookup_combo(self.cmb_route_filter, self.lookup_data["routes"], "route_id", "route_name", "All Routes")
        self._repopulate_lookup_combo(
            self.cmb_price_level_filter, self.lookup_data["price_levels"],
            "price_level_id", "price_level_name", "All Price Levels"
        )

    @staticmethod
    def _repopulate_lookup_combo(combo: QComboBox, rows: list[dict], id_key: str, name_key: str, all_label: str):
        previous_value = combo.currentData()
        combo.blockSignals(True)  # avoid re-triggering reload() while we rebuild the list
        combo.clear()
        combo.addItem(all_label, None)
        for row in rows:
            combo.addItem(row[name_key], row[id_key])
        index = combo.findData(previous_value)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

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
            if row_data.get("is_deleted"):
                item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row_index, col, item)

        if row_data.get("is_deleted"):
            status_text = "Deleted"
        elif row_data.get("is_active"):
            status_text = "Active"
        else:
            status_text = "Inactive"

        status_item = QTableWidgetItem(status_text)
        status_item.setData(Qt.ItemDataRole.UserRole, row_data["customer_id"])
        if row_data.get("is_deleted"):
            status_item.setForeground(Qt.GlobalColor.gray)
        self.table.setItem(row_index, len(values), status_item)

        self.table.setCellWidget(row_index, len(COLUMNS) - 1, self._build_actions_widget(row_data))

    def _build_actions_widget(self, row_data: dict) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        customer_id = row_data["customer_id"]
        is_active = bool(row_data.get("is_active"))
        is_deleted = bool(row_data.get("is_deleted"))

        if is_deleted:
            btn_restore = QPushButton("Restore")
            btn_restore.setProperty("cssClass", "rowIconBtn")
            btn_restore.setToolTip("Restore this deleted customer back to Active")
            btn_restore.clicked.connect(lambda: self._handle_restore(customer_id))
            row.addWidget(btn_restore)
            return container

        btn_edit = QPushButton("Edit")
        btn_edit.setProperty("cssClass", "rowIconBtn")
        btn_edit.setToolTip("Edit this customer's details")
        btn_edit.clicked.connect(lambda: self._open_form(customer_id))
        row.addWidget(btn_edit)

        btn_toggle = QPushButton("Deactivate" if is_active else "Activate")
        btn_toggle.setProperty("cssClass", "rowIconBtn")
        btn_toggle.setToolTip(
            "Mark this customer Inactive (hidden from Sales entry)" if is_active
            else "Mark this customer Active again"
        )
        btn_toggle.clicked.connect(lambda: self._handle_toggle_active(customer_id, not is_active))
        row.addWidget(btn_toggle)

        btn_delete = QPushButton("Delete")
        btn_delete.setProperty("cssClass", "rowIconBtn")
        btn_delete.setToolTip("Soft-delete this customer (can be restored later)")
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
    # DETAIL PANEL (updates on single click / selection)
    # -----------------------------------------------------

    def _handle_selection_changed(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            self._show_detail_placeholder()
            return

        customer_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        row_data = next((r for r in self._rows if r["customer_id"] == customer_id), None)
        if row_data is None:
            self._show_detail_placeholder()
            return

        self._show_detail(row_data)

    def _show_detail_placeholder(self):
        self.lbl_detail_photo.setPixmap(QIcon(f"{ICON_DIR}/user.svg").pixmap(QSize(48, 48)))
        self.lbl_detail_name.setText("Select a customer")
        self.lbl_detail_code.setText("")
        for label in (
        self.lbl_detail_mobile, self.lbl_detail_phone, self.lbl_detail_address,
        self.lbl_detail_city, self.lbl_detail_area, self.lbl_detail_route,
        self.lbl_detail_price_level, self.lbl_detail_balance,
        self.lbl_detail_credit_limit, self.lbl_detail_status,
        self.lbl_detail_created, self.lbl_detail_updated, self.lbl_detail_deleted,
    ):
            label.setText("-")

    @staticmethod
    def _format_audit(by, at_bs, at_ad) -> str:
        """Formats a 'who + when' audit pair - prefers the BS date (per
        project's BS-first rule), falls back to AD if BS wasn't stamped."""
        if not by and not at_bs and not at_ad:
            return "-"
        when = at_bs or (at_ad.strftime("%Y-%m-%d %H:%M") if at_ad else "")
        who = by or "-"
        return f"{who}\n{when}" if when else who

    def _show_detail(self, row_data: dict):
        photo_path = row_data.get("photo_path")
        pixmap = QPixmap(photo_path) if photo_path else None
        if pixmap and not pixmap.isNull():
            self.lbl_detail_photo.setPixmap(
                pixmap.scaled(
                    DETAIL_PHOTO_SIZE, DETAIL_PHOTO_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.lbl_detail_photo.setPixmap(QIcon(f"{ICON_DIR}/user.svg").pixmap(QSize(48, 48)))

        self.lbl_detail_name.setText(row_data.get("customer_name") or "-")
        self.lbl_detail_code.setText(row_data.get("customer_code") or "")

        area_name = self._lookup_name(self.lookup_data["areas"], "area_id", row_data.get("area_id"), "area_name")
        route_name = self._lookup_name(self.lookup_data["routes"], "route_id", row_data.get("route_id"), "route_name")
        price_level_name = self._lookup_name(
            self.lookup_data["price_levels"], "price_level_id", row_data.get("price_level_id"), "price_level_name"
        )

        self.lbl_detail_mobile.setText(row_data.get("mobile") or "-")
        self.lbl_detail_phone.setText(row_data.get("phone") or "-")
        self.lbl_detail_address.setText(row_data.get("address") or "-")
        self.lbl_detail_city.setText(row_data.get("city") or "-")
        self.lbl_detail_area.setText(area_name or "-")
        self.lbl_detail_route.setText(route_name or "-")
        self.lbl_detail_price_level.setText(price_level_name or "-")
        self.lbl_detail_balance.setText(
            f"{row_data.get('opening_balance', 0):,.2f} {row_data.get('balance_type', '')}"
        )
        self.lbl_detail_credit_limit.setText(f"{row_data.get('credit_limit', 0):,.2f}")

        if row_data.get("is_deleted"):
            self.lbl_detail_status.setText("Deleted")
        elif row_data.get("is_active"):
            self.lbl_detail_status.setText("Active")
        else:
            self.lbl_detail_status.setText("Inactive")

        self.lbl_detail_created.setText(
            self._format_audit(row_data.get("created_by"), row_data.get("created_at_bs"), row_data.get("created_at_ad"))
        )
        self.lbl_detail_updated.setText(
            self._format_audit(row_data.get("updated_by"), row_data.get("updated_at_bs"), row_data.get("updated_at_ad"))
        )
        self.lbl_detail_deleted.setText(
            self._format_audit(row_data.get("deleted_by"), row_data.get("deleted_at_bs"), row_data.get("deleted_at_ad"))
            if row_data.get("is_deleted") else "-"
        )

    # -----------------------------------------------------
    # ACTIONS
    # -----------------------------------------------------

    def _handle_row_double_clicked(self, row_index: int, column_index: int):
        item = self.table.item(row_index, 0)
        if item is None:
            return
        customer_id = item.data(Qt.ItemDataRole.UserRole)
        row_data = next((r for r in self._rows if r["customer_id"] == customer_id), None)
        if row_data is not None and row_data.get("is_deleted"):
            return  # deleted rows come back only via Restore, not Edit
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
        if not confirm("Delete this customer?\n\nThis can be restored later."):
            return

        success, message = customer_engine.soft_delete_customer(customer_id, self.login_result.username)
        if success:
            show_success(message)
            self.reload()
        else:
            show_error(message)

    def _handle_restore(self, customer_id: int):
        success, message = customer_engine.restore_customer(customer_id, self.login_result.username)
        if success:
            show_success(message)
            self.reload()
        else:
            show_error(message)