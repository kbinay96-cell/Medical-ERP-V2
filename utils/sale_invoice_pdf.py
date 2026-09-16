"""
utils/sale_invoice_pdf.py

Generates a dynamic, print-ready PDF for a Sale Invoice, matching the
same visual design standard as utils/purchase_invoice_pdf.py (same
fonts, spacing, logo handling, full-height grid). Column set adapts to
sale_mode: Retail shows 11 base columns; Wholesale adds CC Amt and Tax
Amt columns (matching the same Wholesale-only rule already used by
screens/sale_invoice_list_screen.py's _SaleInvoiceViewDialog).

NOTE: SaleInvoiceLineDTO does not carry mrp/packing (confirmed --
these exist only transiently inside SaleEngine.compute_line()'s
intermediate dict and are dropped when the DTO is built). This module
re-resolves both per line via item_engine.get_item(), the same
fallback approach utils/purchase_invoice_pdf.py already uses for
item_name.
"""

from __future__ import annotations

import os
import io
import logging
from datetime import datetime
from PIL import Image as PILImage

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
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from engines import settings_engine

logger = logging.getLogger(__name__)

styles = getSampleStyleSheet()

# --- Custom Paragraph Styles (mirrors utils/purchase_invoice_pdf.py exactly) ---
_style_top_shree = ParagraphStyle("SaleTopShree", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER)
_style_company_title = ParagraphStyle(
    "SaleCompanyTitleTight", parent=styles["Normal"], fontSize=21, leading=22,
    alignment=TA_CENTER, fontName="Helvetica-Bold",
)
_style_center = ParagraphStyle("SaleCenter", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8, leading=10)
_style_right = ParagraphStyle("SaleRight", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=8, leading=10)
_style_normal = ParagraphStyle("SaleNormalCustom", parent=styles["Normal"], fontSize=8, leading=10)
_style_bold = ParagraphStyle("SaleBoldCustom", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10)

# Table Cell Styles
_style_cell = ParagraphStyle("SaleCellNormal", parent=styles["Normal"], fontSize=7.5, leading=9, fontName="Helvetica")
_style_cell_center = ParagraphStyle("SaleCellCenter", parent=_style_cell, alignment=TA_CENTER)
_style_cell_right = ParagraphStyle("SaleCellRight", parent=_style_cell, alignment=TA_RIGHT)
_style_cell_bold = ParagraphStyle("SaleCellBold", parent=_style_cell, fontName="Helvetica-Bold")
_style_cell_header = ParagraphStyle("SaleCellHeader", parent=_style_cell_bold, alignment=TA_CENTER)

_style_amt_val = ParagraphStyle("SaleAmtVal", parent=_style_normal, alignment=TA_RIGHT)

TOTAL_GRID_ROWS = 28  # matches Purchase invoice's full-page-height appearance

# Fixed width (mm) per column name, when that column is visible. "Item"
# (renamed from Particulars) is NOT here -- it stretches to absorb
# whatever width remains out of the 194mm usable page width (A4 minus
# 8mm margins each side), same way COL_ITEM stretches in the real entry
# table (setSectionResizeMode(COL_ITEM, QHeaderView.Stretch)).
_PAGE_USABLE_WIDTH_MM = 194
_MIN_ITEM_WIDTH_MM = 30

_COLUMN_WIDTHS_MM = {
    "SN.": 8,
    "Batch No": 18,
    "Expiry": 14,
    "Packing": 14,
    "Mode": 16,
    "Qty": 12,
    "Free Qty": 12,
    "Rate": 14,
    "Disc %": 10,
    "MRP": 13,
    "Tax %": 10,
    "Tax Amt": 14,
    "Amount": 16,
}

_ENTRY_MODE_LABELS = {"free_qty": "Free Qty", "net_rate": "Net Rate"}


