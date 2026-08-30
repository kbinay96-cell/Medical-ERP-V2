"""
utils/purchase_invoice_pdf.py

Generates a print-ready PDF for a Purchase Invoice, matching the
physical Monika Medico bill layout. Used by:
    - the View dialog's "PDF" button (just saves the file)
    - the "Print" button (renders this same PDF, then sends it
      to a printer / print-preview)
    - the "Email" button (attaches this PDF)
    - the "WhatsApp" button (generates this PDF for the user to
      manually attach)

Pure function module -- no Qt dependency except reusing the
number-to-words helper already written for the View dialog.
"""

from __future__ import annotations

import logging

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

logger = logging.getLogger(__name__)

styles = getSampleStyleSheet()

_style_company_name = ParagraphStyle(
    "CompanyName", parent=styles["Normal"], fontSize=18, alignment=TA_CENTER, fontName="Helvetica-Bold"
)
_style_center = ParagraphStyle("Center", parent=styles["Normal"], alignment=TA_CENTER)
_style_bold_center = ParagraphStyle(
    "BoldCenter", parent=styles["Normal"], alignment=TA_CENTER, fontName="Helvetica-Bold"
)
_style_normal = styles["Normal"]
_style_bold = ParagraphStyle("Bold", parent=styles["Normal"], fontName="Helvetica-Bold")


def generate_purchase_invoice_pdf(
    output_path: str,
    invoice,
    supplier,
    company,
    item_engine,
    current_balance: float,
) -> str:
    """
    Builds the PDF at output_path and returns that same path.
    `invoice` is a PurchaseInvoiceDTO, `supplier` a SupplierDTO,
    `company` a CompanyDTO (may be None if not resolvable).
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
    )
    story = []

    # -- letterhead -----------------------------------------------------
    if company and company.logo_path:
        try:
            story.append(Image(company.logo_path, width=25 * mm, height=25 * mm))
        except Exception:
            logger.exception("Could not load company logo for PDF.")

    company_name = company.company_name if company else "(Company not set)"
    story.append(Paragraph(company_name, _style_company_name))
    if company and company.address:
        story.append(Paragraph(company.address, _style_center))
    if company and company.phone_no:
        story.append(Paragraph(f"Phone: {company.phone_no}", _style_center))

    id_bits = []
    if company and company.pan_vat_no:
        id_bits.append(f"PAN No: {company.pan_vat_no}")
    if company and company.dda_no:
        id_bits.append(f"DDA No: {company.dda_no}")
    if id_bits:
        story.append(Paragraph("&nbsp;&nbsp;&nbsp;".join(id_bits), _style_bold_center))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Invoice (Copy of Original)", _style_bold_center))
    story.append(Spacer(1, 4 * mm))

    # -- supplier + invoice details --------------------------------------
    supplier_lines = [f"<b>Supplier Details</b>", f"Name: {supplier.supplier_name if supplier else ''}"]
    if supplier and supplier.address:
        supplier_lines.append(f"Address: {supplier.address}")
    if supplier and supplier.phone_no:
        supplier_lines.append(f"Phone No: {supplier.phone_no}")
    if supplier and supplier.pan_vat_no:
        supplier_lines.append(f"Pan No: {supplier.pan_vat_no}")

    invoice_lines = [
        "<b>Invoice Details</b>",
        f"Invoice No: {invoice.invoice_number}",
        f"Internal Ref: {invoice.internal_ref_number}",
        f"Invoice Miti: {invoice.invoice_date_bs}",
        f"Invoice Date: {invoice.invoice_date_ad or ''}",
        f"Status: {invoice.status}",
    ]

    details_table = Table(
        [[
            Paragraph("<br/>".join(supplier_lines), _style_normal),
            Paragraph("<br/>".join(invoice_lines), _style_normal),
        ]],
        colWidths=[90 * mm, 90 * mm],
    )
    details_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 4 * mm))

    # -- item table -------------------------------------------------------
    header_row = ["SN.", "Particulars", "Batch_No", "Expiry", "MRP", "Qty.", "Free", "Rate", "Amount", "Dis%"]
    rows = [header_row]

    for idx, line in enumerate(invoice.lines, start=1):
        try:
            item_name = item_engine.get_item(line.item_id).item_name
        except Exception:
            item_name = f"(item #{line.item_id})"
        expiry_display = f"{line.expiry_month:02d}/{line.expiry_year}"
        amount = (line.qty or 0) * (line.purchase_rate or 0)
        rows.append([
            str(idx), item_name, line.batch_no or "", expiry_display,
            f"{line.mrp:.2f}", f"{line.qty:.2f}", f"{line.free_qty:.2f}",
            f"{line.purchase_rate:.2f}", f"{amount:.2f}", f"{line.discount_percent:.2f}",
        ])

    item_table = Table(
        rows,
        colWidths=[10 * mm, 45 * mm, 22 * mm, 16 * mm, 16 * mm, 14 * mm, 14 * mm, 16 * mm, 20 * mm, 12 * mm],
        repeatRows=1,
    )
    item_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(item_table)
    story.append(Spacer(1, 4 * mm))

    # -- summary -------------------------------------------------------
    basic_amount = sum((l.qty or 0) * (l.purchase_rate or 0) for l in invoice.lines)
    product_discount = sum(l.discount_amount or 0 for l in invoice.lines)
    cc_on_free_goods = sum(l.cc_amount or 0 for l in invoice.lines)

    summary_rows = [
        [f"Basic Amount: {basic_amount:.2f}", f"Product Discount: {product_discount:.2f}"],
        [f"CC On Free Goods: {cc_on_free_goods:.2f}", f"Round Off: {invoice.round_off_amount:.2f}"],
        [f"Net Total: {invoice.grand_total:.2f}", f"Current Balance: {current_balance:.2f}"],
    ]
    summary_table = Table(summary_rows, colWidths=[90 * mm, 90 * mm])
    summary_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph(
        f"<b>In Words:</b> {_amount_in_words(invoice.grand_total)}", _style_normal
    ))

    doc.build(story)
    return output_path


def _amount_in_words(amount: float) -> str:
    """Duplicated from PurchaseInvoiceViewDialog._amount_in_words (kept as
    a plain function here since this module has no Qt/GUI dependency and
    shouldn't import a QDialog subclass just for this)."""
    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
        "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
        "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two_digits(n: int) -> str:
        if n < 20:
            return ones[n]
        return (tens[n // 10] + (f" {ones[n % 10]}" if n % 10 else "")).strip()

    def three_digits(n: int) -> str:
        if n >= 100:
            return f"{ones[n // 100]} Hundred" + (f" {two_digits(n % 100)}" if n % 100 else "")
        return two_digits(n)

    n = int(round(amount))
    if n == 0:
        return "Zero Only"

    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1_000)
    hundred = n

    parts = []
    if crore:
        parts.append(f"{three_digits(crore)} Crore")
    if lakh:
        parts.append(f"{two_digits(lakh)} Lakh")
    if thousand:
        parts.append(f"{two_digits(thousand)} Thousand")
    if hundred:
        parts.append(three_digits(hundred))

    return " ".join(parts) + " Only"