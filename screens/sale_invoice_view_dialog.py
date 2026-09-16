"""
screens/sale_invoice_view_dialog.py

Print Preview dialog for a saved Sale Invoice. Renders the PDF from
utils/sale_invoice_pdf.py in an embedded QPdfView, with Print and
Save (PDF) buttons -- same single source of truth as the on-screen
preview (no separate widget-based layout to keep in sync).

Company is resolved via the session, same pattern confirmed in
screens/purchase_invoice_view_dialog.py (_get_current_company).
"""

from __future__ import annotations

import logging
import os
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewWidget
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout,
)

from engines.company_engine import CompanyEngine
from engines.session_manager import get_current_session
from utils.sale_invoice_pdf import generate_sale_invoice_pdf
from utils.window_chrome import apply_standard_window_chrome

logger = logging.getLogger(__name__)


class SaleInvoiceViewDialog(QDialog):
    """Read-only Sale Invoice print-preview dialog: PDF viewer + Print +
    Save (PDF) + Close. Deletes its temp preview PDF on close; never
    saves anything on its own unless the user explicitly clicks Save."""

    def __init__(self, parent, invoice, item_engine, customer_engine, free_scheme_enabled: bool):
        super().__init__(parent)
        self._invoice = invoice
        self._item_engine = item_engine
        self._customer_engine = customer_engine
        self._free_scheme_enabled = free_scheme_enabled
        self._view_temp_path: str | None = None

        self.setWindowTitle(f"Sale Invoice — {getattr(invoice, 'invoice_number', '')}")
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

        save_button = QPushButton("Save (PDF)")
        save_button.clicked.connect(self._on_save_pdf_clicked)
        button_row.addWidget(save_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        button_row.addWidget(close_button)

        root.addLayout(button_row)

    # ------------------------------------------------------------------ #
    def _load_preview_pdf(self) -> None:
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp_path = tmp.name
            tmp.close()
            self._generate_pdf_to(tmp_path)
            self._view_temp_path = tmp_path
            self._pdf_document.load(tmp_path)
        except Exception:
            logger.exception("Failed to load Sale Invoice preview PDF.")
            QMessageBox.warning(self, "Preview", "Could not generate the invoice preview.")

    def _generate_pdf_to(self, path: str) -> None:
        company = self._get_current_company()
        customer = self._get_customer()
        generate_sale_invoice_pdf(
            output_path=path,
            invoice=self._invoice,
            customer=customer,
            company=company,
            item_engine=self._item_engine,
            free_scheme_enabled=self._free_scheme_enabled,
        )

    def _get_current_company(self):
        try:
            session = get_current_session()
            if not session or "companyid" not in session:
                return None
            return CompanyEngine().get_company(session["companyid"])
        except Exception:
            logger.exception("Could not resolve current company for Sale invoice PDF/print.")
            return None

    def _get_customer(self) -> dict | None:
        customer_id = getattr(self._invoice, "customer_id", None)
        if not customer_id or not self._customer_engine:
            return None
        try:
            return self._customer_engine.get_customer(customer_id)
        except Exception:
            logger.exception("Could not resolve customer for Sale invoice PDF.")
            return None

    # ------------------------------------------------------------------ #
    def _on_zoom_in(self) -> None:
        self._pdf_view.setZoomFactor(self._pdf_view.zoomFactor() * 1.2)

    def _on_zoom_out(self) -> None:
        self._pdf_view.setZoomFactor(self._pdf_view.zoomFactor() / 1.2)

    def _on_fit_width(self) -> None:
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _on_print_clicked(self) -> None:
        pdf_path = self._view_temp_path
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.warning(self, "Print", "No PDF is loaded for this invoice.")
            return

        printer = QPrinter(QPrinter.HighResolution)

        def render(printer_to_render):
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

        preview_window.exec()

    def _on_save_pdf_clicked(self) -> None:
        default_name = f"SaleInvoice_{getattr(self._invoice, 'invoice_number', 'invoice')}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", default_name, "PDF Files (*.pdf)")
        if not path:
            return
        try:
            self._generate_pdf_to(path)
        except Exception as exc:
            logger.exception("Sale invoice PDF generation failed.")
            QMessageBox.warning(self, "Save PDF", f"Could not generate the invoice: {exc}")
            return
        QMessageBox.information(self, "Save PDF", f"Invoice saved to:\n{path}")

    def closeEvent(self, event) -> None:
        if self._view_temp_path and os.path.exists(self._view_temp_path):
            try:
                os.unlink(self._view_temp_path)
            except OSError:
                pass
        super().closeEvent(event)


__all__ = ["SaleInvoiceViewDialog"]