def _resolve_column_flags(is_wholesale: bool, free_scheme_enabled: bool) -> dict:
    """Reads the SAME sale.column_show_* settings the real entry table
    reads in SaleInvoiceFormScreen._build_visible_columns(), plus the
    same two engine-derived flags (Rate gated by is_wholesale, Free
    Qty/Mode gated by free_scheme_enabled) -- so the printed invoice
    always shows exactly the columns the entry screen showed."""
    return {
        "show_batch": bool(settings_engine.get_setting("sale.column_show_batch", True)),
        "show_expiry": bool(settings_engine.get_setting("sale.column_show_expiry", True)),
        "show_mrp": bool(settings_engine.get_setting("sale.column_show_mrp", True)),
        "show_discount": bool(settings_engine.get_setting("sale.column_show_discount_percent", True)),
        "show_packing": bool(settings_engine.get_setting("sale.column_show_packing", True)),
        "show_tax": bool(settings_engine.get_setting("sale.column_show_tax", False)),
        "show_free": free_scheme_enabled,
        "show_rate": is_wholesale,
    }


def _build_headers(flags: dict) -> list[str]:
    """Builds the header list in the SAME column order as
    COLUMN_HEADERS in sale_invoice_form_screen.py (Item, Batch No,
    Expiry, Packing, Mode, Qty, Free Qty, Rate, Disc %, MRP, Tax %,
    Tax Amt, Amount), with SN. prepended for print row-numbering
    (a print-only addition, not gated by any setting -- standard
    invoice convention, not part of the on-screen entry grid)."""
    headers = ["SN.", "Item"]
    if flags["show_batch"]:
        headers.append("Batch No")
    if flags["show_expiry"]:
        headers.append("Expiry")
    if flags["show_packing"]:
        headers.append("Packing")
    if flags["show_free"]:
        headers.append("Mode")
    headers.append("Qty")
    if flags["show_free"]:
        headers.append("Free Qty")
    if flags["show_rate"]:
        headers.append("Rate")
    if flags["show_discount"]:
        headers.append("Disc %")
    if flags["show_mrp"]:
        headers.append("MRP")
    if flags["show_tax"]:
        headers.append("Tax %")
        headers.append("Tax Amt")
    headers.append("Amount")
    return headers


def _build_column_widths_mm(headers: list[str]) -> list[float]:
    """Item gets whatever width remains after all other visible columns
    take their fixed width -- mirrors the entry table's COL_ITEM
    Stretch resize mode."""
    fixed_total = sum(_COLUMN_WIDTHS_MM.get(h, 0) for h in headers if h != "Item")
    item_width = max(_MIN_ITEM_WIDTH_MM, _PAGE_USABLE_WIDTH_MM - fixed_total)
    return [item_width if h == "Item" else _COLUMN_WIDTHS_MM.get(h, 10) for h in headers]


def compress_logo_to_buffer(image_path: str, max_width: int = 350, quality: int = 75) -> io.BytesIO | None:
    """Compresses a high-res company logo using Pillow to keep the PDF small.
    Identical behaviour to utils/purchase_invoice_pdf.py's helper."""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with PILImage.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            w_percent = max_width / float(img.size[0])
            if w_percent < 1.0:
                h_size = int(float(img.size[1]) * float(w_percent))
                img = img.resize((max_width, h_size), PILImage.Resampling.LANCZOS)

            img_buffer = io.BytesIO()
            img.save(img_buffer, format="JPEG", quality=quality, optimize=True)
            img_buffer.seek(0)
            return img_buffer
    except Exception as e:
        logger.error(f"Error compressing logo image: {e}")
        return None


def _resolve_line_item_details(item_engine, item_id: int) -> tuple[str, str, float]:
    """Returns (item_name, packing, mrp) for a line. SaleInvoiceLineDTO does
    not carry packing/mrp (confirmed dropped during DTO construction in
    SaleEngine._to_dto), so this always re-resolves via ItemEngine.get_item(),
    the same defensive pattern utils/purchase_invoice_pdf.py uses for
    item_name."""
    if not item_engine or not item_id:
        return f"(item #{item_id})" if item_id else "", "", 0.0
    try:
        item = item_engine.get_item(item_id)
        if not item:
            return f"(item #{item_id})", "", 0.0
        item_name = getattr(item, "item_name", "") or f"(item #{item_id})"
        packing = getattr(item, "packing", "") or ""
        mrp = float(getattr(item, "mrp", 0.0) or 0.0)
        return item_name, packing, mrp
    except Exception:
        logger.exception("Could not resolve item #%s for Sale invoice PDF.", item_id)
        return f"(item #{item_id})", "", 0.0


