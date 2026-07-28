"""
=========================================================
Medical ERP V2
Language Dialog
---------------------------------------------------------
UI event handling only. Built programmatically (it is a
small, single-purpose dialog) rather than from a .ui file -
still layout-based, no absolute positioning.
=========================================================
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton,
    QPushButton, QButtonGroup,
)

from utils.language_manager import get_available_languages, get_current_language_code, set_current_language
from utils.message import show_info


class LanguageDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Language")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        title = QLabel("Choose your preferred language:")
        layout.addWidget(title)

        self.button_group = QButtonGroup(self)
        current_code = get_current_language_code()

        for code, name in get_available_languages():
            radio = QRadioButton(name)
            radio.setProperty("languageCode", code)
            if code == current_code:
                radio.setChecked(True)
            self.button_group.addButton(radio)
            layout.addWidget(radio)

        button_row = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_ok.clicked.connect(self._handle_ok)
        self.btn_cancel.clicked.connect(self.reject)
        button_row.addWidget(self.btn_ok)
        button_row.addWidget(self.btn_cancel)
        layout.addLayout(button_row)

    def _handle_ok(self):
        selected = self.button_group.checkedButton()

        if selected is None:
            self.reject()
            return

        code = selected.property("languageCode")
        result = set_current_language(code)

        if result.applied:
            show_info(result.message, "Language")

        self.accept()
