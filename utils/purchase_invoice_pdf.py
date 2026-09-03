"""
utils/purchase_invoice_pdf.py

Generates a dynamic, print-ready PDF for a Purchase Invoice matching 
 exact reference bill layout with full-page height grid, dotted item gridlines,
 image compression optimization, and clean box alignments.
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
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

logger = logging.getLogger(__name__)

styles = getSampleStyleSheet()

# --- Custom Paragraph Styles ---
_style_top_shree = ParagraphStyle("TopShree", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER)
_style_company_name = ParagraphStyle(
    "CompanyName", parent=styles["Normal"], fontSize=20, leading=22, alignment=TA_CENTER, fontName="Helvetica-Bold"
)
_style_center = ParagraphStyle("Center", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8, leading=10)
_style_bold_center = ParagraphStyle(
    "BoldCenter", parent=styles["Normal"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=8, leading=10
)
_style_right = ParagraphStyle("Right", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=8, leading=10)
_style_normal = ParagraphStyle("NormalCustom", parent=styles["Normal"], fontSize=8, leading=10)
_style_bold = ParagraphStyle("BoldCustom", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10)

# Table Cell Styles
_style_cell = ParagraphStyle("CellNormal", parent=styles["Normal"], fontSize=7.5, leading=9, fontName="Helvetica")
_style_cell_center = ParagraphStyle("CellCenter", parent=_style_cell, alignment=TA_CENTER)
_style_cell_right = ParagraphStyle("CellRight", parent=_style_cell, alignment=TA_RIGHT)
_style_cell_bold = ParagraphStyle("CellBold", parent=_style_cell, fontName="Helvetica-Bold")
_style_cell_header = ParagraphStyle("CellHeader", parent=_style_cell_bold, alignment=TA_CENTER)


def compress_logo_to_buffer(image_path: str, max_width: int = 350, quality: int = 75) -> io.BytesIO | None:
    """
    Compresses high-res company logo image dynamically using Pillow (PIL)
    to keep total PDF file size under 100KB-200KB.
    """
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


def generate_purchase_invoice_pdf(
    output_path: str,
    invoice,
    supplier,
    company,
    item_engine,
    current_balance: float = 0.0,
) -> str:
    """
    Builds the dynamic PDF at output_path matching exact reference design layout.
    """
    # Page setup with compact 8mm margins for clean A4 fit
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
    )
    story = []

    # -- 1. Optional Dynamic Top Mantra (Configurable via Settings) ------------
    top_mantra = getattr(company, "top_mantra", "") or getattr(company, "mantra", "")
    if top_mantra:
        header_top = Table(
            [[
                Paragraph("", _style_normal),
                Paragraph(f"|| {top_mantra} ||", _style_top_shree),
                Paragraph("", _style_normal),
            ]],
            colWidths=[40 * mm, 114 * mm, 40 * mm],
        )
        header_top.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_top)
        story.append(Spacer(1, 0.5 * mm))

    # -- 2. Compact Company Header & Details (Top Shifted Alignment) -----------
    company_name = getattr(company, "company_name", "") or getattr(company, "name", "MONIKA MEDICO PVT. LTD.")
    logo_path = getattr(company, "logo_path", None)
    
    logo_img = None
    if logo_path:
        buf = compress_logo_to_buffer(logo_path)
        if buf:
            try:
                logo_img = Image(buf, width=15 * mm, height=15 * mm)
                logo_img.hAlign = 'LEFT'
            except Exception as e:
                logger.error(f"Could not load compressed logo image: {e}")

    # Increased font size, tight line height, top-aligned
    _style_company_title = ParagraphStyle(
        "CompanyTitleTight", parent=styles["Normal"], fontSize=21, leading=22, alignment=TA_CENTER, fontName="Helvetica-Bold"
    )
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

    # Address & Phone Line
    
    comp_addr = getattr(company, "address", "") or ""
    # Safe fallback checking multiple possible phone attributes
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

    # PAN & DDA Line (Balanced Space Right Below Address)
    pan_no = getattr(company, "pan_vat_no", "") or getattr(company, "pan_no", "")
    dda_no = getattr(company, "dda_no", "")
    
    pan_bits = []
    if pan_no:
        pan_bits.append(f"<b>PAN No. :</b> {pan_no}")
    if dda_no:
        pan_bits.append(f"<b>DDA No. :</b> {dda_no}")

    if pan_bits:
        story.append(Spacer(1, 0.5 * mm))
        story.append(Paragraph(f"<b>PAN No. :</b> {pan_no}<seq reset/>" + "&nbsp;" * 150 + f"<b>DDA No. :</b> {dda_no}", _style_center))

    story.append(Spacer(1, 2 * mm))

    # -- 3. Customer & Invoice Details Boxes ---------------------------------
    sup_name = getattr(supplier, "supplier_name", "") or getattr(supplier, "name", "")
    sup_addr = getattr(supplier, "address", "")
    sup_phone = getattr(supplier, "phone_no", "") or getattr(supplier, "phone", "")
    sup_pan = getattr(supplier, "pan_vat_no", "") or getattr(supplier, "pan_no", "")
    sup_dda = getattr(supplier, "dda_no", "")

    inv_no = getattr(invoice, "invoice_number", "") or getattr(invoice, "invoice_no", "")
    internal_ref = getattr(invoice, "internal_ref_number", "")
    inv_miti = getattr(invoice, "invoice_date_bs", "")
    inv_date = getattr(invoice, "invoice_date_ad", "") or getattr(invoice, "date", "")
    payment_type = getattr(invoice, "payment_type", "") or getattr(invoice, "invoice_type", "Credit")
    branch_name = getattr(invoice, "branch", "Head Office")

    # Left Column: Customer Details Box
    left_data = [
        [Paragraph("<b><u>Customer Details</u></b>", _style_bold), "", "", ""],
        [Paragraph("<b>Name</b>", _style_normal), Paragraph(f": <b>{sup_name}</b>", _style_normal), "", ""],
        [Paragraph("<b>Address</b>", _style_normal), Paragraph(f": {sup_addr}", _style_normal), "", ""],
        [Paragraph("<b>Phone No.</b>", _style_normal), Paragraph(f": {sup_phone}", _style_normal), "", ""],
        [Paragraph("<b>Pan No.</b>", _style_normal), Paragraph(f": {sup_pan}", _style_normal), Paragraph("<b>DDA No.</b>", _style_normal), Paragraph(f": {sup_dda}", _style_normal)],
    ]
    
    left_sub_table = Table(left_data, colWidths=[18 * mm, 42 * mm, 16 * mm, 28 * mm])
    left_sub_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (3, 0)),
        ("SPAN", (1, 1), (3, 1)),
        ("SPAN", (1, 2), (3, 2)),
        ("SPAN", (1, 3), (3, 3)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    # Right Column: Invoice Details Box
    right_data = [
        [Paragraph("<b><u>Invoice Details</u></b>", _style_bold), ""],
        [Paragraph("<b>Invoice No.</b>", _style_normal), Paragraph(f": {inv_no}", _style_normal)],
        [Paragraph("<b>Invoice Miti</b>", _style_normal), Paragraph(f": {inv_miti}", _style_normal)],
        [Paragraph("<b>Invoice Date</b>", _style_normal), Paragraph(f": {inv_date}", _style_normal)],
        [Paragraph("<b>Invoice Type</b>", _style_normal), Paragraph(f": {payment_type}", _style_normal)],
        [Paragraph("<b>Branch</b>", _style_normal), Paragraph(f": {branch_name}", _style_normal)],
    ]
    if internal_ref:
        right_data.insert(2, [Paragraph("<b>Internal Ref</b>", _style_normal), Paragraph(f": {internal_ref}", _style_normal)])

    right_sub_table = Table(right_data, colWidths=[24 * mm, 54 * mm])
    right_sub_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    # Main Outer Details Box Table
    details_table = Table(
        [[left_sub_table, "", right_sub_table]],
        colWidths=[108 * mm, 4 * mm, 82 * mm],
    )
    details_table.setStyle(TableStyle([
        ("BOX", (0, 0), (0, 0), 0.5, colors.black),
        ("PADDING", (0, 0), (0, 0), 3.5),
        ("BOX", (2, 0), (2, 0), 0.5, colors.black),
        ("PADDING", (2, 0), (2, 0), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 2 * mm))

    # -- 4. Dynamic Items Table (Solid Vertical Lines, Dotted Row Lines) ------
    TOTAL_GRID_ROWS = 28  # Total table rows to ensure exact reference full-height appearance

    headers = ["SN.", "Particulars", "Pack", "Batch_No", "Expiry", "MRP", "Qty.", "Free", "Rate", "Amount", "Dis%"]
    rows = [[Paragraph(h, _style_cell_header) for h in headers]]

    total_qty = 0.0
    total_free = 0.0
    gross_amount_sum = 0.0

    lines = getattr(invoice, "lines", []) or getattr(invoice, "items_list", []) or []
    item_count = len(lines)

    for idx, line in enumerate(lines, start=1):
        if hasattr(line, "item_id") and item_engine:
            try:
                item_name = item_engine.get_item(line.item_id).item_name
            except Exception:
                item_name = getattr(line, "item_name", getattr(line, "name", f"(item #{line.item_id})"))
        else:
            item_name = getattr(line, "item_name", getattr(line, "name", ""))

        pack = getattr(line, "pack", "") or ""
        batch_no = getattr(line, "batch_no", "") or getattr(line, "batch", "") or ""
        
        # Expiry formatting
        exp_m = getattr(line, "expiry_month", 0) or 0
        exp_y = getattr(line, "expiry_year", 0) or 0
        exp_str = getattr(line, "exp", "") or getattr(line, "expiry", "")
        if exp_m and exp_y:
            expiry_display = f"{exp_m:02d}/{exp_y}"
        elif exp_str:
            expiry_display = exp_str
        else:
            expiry_display = ""

        qty = float(getattr(line, "qty", 0.0) or 0.0)
        free_qty = float(getattr(line, "free_qty", 0.0) or getattr(line, "free", 0.0) or 0.0)
        rate = float(getattr(line, "purchase_rate", 0.0) or getattr(line, "rate", 0.0) or 0.0)
        
        line_amt = getattr(line, "amount", None)
        amount = float(line_amt) if line_amt is not None else (qty * rate)
        
        mrp = float(getattr(line, "mrp", 0.0) or 0.0)
        dis_pct = float(getattr(line, "discount_percent", 0.0) or getattr(line, "disc", 0.0) or 0.0)

        total_qty += qty
        total_free += free_qty
        gross_amount_sum += amount

        rows.append([
            Paragraph(str(idx), _style_cell_center),
            Paragraph(item_name, _style_cell),
            Paragraph(str(pack), _style_cell_center),
            Paragraph(str(batch_no), _style_cell_center),
            Paragraph(expiry_display, _style_cell_center),
            Paragraph(f"{mrp:.2f}" if mrp else "", _style_cell_right),
            Paragraph(f"{qty:.2f}", _style_cell_right),
            Paragraph(f"{free_qty:.2f}", _style_cell_right),
            Paragraph(f"{rate:.2f}", _style_cell_right),
            Paragraph(f"{amount:.2f}", _style_cell_right),
            Paragraph(f"{dis_pct:.2f}", _style_cell_right),
        ])

    # Plain empty rows filling bottom height
    blank_rows_needed = max(0, TOTAL_GRID_ROWS - item_count)
    for _ in range(blank_rows_needed):
        rows.append([Paragraph("", _style_cell) for _ in range(11)])

    # Grid Total Row
    total_row = [
        Paragraph("<b>Total :</b>", _style_cell_bold),
        Paragraph("", _style_cell),
        Paragraph("", _style_cell),
        Paragraph("", _style_cell),
        Paragraph("", _style_cell),
        Paragraph("", _style_cell),
        Paragraph(f"<b>{total_qty:.2f}</b>", _style_cell_right),
        Paragraph(f"<b>{total_free:.2f}</b>", _style_cell_right),
        Paragraph("", _style_cell),
        Paragraph(f"<b>{gross_amount_sum:.2f}</b>", _style_cell_right),
        Paragraph("", _style_cell),
    ]
    rows.append(total_row)

    col_widths = [8*mm, 52*mm, 15*mm, 20*mm, 16*mm, 15*mm, 14*mm, 12*mm, 16*mm, 16*mm, 10*mm]
    row_heights = [6.5 * mm] + [5.6 * mm] * (len(rows) - 1)

    item_table = Table(rows, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
    
    # Grid Styling
    table_style = [
        ("BOX", (0, 0), (-1, -1), 0.75, colors.black),                 # Outer Solid Box
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),            # Header Bottom Solid Line
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),          # Total Row Top Solid Line
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]

    # Continuous Vertical Lines down all columns
    for col_idx in range(10):
        table_style.append(("LINEAFTER", (col_idx, 0), (col_idx, -1), 0.4, colors.gray))

    # Horizontal Dotted Lines (Only active item rows)
    for r_idx in range(1, item_count + 1):
        table_style.append(("LINEBELOW", (0, r_idx), (-1, r_idx), 0.4, colors.gray, None, (1, 2)))

    item_table.setStyle(TableStyle(table_style))
    story.append(item_table)
    story.append(Spacer(1, 2 * mm))

    # -- 5. Summary & Financial Totals Section --------------------------------
    product_discount = sum(float(getattr(l, "discount_amount", 0) or getattr(l, "disc_amt", 0) or 0) for l in lines)
    cc_on_free_goods = sum(float(getattr(l, "cc_amount", 0) or getattr(l, "cc_amt", 0) or 0) for l in lines)
    round_off = float(getattr(invoice, "round_off_amount", 0.0) or getattr(invoice, "round_off", 0.0) or 0.0)
    net_total = float(getattr(invoice, "grand_total", 0.0) or getattr(invoice, "net_total", gross_amount_sum - product_discount) or 0.0)
    
    printed_dt = datetime.now().strftime("%m/%d/%Y %I:%M:%S%p")
    remarks = getattr(invoice, "remarks", "") or ""

    bank_details_html = ""
    if hasattr(company, "bank_name") and getattr(company, "bank_name", None):
        bank_details_html = f"<br/><b>Bank Account:</b> {company.bank_name} &nbsp;&nbsp; Acc: {getattr(company, 'account_no', '')}"

    left_summary_data = [
        [Paragraph("<b>Printed DateTime :</b>", _style_normal), Paragraph(printed_dt, _style_normal)],
        [Paragraph("<b>Total Amount :</b>", _style_normal), Paragraph(f"NRs. {net_total:.2f}", _style_normal)],
        [Paragraph("<b>Current Balance :</b>", _style_normal), Paragraph(f"NRs. {current_balance:.2f}", _style_normal)],
        [Paragraph("<b>Remarks :</b>", _style_normal), Paragraph(f"{remarks}{bank_details_html}", _style_normal)],
    ]
    left_summary_table = Table(left_summary_data, colWidths=[32 * mm, 94 * mm])
    left_summary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))

    _style_amt_val = ParagraphStyle("AmtVal", parent=_style_normal, alignment=2) # 2 = TA_RIGHT

    right_summary_data = [
        [Paragraph("<b>Product Discount:</b>", _style_normal), Paragraph(f"{product_discount:.2f}", _style_amt_val)],
        [Paragraph("<b>CC On Free Goods:</b>", _style_normal), Paragraph(f"{cc_on_free_goods:.2f}", _style_amt_val)],
        [Paragraph("<b>Round Off:</b>", _style_normal), Paragraph(f"{round_off:.2f}", _style_amt_val)],
        [Paragraph("<b>Net Total:</b>", _style_bold), Paragraph(f"<b>{net_total:.2f}</b>", _style_amt_val)],
    ]

    right_summary_table = Table(right_summary_data, colWidths=[36 * mm, 22 * mm])
    right_summary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))

    summary_table = Table(
        [[
            left_summary_table,
            right_summary_table,
        ]],
        colWidths=[130 * mm, 64 * mm],
    )
    summary_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    story.append(summary_table)

    # In Words Box
    words_str = _amount_in_words(net_total)
    in_words_table = Table(
        [[Paragraph(f"<b>In Words :</b> {words_str}", _style_normal)]],
        colWidths=[194 * mm],
    )
    in_words_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(in_words_table)

    doc.build(story)
    return output_path


def _amount_in_words(amount: float) -> str:
    """Converts numerical amount into Indian Numbering System words."""
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