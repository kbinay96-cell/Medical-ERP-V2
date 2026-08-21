# engines/purchase_engine.py
from __future__ import annotations
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional, List

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError

from models.purchase_invoice_model import PurchaseInvoiceModel, PurchaseInvoiceSearchFilters
from engines.purchase_validator import PurchaseValidator

logger = logging.getLogger(__name__)


@dataclass
class PurchaseInvoiceLineDTO:
    item_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    qty: float
    free_qty: float
    purchase_rate: float
    discount_percent: float
    cc_percent: float = 0.0
    mrp: float = 0.0
    sale_rate: float = 0.0
    # computed/output fields
    discount_amount: float = 0.0
    cc_amount: float = 0.0
    freight_allocated: float = 0.0
    other_charges_allocated: float = 0.0
    landing_cost_per_unit: float = 0.0
    item_batch_id: Optional[int] = None


@dataclass
class PurchaseInvoiceDTO:
    purchase_invoice_id: Optional[int]
    internal_ref_number: str
    invoice_number: str
    supplier_id: int
    invoice_date_bs: str
    total_qty: float
    total_gross_amount: float
    total_discount_amount: float
    total_cc_amount: float
    total_freight_amount: float
    total_other_charges: float
    grand_total: float
    status: str
    lines: List[PurchaseInvoiceLineDTO] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class PurchaseEngine:
    def __init__(
        self,
        model: PurchaseInvoiceModel,
        date_engine,
        settings_engine,
        item_engine,
        purchase_order_engine,
        country_tax_lookup_fn,
        manufacturer_lookup_fn,
    ) -> None:
        self._model = model
        self._date_engine = date_engine
        self._settings_engine = settings_engine
        self._item_engine = item_engine
        self._purchase_order_engine = purchase_order_engine
        self._country_tax_lookup = country_tax_lookup_fn
        self._manufacturer_lookup = manufacturer_lookup_fn

    def _now_ad(self) -> datetime:
        return datetime.now()

    def _now_bs(self) -> str:
        try:
            return self._date_engine.ad_to_bs(self._now_ad().date())
        except Exception:
            return ""

    def generate_internal_ref_number(self) -> str:
        prefix = self._settings_engine.get_setting("purchase.invoice_prefix", "PINV-")
        last = self._model.get_last_internal_ref_sequence(prefix)
        next_seq = (last or 0) + 1
        return f"{prefix}{next_seq:04d}"

    def _resolve_cc_percent(self, item_id: int) -> float:
        try:
            # Find manufacturer via injected lookup: first get manufacturer_id for item via ItemModel
            # We'll lazy-import ItemModel to avoid circular imports
            from models.item_model import ItemModel

            im = ItemModel()
            item_row = im.get_by_id(item_id)
            if not item_row:
                return 0.0
            manufacturer_id = item_row.get("manufacturer_id")
            if not manufacturer_id:
                return 0.0
            # manufacturer_lookup_fn returns manufacturer data (including country) or None
            manufacturer = self._manufacturer_lookup(manufacturer_id)
            if not manufacturer:
                return 0.0
            country = manufacturer.get("country")
            if not country:
                return 0.0
            cc, _ = self._country_tax_lookup(country)  # returns (vat_percent, custom_percent)
            return float(cc or 0.0)
        except Exception:
            return 0.0

    def _allocate_invoice_level_charges(self, lines: List[PurchaseInvoiceLineDTO], total_freight: float, total_other: float) -> List[PurchaseInvoiceLineDTO]:
        total_units = sum((line.qty + line.free_qty) for line in lines)
        if total_units <= 0:
            # nothing to allocate
            return lines
        for line in lines:
            share = (line.qty + line.free_qty) / total_units
            line.freight_allocated = round(total_freight * share, 4)
            line.other_charges_allocated = round(total_other * share, 4)
        return lines

    def _calculate_line_amounts(self, line: PurchaseInvoiceLineDTO) -> PurchaseInvoiceLineDTO:
        # discount on paid qty only
        paid_value = line.qty * line.purchase_rate
        line.discount_amount = round(paid_value * (line.discount_percent / 100.0), 4)

        # cc basis: free_qty * declared_customs_value_per_unit (use purchase_rate of paid units)
        declared_customs_value_per_unit = line.purchase_rate or 0.0
        line.cc_amount = round((line.free_qty * declared_customs_value_per_unit) * (line.cc_percent / 100.0), 4)

        # landing cost per unit = (paid_value - discount + cc + freight_allocated + other_allocated) / total_units
        total_units = (line.qty + line.free_qty) or 1.0
        numerator = (paid_value - line.discount_amount + line.cc_amount + line.freight_allocated + line.other_charges_allocated)
        line.landing_cost_per_unit = round(numerator / total_units, 4)

        return line

    def create_purchase_invoice(self, payload: dict[str, Any], current_user_id: int) -> PurchaseInvoiceDTO:
        # 1. Validate header
        ok, err = PurchaseValidator.validate_invoice_header(payload)
        if not ok:
            raise ValidationError([err])

        raw_lines = payload.get("lines", [])
        if not isinstance(raw_lines, list) or len(raw_lines) == 0:
            raise ValidationError(["Invoice must include at least one line."])

        # 1b: Validate each line
        lines_dto: List[PurchaseInvoiceLineDTO] = []
        for idx, l in enumerate(raw_lines):
            ok, err = PurchaseValidator.validate_invoice_line(l)
            if not ok:
                raise ValidationError([f"Line {idx+1}: {err}"])
            ok, err = PurchaseValidator.validate_free_qty_rate(l)
            if not ok:
                raise ValidationError([f"Line {idx+1}: {err}"])

            line_dto = PurchaseInvoiceLineDTO(
                item_id=int(l["item_id"]),
                batch_no=str(l["batch_no"]),
                expiry_month=int(l["expiry_month"]),
                expiry_year=int(l["expiry_year"]),
                qty=float(l.get("qty", 0) or 0),
                free_qty=float(l.get("free_qty", 0) or 0),
                purchase_rate=float(l.get("purchase_rate", 0) or 0),
                discount_percent=float(l.get("discount_percent", 0) or 0),
                cc_percent=float(l.get("cc_percent", 0) or 0),
                mrp=float(l.get("mrp", 0) or 0),
                sale_rate=float(l.get("sale_rate", 0) or 0),
            )
            # Resolve CC percent if not provided
            if not line_dto.cc_percent or line_dto.cc_percent == 0:
                line_dto.cc_percent = self._resolve_cc_percent(line_dto.item_id)
            lines_dto.append(line_dto)

        # 4. Allocate invoice-level freight/other charges (if present in payload)
        total_freight = float(payload.get("total_freight_amount", 0) or 0)
        total_other = float(payload.get("total_other_charges", 0) or 0)
        lines_dto = self._allocate_invoice_level_charges(lines_dto, total_freight, total_other)

        # 5. Calculate amounts per line
        total_qty = 0.0
        total_gross = 0.0
        total_discount = 0.0
        total_cc = 0.0
        for line in lines_dto:
            line = self._calculate_line_amounts(line)
            total_qty += line.qty + line.free_qty
            total_gross += (line.qty * line.purchase_rate)
            total_discount += line.discount_amount
            total_cc += line.cc_amount

        grand_total = round(total_gross - total_discount + total_cc + total_freight + total_other, 4)

        # 6. Duplicate check
        supplier_id = payload.get("supplier_id")
        invoice_number = payload.get("invoice_number")
        if self._model.exists_by_supplier_and_billno(supplier_id, invoice_number, exclude_id=None):
            raise DuplicateRecordError(f"Supplier {supplier_id} already has an invoice with number {invoice_number}.")

        # 7. Insert purchase_invoice header
        header = {
            "invoice_number": invoice_number,
            "internal_ref_number": payload.get("internal_ref_number") or self.generate_internal_ref_number(),
            "supplier_id": supplier_id,
            "purchase_order_id": payload.get("purchase_order_id"),
            "invoice_date_ad": payload.get("invoice_date_ad") or self._now_ad().date(),
            "invoice_date_bs": payload.get("invoice_date_bs") or self._now_bs(),
            "total_qty": total_qty,
            "total_gross_amount": total_gross,
            "total_discount_amount": total_discount,
            "total_cc_amount": total_cc,
            "total_freight_amount": total_freight,
            "total_other_charges": total_other,
            "grand_total": grand_total,
            "status": payload.get("status", "Posted"),
            "remarks": payload.get("remarks"),
            "created_by": current_user_id,
            "created_at_ad": self._now_ad(),
            "created_at_bs": self._now_bs(),
        }

        with self._model.insert_invoice.__self__ if hasattr(self._model.insert_invoice, "__self__") else self._model as _ignore:
            # Insert header via model
            new_invoice_id = self._model.insert_invoice(header)

        # 8. For each line: insert line row and call ItemEngine.add_batch
        inserted_line_ids = []
        for line in lines_dto:
            item_line_data = {
                "purchase_invoice_id": new_invoice_id,
                "item_id": line.item_id,
                "batch_no": line.batch_no,
                "expiry_month": line.expiry_month,
                "expiry_year": line.expiry_year,
                "qty": line.qty,
                "free_qty": line.free_qty,
                "purchase_rate": line.purchase_rate,
                "discount_percent": line.discount_percent,
                "discount_amount": line.discount_amount,
                "cc_percent": line.cc_percent,
                "cc_amount": line.cc_amount,
                "freight_amount_allocated": line.freight_allocated,
                "other_charges_allocated": line.other_charges_allocated,
                "landing_cost_per_unit": line.landing_cost_per_unit,
                "mrp": line.mrp,
                "sale_rate": line.sale_rate,
                "remarks": None,
            }
            invoice_item_id = self._model.insert_invoice_item(new_invoice_id, item_line_data)
            # Build batch payload for ItemEngine.add_batch()
            batch_payload = {
                "batch_no": line.batch_no,
                "expiry_month": line.expiry_month,
                "expiry_year": line.expiry_year,
                "batch_qty": (line.qty + line.free_qty),
                "batch_purchase_rate": line.purchase_rate,
                "remarks": None,
            }
            # Call ItemEngine to create batch + stock ledger
            try:
                item_batch_id = self._item_engine.add_batch(
                    item_id=line.item_id,
                    batch_payload=batch_payload,
                    current_user_id=current_user_id,
                    transaction_type="PURCHASE",
                    reference_type="purchase_invoice",
                    reference_id=new_invoice_id,
                )
            except Exception as exc:
                logger.exception("Failed to create item batch for invoice line; rolling up error.")
                # We do not attempt DB rollback here; let caller handle failures / ensure transactions at a higher level if needed.
                raise

            # Stamp back to invoice item
            self._model.update_invoice_item_batch_link(invoice_item_id, item_batch_id)
            line.item_batch_id = item_batch_id
            inserted_line_ids.append(invoice_item_id)

        # 9. If linked to a PO, mark PO received via injected engine
        po_id = payload.get("purchase_order_id")
        if po_id:
            try:
                # The PurchaseOrderEngine is expected to offer mark_received()
                self._purchase_order_engine.mark_received(po_id, current_user_id)
            except Exception:
                # Log but do not fail the invoice creation (safety: invoice must be created)
                logger.exception("Failed to mark linked purchase order as Received: %s", po_id)

        # Build DTO to return
        created_invoice = PurchaseInvoiceDTO(
            purchase_invoice_id=new_invoice_id,
            internal_ref_number=header["internal_ref_number"],
            invoice_number=invoice_number,
            supplier_id=supplier_id,
            invoice_date_bs=header["invoice_date_bs"],
            total_qty=total_qty,
            total_gross_amount=total_gross,
            total_discount_amount=total_discount,
            total_cc_amount=total_cc,
            total_freight_amount=total_freight,
            total_other_charges=total_other,
            grand_total=grand_total,
            status=header["status"],
            lines=lines_dto,
        )
        return created_invoice

    def get_purchase_invoice(self, purchase_invoice_id: int, include_deleted: bool = False) -> Optional[PurchaseInvoiceDTO]:
        row = self._model.get_by_id(purchase_invoice_id, include_deleted=include_deleted)
        if not row:
            return None
        items = self._model.get_items_by_invoice(purchase_invoice_id)
        lines = []
        for r in items:
            l = PurchaseInvoiceLineDTO(
                item_id=r.get("item_id"),
                batch_no=r.get("batch_no"),
                expiry_month=r.get("expiry_month"),
                expiry_year=r.get("expiry_year"),
                qty=float(r.get("qty") or 0),
                free_qty=float(r.get("free_qty") or 0),
                purchase_rate=float(r.get("purchase_rate") or 0),
                discount_percent=float(r.get("discount_percent") or 0),
                cc_percent=float(r.get("cc_percent") or 0),
                mrp=float(r.get("mrp") or 0),
                sale_rate=float(r.get("sale_rate") or 0),
            )
            lines.append(l)
        dto = PurchaseInvoiceDTO(
            purchase_invoice_id=row.get("purchase_invoice_id"),
            internal_ref_number=row.get("internal_ref_number"),
            invoice_number=row.get("invoice_number"),
            supplier_id=row.get("supplier_id"),
            invoice_date_bs=row.get("invoice_date_bs"),
            total_qty=float(row.get("total_qty") or 0),
            total_gross_amount=float(row.get("total_gross_amount") or 0),
            total_discount_amount=float(row.get("total_discount_amount") or 0),
            total_cc_amount=float(row.get("total_cc_amount") or 0),
            total_freight_amount=float(row.get("total_freight_amount") or 0),
            total_other_charges=float(row.get("total_other_charges") or 0),
            grand_total=float(row.get("grand_total") or 0),
            status=row.get("status"),
            lines=lines,
        )
        return dto

    def search_purchase_invoices(self, **kwargs):
        # Bridge to model.search() using provided filters
        filters = PurchaseInvoiceSearchFilters(
            search_text=kwargs.get("search_text"),
            supplier_id=kwargs.get("supplier_id"),
            status=kwargs.get("status"),
            date_from_ad=kwargs.get("date_from_ad"),
            date_to_ad=kwargs.get("date_to_ad"),
            include_deleted=kwargs.get("include_deleted", False),
            page=kwargs.get("page", 1),
            page_size=kwargs.get("page_size", 50),
        )
        rows, total = self._model.search(filters)
        # Convert rows (dicts) to DTOs minimally if desired, but for efficiency we can return raw rows + total
        return rows, total

    def cancel_purchase_invoice(self, purchase_invoice_id: int, current_user_id: int, reason: str) -> None:
        # Soft-delete via model
        from datetime import datetime
        deleted_at_ad = datetime.now()
        deleted_at_bs = self._now_bs()
        self._model.soft_delete(purchase_invoice_id, deleted_by=current_user_id, deleted_at_ad=deleted_at_ad, deleted_at_bs=deleted_at_bs)