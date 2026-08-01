"""
=========================================================
Medical ERP V2
Customer Form Screen (Add / Edit)
---------------------------------------------------------
UI event handling ONLY - no SQL, no business rules. Every
save goes through engines.customer_engine, which validates,
generates/checks the Customer Code, handles the photo via
utils.image_manager, and stamps audit fields via
engines.date_engine.

Same form is used for both Add and Edit, per spec's workflow:
    Dashboard -> Customer List -> Add -> Customer Form -> Save
    (Edit uses same form.)
=========================================================
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QCheckBox,
    QPushButton, QScrollArea, QWidget,
)

from utils.message import show_success, show_error, confirm
from engines import customer_engine
from widgets.photo_picker import PhotoPicker

ICON_DIR = "resources/icons"
NONE_OPTION_LABEL = "-- None --"


class CustomerFormScreen(QDialog):

    def __init__(self, login_result, customer_id: int | None = None, parent=None):
        super().__init__(parent)

        self.login_result = login_result
        self.customer_id = customer_id
        self.is_edit_mode = customer_id is not None
        self.lookup_data = customer_engine.get_lookup_data()

        self.setWindowTitle("Edit Customer" if self.is_edit_mode else "Add Customer")
        self.resize(760, 640)
        self.setModal(True)

        self._build_ui()

        if self.is_edit_mode:
            self._load_existing_customer()

    # -----------------------------------------------------
    # BUILD
    # -----------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setSpacing(20)

        content_layout.addWidget(self._build_photo_and_status_column(), 0)
        content_layout.addWidget(self._build_fields_column(), 1)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setPixmap(QIcon(f"{ICON_DIR}/customer.svg").pixmap(24, 24))
        row.addWidget(icon_label)

        title = QLabel("Edit Customer" if self.is_edit_mode else "Add Customer")
        title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        row.addWidget(title)
        row.addStretch(1)

        return header

    def _build_photo_and_status_column(self) -> QWidget:
        column = QWidget()
        column.setFixedWidth(180)
        layout = QVBoxLayout(column)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(16)

        self.photo_picker = PhotoPicker()
        layout.addWidget(self.photo_picker, 0, Qt.AlignmentFlag.AlignHCenter)

        self.chk_active = QCheckBox("Active")
        self.chk_active.setChecked(True)
        layout.addWidget(self.chk_active, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)
        return column

    def _build_fields_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(14)

        layout.addWidget(self._build_identification_group())
        layout.addWidget(self._build_contact_group())
        layout.addWidget(self._build_address_group())
        layout.addWidget(self._build_business_group())
        layout.addWidget(self._build_financial_group())
        layout.addWidget(self._build_classification_group())
        layout.addWidget(self._build_remarks_group())

        return column

    def _build_identification_group(self) -> QGroupBox:
        group = QGroupBox("Customer Identification")
        form = QFormLayout(group)

        self.txt_customer_code = QLineEdit()
        self.txt_customer_code.setPlaceholderText("Leave blank to auto-generate")
        form.addRow("Customer Code", self.txt_customer_code)

        self.txt_customer_name = QLineEdit()
        form.addRow("Customer Name *", self.txt_customer_name)

        self.txt_print_name = QLineEdit()
        form.addRow("Print Name", self.txt_print_name)

        self.txt_contact_person = QLineEdit()
        form.addRow("Contact Person", self.txt_contact_person)

        return group

    def _build_contact_group(self) -> QGroupBox:
        group = QGroupBox("Contact Details")
        form = QFormLayout(group)

        self.txt_phone = QLineEdit()
        form.addRow("Phone", self.txt_phone)

        self.txt_mobile = QLineEdit()
        form.addRow("Mobile", self.txt_mobile)

        self.txt_alternate_mobile = QLineEdit()
        form.addRow("Alternate Mobile", self.txt_alternate_mobile)

        self.txt_email = QLineEdit()
        form.addRow("Email", self.txt_email)

        self.txt_website = QLineEdit()
        form.addRow("Website", self.txt_website)

        return group

    def _build_address_group(self) -> QGroupBox:
        group = QGroupBox("Address")
        form = QFormLayout(group)

        self.txt_address = QPlainTextEdit()
        self.txt_address.setMaximumHeight(60)
        form.addRow("Address", self.txt_address)

        self.txt_city = QLineEdit()
        form.addRow("City", self.txt_city)

        self.txt_state = QLineEdit()
        form.addRow("State", self.txt_state)

        self.txt_country = QLineEdit("Nepal")
        form.addRow("Country", self.txt_country)

        self.txt_pincode = QLineEdit()
        form.addRow("PIN Code", self.txt_pincode)

        return group

    def _build_business_group(self) -> QGroupBox:
        group = QGroupBox("Business Identification")
        form = QFormLayout(group)

        self.txt_pan_vat = QLineEdit()
        form.addRow("PAN / VAT", self.txt_pan_vat)

        self.txt_gst_number = QLineEdit()
        form.addRow("GST Number (future ready)", self.txt_gst_number)

        self.txt_drug_license_no = QLineEdit()
        form.addRow("Drug License No.", self.txt_drug_license_no)

        return group

    def _build_financial_group(self) -> QGroupBox:
        group = QGroupBox("Financial")
        form = QFormLayout(group)

        self.spn_credit_limit = QDoubleSpinBox()
        self.spn_credit_limit.setRange(0, 999_999_999)
        self.spn_credit_limit.setDecimals(2)
        form.addRow("Credit Limit", self.spn_credit_limit)

        self.spn_credit_days = QSpinBox()
        self.spn_credit_days.setRange(0, 3650)
        form.addRow("Credit Days", self.spn_credit_days)

        self.spn_opening_balance = QDoubleSpinBox()
        self.spn_opening_balance.setRange(0, 999_999_999)
        self.spn_opening_balance.setDecimals(2)
        form.addRow("Opening Balance", self.spn_opening_balance)

        self.cmb_balance_type = QComboBox()
        self.cmb_balance_type.addItems(["Dr", "Cr"])
        form.addRow("Balance Type", self.cmb_balance_type)

        return group

    def _build_classification_group(self) -> QGroupBox:
        group = QGroupBox("Classification")
        form = QFormLayout(group)

        self.cmb_price_level = QComboBox()
        self._populate_lookup_combo(self.cmb_price_level, self.lookup_data["price_levels"], "price_level_id", "price_level_name")
        form.addRow("Price Level", self.cmb_price_level)

        self.cmb_area = QComboBox()
        self._populate_lookup_combo(self.cmb_area, self.lookup_data["areas"], "area_id", "area_name")
        form.addRow("Area", self.cmb_area)

        self.cmb_route = QComboBox()
        self._populate_lookup_combo(self.cmb_route, self.lookup_data["routes"], "route_id", "route_name")
        form.addRow("Route", self.cmb_route)

        return group

    def _build_remarks_group(self) -> QGroupBox:
        group = QGroupBox("Remarks")
        layout = QVBoxLayout(group)

        self.txt_remarks = QPlainTextEdit()
        self.txt_remarks.setMaximumHeight(60)
        layout.addWidget(self.txt_remarks)

        return group

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        row = QHBoxLayout(footer)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._handle_cancel)
        row.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._handle_save)
        row.addWidget(self.btn_save)

        return footer

    @staticmethod
    def _populate_lookup_combo(combo: QComboBox, rows: list[dict], id_key: str, name_key: str):
        combo.addItem(NONE_OPTION_LABEL, None)
        for row in rows:
            combo.addItem(row[name_key], row[id_key])

    @staticmethod
    def _select_combo_by_data(combo: QComboBox, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    # -----------------------------------------------------
    # LOAD (Edit mode)
    # -----------------------------------------------------

    def _load_existing_customer(self):
        row = customer_engine.get_customer(self.customer_id)
        if row is None:
            show_error("This customer could not be found. It may have been deleted.")
            self.reject()
            return

        self.txt_customer_code.setText(row.get("customer_code") or "")
        self.txt_customer_name.setText(row.get("customer_name") or "")
        self.txt_print_name.setText(row.get("print_name") or "")
        self.txt_contact_person.setText(row.get("contact_person") or "")
        self.txt_phone.setText(row.get("phone") or "")
        self.txt_mobile.setText(row.get("mobile") or "")
        self.txt_alternate_mobile.setText(row.get("alternate_mobile") or "")
        self.txt_email.setText(row.get("email") or "")
        self.txt_website.setText(row.get("website") or "")
        self.txt_address.setPlainText(row.get("address") or "")
        self.txt_city.setText(row.get("city") or "")
        self.txt_state.setText(row.get("state") or "")
        self.txt_country.setText(row.get("country") or "Nepal")
        self.txt_pincode.setText(row.get("pincode") or "")
        self.txt_pan_vat.setText(row.get("pan_vat") or "")
        self.txt_gst_number.setText(row.get("gst_number") or "")
        self.txt_drug_license_no.setText(row.get("drug_license_no") or "")
        self.spn_credit_limit.setValue(float(row.get("credit_limit") or 0))
        self.spn_credit_days.setValue(int(row.get("credit_days") or 0))
        self.spn_opening_balance.setValue(float(row.get("opening_balance") or 0))
        self.cmb_balance_type.setCurrentText(row.get("balance_type") or "Dr")
        self._select_combo_by_data(self.cmb_price_level, row.get("price_level_id"))
        self._select_combo_by_data(self.cmb_area, row.get("area_id"))
        self._select_combo_by_data(self.cmb_route, row.get("route_id"))
        self.txt_remarks.setPlainText(row.get("remarks") or "")
        self.chk_active.setChecked(bool(row.get("is_active", True)))

        self.photo_picker.load_existing(row.get("photo_path"))

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    def _collect_form_data(self) -> dict:
        data = {
            "customer_code": self.txt_customer_code.text().strip(),
            "customer_name": self.txt_customer_name.text().strip(),
            "print_name": self.txt_print_name.text().strip() or None,
            "contact_person": self.txt_contact_person.text().strip() or None,
            "address": self.txt_address.toPlainText().strip() or None,
            "city": self.txt_city.text().strip() or None,
            "state": self.txt_state.text().strip() or None,
            "country": self.txt_country.text().strip() or None,
            "pincode": self.txt_pincode.text().strip() or None,
            "phone": self.txt_phone.text().strip() or None,
            "mobile": self.txt_mobile.text().strip() or None,
            "alternate_mobile": self.txt_alternate_mobile.text().strip() or None,
            "email": self.txt_email.text().strip() or None,
            "website": self.txt_website.text().strip() or None,
            "pan_vat": self.txt_pan_vat.text().strip() or None,
            "gst_number": self.txt_gst_number.text().strip() or None,
            "drug_license_no": self.txt_drug_license_no.text().strip() or None,
            "credit_limit": self.spn_credit_limit.value(),
            "credit_days": self.spn_credit_days.value(),
            "opening_balance": self.spn_opening_balance.value(),
            "balance_type": self.cmb_balance_type.currentText(),
            "price_level_id": self.cmb_price_level.currentData(),
            "area_id": self.cmb_area.currentData(),
            "route_id": self.cmb_route.currentData(),
            "remarks": self.txt_remarks.toPlainText().strip() or None,
            "is_active": self.chk_active.isChecked(),
        }
        data.update(self.photo_picker.get_photo_update())
        return data

    def _handle_save(self):
        data = self._collect_form_data()

        if self.is_edit_mode:
            success, message = customer_engine.update_customer(self.customer_id, data, self.login_result.username)
        else:
            success, message, _new_id = customer_engine.create_customer(data, self.login_result.username)

        if success:
            show_success(message)
            self.accept()
        else:
            show_error(message)

    def _handle_cancel(self):
        if confirm("Discard changes to this customer?"):
            self.reject()
