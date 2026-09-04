"""
screens/cancellation_reason_dialog.py

Shared Cancellation Reason Dialog - Medical ERP V2

This file did not yet exist in the real project (confirmed by repo search
during Receipt Module wiring verification), even though it is imported by
receipt_list_screen.py and is referenced as an already-shared component in
the Sale Return / Purchase Return blueprints. Creating it here as the one
true implementation so Sale Return, Purchase Return, Receipt, and Payment
all import the SAME dialog rather than each rolling their own.

Responsibility (and ONLY this):
    Collect a mandatory free-text cancellation reason before any Posted
    document (Receipt, Payment, Sale Return, Purchase Return, ...) is
    cancelled. Enforces the project-wide rule that cancellation always
    requires a reason -- OK is disabled until non-whitespace text is
    entered.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_MIN_REASON_LENGTH = 3


class CancellationReasonDialog(QDialog):
    """Modal dialog collecting a mandatory cancellation reason.

    Usage:
        dialog = CancellationReasonDialog(parent)
        if dialog.exec():
            reason = dialog.get_reason()  # guaranteed non-empty, stripped
    """

    def __init__(self, parent: Optional[QWidget] = None, prompt_text: str = "Please enter the reason for cancellation:") -> None:
        super().__init__(parent)
        self.setObjectName("dlgCancellationReason")
        self.setWindowTitle("Cancellation Reason")
        self.setModal(True)
        self.resize(420, 240)

        self._reason: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.lblPrompt = QLabel(prompt_text, self)
        self.lblPrompt.setObjectName("lblCancellationPrompt")
        self.lblPrompt.setWordWrap(True)
        layout.addWidget(self.lblPrompt)

        self.txtReason = QTextEdit(self)
        self.txtReason.setObjectName("txtCancellationReason")
        self.txtReason.setPlaceholderText("e.g. Entered against the wrong customer, duplicate entry, ...")
        self.txtReason.setFixedHeight(100)
        layout.addWidget(self.txtReason)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttonBox.setObjectName("buttonBoxCancellationReason")
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttonBox.accepted.connect(self._on_accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

        self.txtReason.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self) -> None:
        text = self.txtReason.toPlainText().strip()
        ok_button = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(len(text) >= _MIN_REASON_LENGTH)

    def _on_accept(self) -> None:
        text = self.txtReason.toPlainText().strip()
        if len(text) < _MIN_REASON_LENGTH:
            return
        self._reason = text
        self.accept()

    def get_reason(self) -> Optional[str]:
        """Returns the entered reason (stripped, non-empty) after an
        accepted dialog, or None if the dialog was cancelled/never
        accepted."""
        return self._reason