def _build_line_cell(header: str, ctx: dict) -> Paragraph:
    mapping = {
        "SN.": (str(ctx["idx"]), _style_cell_center),
        "Item": (ctx["item_name"], _style_cell),
        "Batch No": (str(ctx["batch_no"]), _style_cell_center),
        "Expiry": (ctx["expiry_display"], _style_cell_center),
        "Packing": (str(ctx["pack"]), _style_cell_center),
        "Mode": (ctx["entry_mode_label"], _style_cell_center),
        "MRP": (f"{ctx['mrp']:.2f}" if ctx["mrp"] else "", _style_cell_right),
        "Qty": (f"{ctx['qty']:.2f}", _style_cell_right),
        "Free Qty": (f"{ctx['free_qty']:.2f}", _style_cell_right),
        "Rate": (f"{ctx['rate']:.2f}", _style_cell_right),
        "Amount": (f"{ctx['amount']:.2f}", _style_cell_right),
        "Tax %": (f"{ctx['tax_pct']:.2f}", _style_cell_right),
        "Tax Amt": (f"{ctx['tax_amount']:.2f}", _style_cell_right),
        "Disc %": (f"{ctx['dis_pct']:.2f}", _style_cell_right),
    }
    text, style = mapping[header]
    return Paragraph(text, style)


