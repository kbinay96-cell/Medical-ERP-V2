from __future__ import annotations

import logging
import os
import smtplib
import tempfile
from email.message import EmailMessage
from urllib.parse import quote

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewWidget
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from engines.company_engine import CompanyEngine
from engines.session_manager import get_current_session
from engines.settings_engine import get_company_setting, save_company_setting_value
from utils.integration_adapters import get_current_user_id
from utils.purchase_invoice_pdf import generate_purchase_invoice_pdf
from utils.window_chrome import apply_standard_window_chrome

logger = logging.getLogger(__name__)


class PurchaseInvoiceViewDialog(QDialog):
    """Read-only Purchase Invoice detail dialog. Renders the SAME PDF
    used by Print/Email/WhatsApp (via generate_purchase_invoice_pdf) in
    an embedded PDF viewer, so there is exactly one source of truth for
    what this invoice looks like -- no separate widget-based layout to
    keep in sync with the print output. The temp PDF used for on-screen
    viewing is deleted when the dialog closes; it is never saved
    anywhere by itself."""

    def __init__(self, parent, invoice, supplier_name, item_engine, supplier_engine):
        super().__init__(parent)
        self._invoice = invoice
        self._item_engine = item_engine
        self._supplier_engine = supplier_engine
        self._supplier_name = supplier_name
        self._view_temp_path: str | None = None

        self.setWindowTitle(f"Purchase Invoice — {invoice.internal_ref_number}")
        apply_standard_window_chrome(self, width=1100, height=800, start_maximized=True)

        root = QVBoxLayout(self)

        self._pdf_document = QPdfDocument(self)
        self._pdf_view = QPdfView(self)
        self._pdf_view.setDocument(self._pdf_document)
        self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(1.0)

        zoom_bar = QHBoxLayout()
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedWidth(30)
        zoom_out_btn.clicked.connect(self._on_zoom_out)
        zoom_bar.addWidget(zoom_out_btn)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedWidth(30)
        zoom_in_btn.clicked.connect(self._on_zoom_in)
        zoom_bar.addWidget(zoom_in_btn)

        fit_width_btn = QPushButton("Fit Width")
        fit_width_btn.clicked.connect(self._on_fit_width)
        zoom_bar.addWidget(fit_width_btn)

        zoom_bar.addStretch(1)
        root.addLayout(zoom_bar)

        root.addWidget(self._pdf_view, stretch=1)

        self._load_preview_pdf()

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        print_button = QPushButton("Print")
        print_button.clicked.connect(self._on_print_clicked)
        button_row.addWidget(print_button)

        pdf_button = QPushButton("PDF")
        pdf_button.clicked.connect(self._on_pdf_clicked)
        button_row.addWidget(pdf_button)

        email_button = QPushButton("Email")
        email_button.clicked.connect(self._on_email_clicked)
        button_row.addWidget(email_button)

        whatsapp_button = QPushButton("WhatsApp")
        whatsapp_button.clicked.connect(self._on_whatsapp_clicked)
        button_row.addWidget(whatsapp_button)

        change_wa_folder_button = QPushButton("📁")
        change_wa_folder_button.setToolTip("Change WhatsApp PDF save folder")
        change_wa_folder_button.setFixedWidth(30)
        change_wa_folder_button.clicked.connect(self._on_change_whatsapp_folder_clicked)
        button_row.addWidget(change_wa_folder_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        root.addLayout(button_row)

        # -- zoom controls -----------------------------------------------------

    def _on_zoom_in(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(self._pdf_view.zoomFactor() * 1.2)

    def _on_zoom_out(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(self._pdf_view.zoomFactor() / 1.2)

    def _on_fit_width(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def wheelEvent(self, event) -> None:
        """Ctrl + mouse wheel zooms the PDF preview, like every PDF
        reader and browser. Plain scroll (no Ctrl) still scrolls the
        page normally."""
        if event.modifiers() & Qt.ControlModifier:
            self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
            if event.angleDelta().y() > 0:
                self._pdf_view.setZoomFactor(self._pdf_view.zoomFactor() * 1.1)
            else:
                self._pdf_view.setZoomFactor(self._pdf_view.zoomFactor() / 1.1)
            event.accept()
        else:
            super().wheelEvent(event)

    # -- preview loading / cleanup ---------------------------------------

    def _load_preview_pdf(self) -> None:
        try:
            self._view_temp_path = self._generate_pdf()
            self._pdf_document.load(self._view_temp_path)
        except Exception:
            logger.exception("Could not generate/load invoice PDF for preview.")
            QMessageBox.warning(
                self, "Purchase Invoice",
                "Could not generate the invoice preview. You can still use "
                "the Print/PDF/Email/WhatsApp buttons below to try again.",
            )

    def closeEvent(self, event) -> None:
        self._cleanup_temp_pdf()
        super().closeEvent(event)

    def _cleanup_temp_pdf(self) -> None:
        if self._view_temp_path and os.path.exists(self._view_temp_path):
            try:
                self._pdf_document.close()
                os.remove(self._view_temp_path)
            except OSError:
                logger.warning(f"Could not remove temp preview PDF: {self._view_temp_path}")

    # -- shared helpers -----------------------------------------------------

    def _get_current_company(self):
        try:
            session = get_current_session()
            if not session or "companyid" not in session:
                return None
            return CompanyEngine().get_company(session["companyid"])
        except Exception:
            logger.exception("Could not resolve current company for PDF/print.")
            return None

    def _get_supplier(self):
        try:
            return self._supplier_engine.get_supplier(self._invoice.supplier_id)
        except Exception:
            logger.exception("Could not resolve supplier for PDF/print.")
            return None

    def _generate_pdf(self) -> str:
        """Generates the PDF to a temp file and returns its path. Reused
        by the on-screen preview, Print, the PDF button, and Email
        attachment -- single source of truth for the printable layout."""
        temp_path = os.path.join(
            tempfile.gettempdir(), f"PurchaseInvoice_{self._invoice.internal_ref_number}.pdf"
        )
        return self._generate_pdf_to(temp_path)

    def _generate_pdf_to(self, output_path: str) -> str:
        """Same as _generate_pdf() but saves directly to a user-chosen
        path instead of a temp file -- used by WhatsApp so the PDF is
        somewhere the user can easily find to attach."""
        company = self._get_current_company()
        supplier = self._get_supplier()
        current_balance = 0.0
        try:
            current_balance = self._supplier_engine.get_current_balance(self._invoice.supplier_id)
        except Exception:
            logger.exception("Could not resolve current balance for PDF.")

        return generate_purchase_invoice_pdf(
            output_path=output_path,
            invoice=self._invoice,
            supplier=supplier,
            company=company,
            item_engine=self._item_engine,
            current_balance=current_balance,
        )

    # -- button handlers -----------------------------------------------------

    def _on_print_clicked(self) -> None:
        try:
            pdf_path = self._generate_pdf()
        except Exception as exc:
            logger.exception("PDF generation failed for print.")
            QMessageBox.warning(self, "Print", f"Could not generate the invoice for printing: {exc}")
            return

        printer = QPrinter(QPrinter.HighResolution)

        def render(printer_to_render):
            from PySide6.QtGui import QPainter
            doc = QPdfDocument()
            doc.load(pdf_path)
            painter = QPainter(printer_to_render)
            for page in range(doc.pageCount()):
                if page > 0:
                    printer_to_render.newPage()
                page_size = doc.pagePointSize(page)
                target_rect = painter.viewport()
                image = doc.render(page, page_size.toSize() * 2)
                painter.drawImage(target_rect, image)
            painter.end()

        preview_window = QDialog(self)
        preview_window.setWindowTitle("Print Preview")
        preview_window.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowSystemMenuHint
        )
        preview_window.resize(1000, 800)

        layout = QVBoxLayout(preview_window)

        toolbar = QHBoxLayout()
        print_btn = QPushButton("🖨 Print")
        zoom_in_btn = QPushButton("Zoom In")
        zoom_out_btn = QPushButton("Zoom Out")
        fit_btn = QPushButton("Fit Page")
        close_btn = QPushButton("Close")
        toolbar.addWidget(print_btn)
        toolbar.addWidget(zoom_in_btn)
        toolbar.addWidget(zoom_out_btn)
        toolbar.addWidget(fit_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(close_btn)
        layout.addLayout(toolbar)

        preview_widget = QPrintPreviewWidget(printer, preview_window)
        preview_widget.paintRequested.connect(render)
        layout.addWidget(preview_widget)

        print_btn.clicked.connect(preview_widget.print_)
        zoom_in_btn.clicked.connect(preview_widget.zoomIn)
        zoom_out_btn.clicked.connect(preview_widget.zoomOut)
        fit_btn.clicked.connect(preview_widget.fitInView)
        close_btn.clicked.connect(preview_window.accept)

        preview_window.setWindowState(Qt.WindowMaximized)
        preview_window.exec()

    def _on_pdf_clicked(self) -> None:
        try:
            pdf_path = self._generate_pdf()
        except Exception as exc:
            logger.exception("PDF generation failed.")
            QMessageBox.warning(self, "PDF", f"Could not generate the PDF: {exc}")
            return

        default_name = f"PurchaseInvoice_{self._invoice.internal_ref_number}.pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Invoice PDF", default_name, "PDF Files (*.pdf)")
        if not save_path:
            return

        try:
            with open(pdf_path, "rb") as src, open(save_path, "wb") as dst:
                dst.write(src.read())
            QMessageBox.information(self, "PDF", f"Saved to:\n{save_path}")
        except OSError as exc:
            logger.exception("Could not copy generated PDF to chosen location.")
            QMessageBox.warning(self, "PDF", f"Could not save the file: {exc}")

    def _on_email_clicked(self) -> None:
        company = self._get_current_company()
        if not company:
            QMessageBox.warning(self, "Email", "No company is set up for this session.")
            return

        smtp_host = get_company_setting(company.company_id, "smtp.host", "")
        smtp_port = get_company_setting(company.company_id, "smtp.port", 587)
        smtp_email = get_company_setting(company.company_id, "smtp.email", "")
        smtp_password = get_company_setting(company.company_id, "smtp.app_password", "")

        if not smtp_host or not smtp_email or not smtp_password:
            QMessageBox.warning(
                self, "Email",
                "Email is not set up for this company yet. Go to Company Form "
                "and fill in the Email Settings (SMTP) section first.",
            )
            return

        supplier = self._get_supplier()
        default_recipient = supplier.email if supplier and supplier.email else ""
        recipient, ok = QInputDialog.getText(
            self, "Email", "Send invoice to:", text=default_recipient
        )
        if not ok or not recipient.strip():
            return

        try:
            pdf_path = self._generate_pdf()
        except Exception as exc:
            logger.exception("PDF generation failed for email.")
            QMessageBox.warning(self, "Email", f"Could not generate the invoice: {exc}")
            return

        msg = EmailMessage()
        msg["Subject"] = f"Purchase Invoice {self._invoice.internal_ref_number}"
        msg["From"] = smtp_email
        msg["To"] = recipient.strip()
        msg.set_content(
            f"Dear Supplier,\n\nPlease find attached Purchase Invoice "
            f"{self._invoice.internal_ref_number}.\n\nRegards,\n{company.company_name}"
        )
        with open(pdf_path, "rb") as f:
            msg.add_attachment(
                f.read(), maintype="application", subtype="pdf",
                filename=os.path.basename(pdf_path),
            )

        try:
            with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_email, smtp_password)
                server.send_message(msg)
            QMessageBox.information(self, "Email", f"Invoice emailed to {recipient.strip()}.")
        except Exception as exc:
            logger.exception("Failed to send invoice email.")
            QMessageBox.warning(self, "Email", f"Could not send the email: {exc}")

    def _on_whatsapp_clicked(self) -> None:
        company = self._get_current_company()
        folder = ""
        if company:
            folder = get_company_setting(company.company_id, "whatsapp.pdf_save_path", "") or ""

        if not folder or not os.path.isdir(folder):
            chosen_folder = QFileDialog.getExistingDirectory(
                self, "Choose a folder to save WhatsApp invoice PDFs (one-time setup)"
            )
            if not chosen_folder:
                return
            folder = chosen_folder
            if company:
                save_company_setting_value(
                    company.company_id, "whatsapp.pdf_save_path", folder,
                    str(get_current_user_id()), reason="Set from WhatsApp button",
                )

        default_name = f"PurchaseInvoice_{self._invoice.internal_ref_number}.pdf"
        save_path = os.path.join(folder, default_name)

        try:
            self._generate_pdf_to(save_path)
        except Exception as exc:
            logger.exception("PDF generation failed for WhatsApp.")
            QMessageBox.warning(self, "WhatsApp", f"Could not generate the invoice: {exc}")
            return

        pdf_path = save_path
        supplier = self._get_supplier()

        default_phone = ""
        if supplier and (supplier.mobile_no or supplier.phone_no):
            default_phone = supplier.mobile_no or supplier.phone_no

        phone, ok = QInputDialog.getText(
            self, "WhatsApp", "Supplier's WhatsApp number (with country code):", text=default_phone
        )
        if not ok or not phone.strip():
            return

        clean_phone = "".join(ch for ch in phone if ch.isdigit())
        if len(clean_phone) < 10:
            QMessageBox.warning(
                self, "WhatsApp",
                "That doesn't look like a valid phone number (needs at least "
                "10 digits, including country code). Please check and try again.",
            )
            return

        message = (
            f"Namaste, please find Purchase Invoice "
            f"{self._invoice.internal_ref_number} attached."
        )
        url = f"whatsapp://send?phone={clean_phone}&text={quote(message)}"
        opened = QDesktopServices.openUrl(QUrl(url))
        if not opened:
            QMessageBox.warning(
                self, "WhatsApp",
                "Could not open WhatsApp Desktop. Please make sure it is "
                "installed (download from whatsapp.com/download), or open "
                "WhatsApp manually and attach the PDF from:\n\n" + pdf_path,
            )
            return

        QMessageBox.information(
            self, "WhatsApp",
            f"WhatsApp is opening with the message ready.\n\n"
            f"Please attach this PDF and send:\n{pdf_path}",
        )

    def _on_change_whatsapp_folder_clicked(self) -> None:
        company = self._get_current_company()
        if not company:
            QMessageBox.warning(self, "WhatsApp Folder", "No company is set up for this session.")
            return

        chosen_folder = QFileDialog.getExistingDirectory(self, "Choose WhatsApp PDF save folder")
        if not chosen_folder:
            return

        save_company_setting_value(
            company.company_id, "whatsapp.pdf_save_path", chosen_folder,
            str(get_current_user_id()), reason="Changed from WhatsApp folder button",
        )
        QMessageBox.information(self, "WhatsApp Folder", f"Saved:\n{chosen_folder}")


__all__ = ["PurchaseInvoiceViewDialog"]