def generate_sale_invoice_pdf(
    output_path: str,
    invoice,               # SaleInvoiceDTO
    customer: dict | None,
    company,                # CompanyDTO (attribute access, same as Purchase)
    item_engine,
    free_scheme_enabled: bool,
) -> str:
    """
    Builds the dynamic Sale Invoice PDF at output_path, matching the same
    visual design as utils/purchase_invoice_pdf.py.

    Args:
        output_path: full path where the PDF will be saved.
        invoice:     SaleInvoiceDTO (verified fields: invoice_number,
                     customer_id, customer_name, invoice_date_bs, sale_mode,
                     payment_type, grand_total, amount_paid_now,
                     balance_amount, status, area_id, area_name, remarks,
                     lines: list[SaleInvoiceLineDTO]).
        customer:    dict from CustomerEngine.get_customer(customer_id), or
                     None if lookup failed -- extra fields (address/phone/
                     PAN/drug license) degrade gracefully to blank.
        company:     CompanyDTO from CompanyEngine.get_company(), or None.
        item_engine: ItemEngine -- required to resolve item_name/packing/mrp
                     per line (see _resolve_line_item_details).
    """
    is_wholesale = getattr(invoice, "sale_mode", "") == "Wholesale"
    flags = _resolve_column_flags(is_wholesale, free_scheme_enabled)
    headers = _build_headers(flags)
    col_widths_mm = _build_column_widths_mm(headers)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
    )
    story = []

    # -- 1. Optional Dynamic Top Mantra -------------------------------------
    top_mantra = getattr(company, "top_mantra", "") or getattr(company, "mantra", "") if company else ""
    if top_mantra:
        header_top = Table(
            [[Paragraph("", _style_normal), Paragraph(f"|| {top_mantra} ||", _style_top_shree), Paragraph("", _style_normal)]],
            colWidths=[40 * mm, 114 * mm, 40 * mm],
        )
        header_top.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_top)
        story.append(Spacer(1, 0.5 * mm))

    # -- 2. Compact Company Header & Details --------------------------------
    company_name = (getattr(company, "company_name", "") or getattr(company, "name", "") if company else "") or ""
    logo_path = getattr(company, "logo_path", None) if company else None

    logo_img = None
    if logo_path:
        buf = compress_logo_to_buffer(logo_path)
        if buf:
            try:
                logo_img = Image(buf, width=15 * mm, height=15 * mm)
                logo_img.hAlign = "LEFT"
            except Exception as e:
                logger.error(f"Could not load compressed logo image: {e}")

    comp_title = Paragraph(f"<b>{company_name.upper()}</b>", _style_company_title)
    if logo_img:
        title_table = Table([[logo_img, comp_title]], colWidths=[4 * mm, 178 * mm])
        title_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (0, 0), 5 * mm),
            ("TOPPADDING", (1, 0), (1, 0), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(title_table)
    else:
        story.append(comp_title)

    story.append(Spacer(1, 0.1 * mm))

    comp_addr = getattr(company, "address", "") if company else ""
    comp_phone = ""
    if company:
        comp_phone = (
            getattr(company, "phone_no", None)
            or getattr(company, "mobile_no", None)
            or getattr(company, "phone", None)
            or getattr(company, "contact_no", None)
            or getattr(company, "mobile", "")
        )

    if comp_addr:
        story.append(Paragraph(str(comp_addr), _style_center))
        story.append(Spacer(1, 0.1 * mm))
    if comp_phone:
        story.append(Paragraph(f"Phone : {comp_phone}", _style_center))
        story.append(Spacer(1, 0.3 * mm))

    pan_no = (getattr(company, "pan_vat_no", "") or getattr(company, "pan_no", "")) if company else ""
    dda_no = getattr(company, "dda_no", "") if company else ""
    if pan_no or dda_no:
        story.append(Spacer(1, 0.5 * mm))
        story.append(Paragraph(f"<b>PAN No. :</b> {pan_no}" + "&nbsp;" * 150 + f"<b>DDA No. :</b> {dda_no}", _style_center))

    story.append(Spacer(1, 2 * mm))

    # -- 3. Customer & Invoice Details Boxes --------------------------------
    cust_name = getattr(invoice, "customer_name", "") or (customer.get("customer_name") if customer else "") or ""
    cust_addr = customer.get("address", "") if customer else ""
    cust_phone = (customer.get("phone") or customer.get("mobile") or "") if customer else ""
    cust_pan = customer.get("pan_vat", "") if customer else ""
    cust_drug_license = customer.get("drug_license_no", "") if customer else ""

    left_data = [
        [Paragraph("<b><u>Customer Details</u></b>", _style_bold), "", "", ""],
        [Paragraph("<b>Name</b>", _style_normal), Paragraph(f": <b>{cust_name}</b>", _style_normal), "", ""],
        [Paragraph("<b>Address</b>", _style_normal), Paragraph(f": {cust_addr}", _style_normal), "", ""],
        [Paragraph("<b>Phone No.</b>", _style_normal), Paragraph(f": {cust_phone}", _style_normal), "", ""],
        [Paragraph("<b>Pan No.</b>", _style_normal), Paragraph(f": {cust_pan}", _style_normal),
         Paragraph("<b>Drug Lic.</b>", _style_normal), Paragraph(f": {cust_drug_license}", _style_normal)],
    ]
    left_sub_table = Table(left_data, colWidths=[18 * mm, 42 * mm, 16 * mm, 28 * mm])
    left_sub_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (3, 0)), ("SPAN", (1, 1), (3, 1)), ("SPAN", (1, 2), (3, 2)), ("SPAN", (1, 3), (3, 3)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    inv_no = getattr(invoice, "invoice_number", "") or ""
    inv_miti = getattr(invoice, "invoice_date_bs", "") or ""
    sale_mode = getattr(invoice, "sale_mode", "") or ""
    area_name = getattr(invoice, "area_name", "") or ""
    payment_type = getattr(invoice, "payment_type", "") or "Credit"

    right_data = [
        [Paragraph("<b><u>Invoice Details</u></b>", _style_bold), ""],
        [Paragraph("<b>Invoice No.</b>", _style_normal), Paragraph(f": {inv_no}", _style_normal)],
        [Paragraph("<b>Invoice Miti</b>", _style_normal), Paragraph(f": {inv_miti}", _style_normal)],
        [Paragraph("<b>Sale Mode</b>", _style_normal), Paragraph(f": {sale_mode}", _style_normal)],
        [Paragraph("<b>Invoice Type</b>", _style_normal), Paragraph(f": {payment_type}", _style_normal)],
        [Paragraph("<b>Area</b>", _style_normal), Paragraph(f": {area_name}", _style_normal)],
    ]
    right_sub_table = Table(right_data, colWidths=[24 * mm, 54 * mm])
    right_sub_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    details_table = Table([[left_sub_table, "", right_sub_table]], colWidths=[108 * mm, 4 * mm, 82 * mm])
    details_table.setStyle(TableStyle([
        ("BOX", (0, 0), (0, 0), 0.5, colors.black), ("PADDING", (0, 0), (0, 0), 3.5),
        ("BOX", (2, 0), (2, 0), 0.5, colors.black), ("PADDING", (2, 0), (2, 0), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 2 * mm))

    # -- 4. Dynamic Items Table ----------------------------------------------
    header_row = [Paragraph(h, _style_cell_header) for h in headers]
    rows = [header_row]

    total_qty = 0.0
    total_free = 0.0
    gross_amount_sum = 0.0
    product_discount = 0.0
    cc_on_free_goods = 0.0
    tax_total = 0.0

    lines = list(getattr(invoice, "lines", []) or [])
    item_count = len(lines)

    for idx, line in enumerate(lines, start=1):
        item_id = getattr(line, "item_id", None)
        item_name, pack, mrp = _resolve_line_item_details(item_engine, item_id)

        batch_no = getattr(line, "batch_no", "") or ""
        exp_m = getattr(line, "expiry_month", 0) or 0
        exp_y = getattr(line, "expiry_year", 0) or 0
        expiry_display = f"{exp_m:02d}/{exp_y}" if exp_m and exp_y else ""

        qty = float(getattr(line, "qty", 0.0) or 0.0)
        free_qty = float(getattr(line, "free_qty", 0.0) or 0.0)
        rate = float(getattr(line, "rate", 0.0) or 0.0)
        amount = float(getattr(line, "amount", 0.0) or 0.0)
        dis_pct = float(getattr(line, "discount_percent", 0.0) or 0.0)
        discount_amount = float(getattr(line, "discount_amount", 0.0) or 0.0)
        cc_amount = float(getattr(line, "cc_amount", 0.0) or 0.0)
        tax_pct = float(getattr(line, "tax_percent", 0.0) or 0.0)
        tax_amount = float(getattr(line, "tax_amount", 0.0) or 0.0)
        entry_mode_raw = getattr(line, "entry_mode", "") or ""
        entry_mode_label = _ENTRY_MODE_LABELS.get(entry_mode_raw, entry_mode_raw)

        total_qty += qty
        total_free += free_qty
        gross_amount_sum += amount
        product_discount += discount_amount
        cc_on_free_goods += cc_amount
        tax_total += tax_amount

        ctx = {
            "idx": idx, "item_name": item_name, "pack": pack, "batch_no": batch_no,
            "expiry_display": expiry_display, "mrp": mrp, "qty": qty, "free_qty": free_qty,
            "rate": rate, "amount": amount, "tax_pct": tax_pct, "tax_amount": tax_amount,
            "dis_pct": dis_pct, "entry_mode_label": entry_mode_label,
        }
        rows.append([_build_line_cell(h, ctx) for h in headers])

    blank_rows_needed = max(0, TOTAL_GRID_ROWS - item_count)
    for _ in range(blank_rows_needed):
        rows.append([Paragraph("", _style_cell) for _ in headers])

    # Grid Total Row -- Qty./Free/Amount columns get totals, rest blank.
    total_row = []
    for h in headers:
        if h == "SN.":
            total_row.append(Paragraph("<b>Total :</b>", _style_cell_bold))
        elif h == "Qty":
            total_row.append(Paragraph(f"<b>{total_qty:.2f}</b>", _style_cell_right))
        elif h == "Free Qty":
            total_row.append(Paragraph(f"<b>{total_free:.2f}</b>", _style_cell_right))
        elif h == "Amount":
            total_row.append(Paragraph(f"<b>{gross_amount_sum:.2f}</b>", _style_cell_right))
        else:
            total_row.append(Paragraph("", _style_cell))
    rows.append(total_row)

    col_widths = [w * mm for w in col_widths_mm]
    row_heights = [6.5 * mm] + [5.6 * mm] * (len(rows) - 1)

    item_table = Table(rows, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
    table_style = [
        ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]
    num_cols = len(headers)
    for col_idx in range(num_cols - 1):
        table_style.append(("LINEAFTER", (col_idx, 0), (col_idx, -1), 0.4, colors.gray))
    for r_idx in range(1, item_count + 1):
        table_style.append(("LINEBELOW", (0, r_idx), (-1, r_idx), 0.4, colors.gray, None, (1, 2)))

    item_table.setStyle(TableStyle(table_style))
    story.append(item_table)
    story.append(Spacer(1, 2 * mm))

    # -- 5. Summary & Financial Totals ---------------------------------------
    grand_total = float(getattr(invoice, "grand_total", 0.0) or 0.0)
    amount_paid_now = float(getattr(invoice, "amount_paid_now", 0.0) or 0.0)
    balance_amount = float(getattr(invoice, "balance_amount", 0.0) or 0.0)
    round_off = float(getattr(invoice, "round_off_amount", 0.0) or getattr(invoice, "round_off", 0.0) or 0.0)
    bill_discount_amount = float(getattr(invoice, "bill_discount_amount", 0.0) or 0.0)
    remarks = getattr(invoice, "remarks", "") or ""
    printed_dt = datetime.now().strftime("%m/%d/%Y %I:%M:%S%p")

    bank_details_html = ""
    if company and hasattr(company, "bank_name") and getattr(company, "bank_name", None):
        bank_details_html = f"<br/><b>Bank Account:</b> {company.bank_name} &nbsp;&nbsp; Acc: {getattr(company, 'account_no', '')}"

    left_summary_data = [
        [Paragraph("<b>Printed DateTime :</b>", _style_normal), Paragraph(printed_dt, _style_normal)],
        [Paragraph("<b>Payment Type :</b>", _style_normal), Paragraph(payment_type, _style_normal)],
        [Paragraph("<b>Remarks :</b>", _style_normal), Paragraph(f"{remarks}{bank_details_html}", _style_normal)],
    ]
    left_summary_table = Table(left_summary_data, colWidths=[34 * mm, 92 * mm])
    left_summary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))

    discount_label = "Discount" if not is_wholesale else "Product Discount"

    right_summary_rows = [
        [Paragraph("<b>Amount Paid Now:</b>", _style_normal), Paragraph(f"{amount_paid_now:.2f}", _style_amt_val)],
    ]
    if not is_wholesale:
        # Retail: bill-level discount (SaleInvoiceDTO.bill_discount_amount),
        # NOT the per-line discount sum -- Retail lines carry no per-line
        # discount. Shown only when there IS a discount, independent of
        # the sale.column_show_discount_percent setting.
        if bill_discount_amount > 0:
            right_summary_rows.append(
                [Paragraph(f"<b>{discount_label}:</b>", _style_normal), Paragraph(f"{bill_discount_amount:.2f}", _style_amt_val)]
            )
    else:
        if flags["show_discount"]:
            right_summary_rows.append(
                [Paragraph(f"<b>{discount_label}:</b>", _style_normal), Paragraph(f"{product_discount:.2f}", _style_amt_val)]
            )
        # Wholesale: always shown, fixed regardless of any setting.
        right_summary_rows.append(
            [Paragraph("<b>CC On Free Goods:</b>", _style_normal), Paragraph(f"{cc_on_free_goods:.2f}", _style_amt_val)]
        )
    if flags["show_tax"]:
        right_summary_rows.append(
            [Paragraph("<b>Tax Amount:</b>", _style_normal), Paragraph(f"{tax_total:.2f}", _style_amt_val)]
        )
    right_summary_rows.append(
        [Paragraph("<b>Round Off:</b>", _style_normal), Paragraph(f"{round_off:.2f}", _style_amt_val)]
    )
    right_summary_rows.append(
        [Paragraph("<b>Net Total:</b>", _style_bold), Paragraph(f"<b>{balance_amount:.2f}</b>", _style_amt_val)]
    )

    right_summary_table = Table(right_summary_rows, colWidths=[36 * mm, 22 * mm])
    right_summary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))

    summary_table = Table([[left_summary_table, right_summary_table]], colWidths=[130 * mm, 64 * mm])
    summary_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    story.append(summary_table)

    words_str = _amount_in_words(grand_total)
    in_words_table = Table([[Paragraph(f"<b>In Words :</b> {words_str}", _style_normal)]], colWidths=[194 * mm])
    in_words_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.black), ("PADDING", (0, 0), (-1, -1), 3)]))
    story.append(in_words_table)

    doc.build(story)
    return output_path


def _amount_in_words(amount: float) -> str:
    """Converts a numerical amount into Indian Numbering System words.
    Identical implementation to utils/purchase_invoice_pdf.py."""
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
            return (f"{two_digits(n // 100)} Hundred " + two_digits(n % 100)).strip()
        return two_digits(n)

    try:
        n = int(round(amount))
    except (TypeError, ValueError):
        return "Zero Only"

    if n <= 0:
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


__all__ = ["generate_sale_invoice_pdf", "compress_logo_to_buffer"]