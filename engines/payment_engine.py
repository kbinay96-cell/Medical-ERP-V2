"""
engines/payment_engine.py

Payment Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." Mirrors
engines/receipt_engine.py's shape exactly, applied to the supplier side:
    - generates Payment Numbers (PYMT-0001)
    - runs FIFO auto-allocation against
      PaymentModel.get_outstanding_invoices_for_supplier()
    - computes advance_amount
    - consumes existing advance against a newly created Purchase Invoice
      (apply_advance_to_invoice() -- called by the Purchase Invoice flow,
      see Wiring Notes, Section 3)
    - orchestrates the audit-logged edit flow
    - enforces Cancel = mandatory reason, status-only
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.payment_validator import PaymentValidator
from models.payment_model import PaymentModel, PaymentSearchFilters

logger = logging.getLogger(__name__)

DEFAULT_PAYMENT_PREFIX = "PYMT-"
DEFAULT_PAYMENT_PADDING = 4  # PYMT-0001


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning("engines.date_engine not importable; PaymentEngine falls back to AD-only stamps.")
        return None


@dataclass
class PaymentAllocationDTO:
    payment_allocation_id: int
    purchase_invoice_id: int
    allocated_amount: float
    is_auto_allocated: bool
    remarks: Optional[str]
    internal_ref_number: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "PaymentAllocationDTO":
        known_fields = cls.__dataclass_fields__.keys()
        return cls(**{k: row.get(k) for k in known_fields})


@dataclass
class PaymentDTO:
    payment_id: int
    payment_number: str
    supplier_id: int
    payment_date_ad: Any
    payment_date_bs: str
    payment_mode: str
    amount: float
    allocated_amount: float
    advance_amount: float
    reference_no: Optional[str]
    bank_name: Optional[str]
    status: str
    cancellation_reason: Optional[str]
    remarks: Optional[str]
    is_deleted: bool
    created_by: int
    created_at_ad: Any
    created_at_bs: Optional[str]
    supplier_name: Optional[str] = None   # only populated by search() (joined)
    allocations: list[PaymentAllocationDTO] = None

    @classmethod
    def from_row(cls, row: dict, allocations: Optional[list[PaymentAllocationDTO]] = None) -> "PaymentDTO":
        known_fields = {f for f in cls.__dataclass_fields__.keys() if f != "allocations"}
        known = {k: row.get(k) for k in known_fields}
        return cls(**known, allocations=allocations or [])

    def to_dict(self) -> dict:
        return asdict(self)


class PaymentEngine:
    """Business-rule orchestration for the Payment module."""

    def __init__(
        self,
        model: Optional[PaymentModel] = None,
        date_engine: Optional[Any] = None,
        validator: Optional[PaymentValidator] = None,
    ) -> None:
        self._model = model or PaymentModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = validator or PaymentValidator(payment_number_exists_fn=self._payment_number_exists)

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #
    def _payment_number_exists(self, payment_number: str, exclude_id: Optional[int] = None) -> bool:
        existing = self._model.search(PaymentSearchFilters(search_text=payment_number, page_size=1))
        for row in existing:
            if row["payment_number"] == payment_number and row["payment_id"] != exclude_id:
                return True
        return False

    def _generate_payment_number(self) -> str:
        latest = self._model.search(PaymentSearchFilters(page_size=1, include_deleted=True))
        next_seq = 1
        if latest:
            try:
                next_seq = int(latest[0]["payment_number"].replace(DEFAULT_PAYMENT_PREFIX, "")) + 1
            except ValueError:
                next_seq = 1
        return f"{DEFAULT_PAYMENT_PREFIX}{next_seq:0{DEFAULT_PAYMENT_PADDING}d}"

    def _stamp_bs_date(self, ad_value: date) -> str:
        if self._date_engine is None:
            return ad_value.isoformat()
        try:
            return self._date_engine.ad_to_bs(ad_value)
        except Exception:
            logger.warning("BS conversion failed for %s; falling back to AD string.", ad_value)
            return ad_value.isoformat()

    def _run_fifo_allocation(self, supplier_id: int, amount: float) -> list[dict]:
        """Mirrors ReceiptEngine._run_fifo_allocation() exactly, for suppliers."""
        remaining = amount
        allocations: list[dict] = []
        open_invoices = self._model.get_outstanding_invoices_for_supplier(supplier_id)

        for invoice in open_invoices:
            if remaining <= 0:
                break
            outstanding = float(invoice["outstanding_amount"])
            take = min(remaining, outstanding)
            if take <= 0:
                continue
            allocations.append({
                "purchase_invoice_id": invoice["purchase_invoice_id"],
                "allocated_amount": round(take, 2),
                "is_auto_allocated": True,
                "remarks": None,
            })
            remaining = round(remaining - take, 2)

        return allocations

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_payment(
        self,
        supplier_id: int,
        payment_date_ad: date,
        payment_mode: str,
        amount: float,
        created_by: int,
        reference_no: Optional[str] = None,
        bank_name: Optional[str] = None,
        remarks: Optional[str] = None,
        manual_allocations: Optional[list[dict]] = None,   # None = auto FIFO; [] = pure advance; [...] = user-chosen
        status: str = "Posted",
    ) -> PaymentDTO:
        header_data = {
            "supplier_id": supplier_id,
            "payment_date_bs": self._stamp_bs_date(payment_date_ad),
            "payment_mode": payment_mode,
            "amount": amount,
            "reference_no": reference_no,
            "bank_name": bank_name,
            "remarks": remarks,
            "status": status,
        }
        header_result = self._validator.validate_header(header_data)
        if not header_result.is_valid:
            raise ValidationError("; ".join(header_result.errors))

        if manual_allocations is None:
            allocation_rows = self._run_fifo_allocation(supplier_id, amount)
        else:
            for row in manual_allocations:
                row.setdefault("is_auto_allocated", False)
            allocation_rows = manual_allocations

        open_invoices = self._model.get_outstanding_invoices_for_supplier(supplier_id)
        outstanding_lookup = {inv["purchase_invoice_id"]: float(inv["outstanding_amount"]) for inv in open_invoices}
        alloc_result = self._validator.validate_allocations(allocation_rows, amount, outstanding_lookup)
        if not alloc_result.is_valid:
            raise ValidationError("; ".join(alloc_result.errors))

        allocated_amount = round(sum(a["allocated_amount"] for a in allocation_rows), 2)
        advance_amount = round(amount - allocated_amount, 2)

        payment_number = self._generate_payment_number()
        number_result = self._validator.validate_payment_number_unique(payment_number)
        if not number_result.is_valid:
            raise DuplicateRecordError("; ".join(number_result.errors))

        now_ad = datetime.now(timezone.utc)
        header_data.update({
            "payment_number": payment_number,
            "payment_date_ad": payment_date_ad,
            "allocated_amount": allocated_amount,
            "advance_amount": advance_amount,
            "created_by": created_by,
            "created_at_ad": now_ad,
            "created_at_bs": self._stamp_bs_date(now_ad.date()),
        })

        payment_id = self._model.insert_with_allocations(header_data, allocation_rows)
        return self.get_by_id(payment_id)

    # ------------------------------------------------------------------ #
    # ADVANCE CONSUMPTION -- called by the Purchase Invoice flow (see Wiring Notes)
    # ------------------------------------------------------------------ #
    def apply_advance_to_invoice(self, supplier_id: int, purchase_invoice_id: int,
                                  requested_amount: float, applied_by: int) -> float:
        """
        Mirrors ReceiptEngine.apply_advance_to_invoice() exactly. NOT
        called automatically by this Engine -- PurchaseEngine's
        create_purchase_invoice() needs the hook described in Wiring
        Notes (Section 3).
        """
        remaining_to_apply = requested_amount
        applied_total = 0.0
        now_ad = datetime.now(timezone.utc)
        now_bs = self._stamp_bs_date(now_ad.date())

        available = self._model.get_available_advance_for_supplier(supplier_id)
        for advance_row in available:
            if remaining_to_apply <= 0:
                break
            usable = min(remaining_to_apply, float(advance_row["remaining_advance"]))
            if usable <= 0:
                continue
            self._model.insert_advance_usage(
                payment_id=advance_row["payment_id"],
                purchase_invoice_id=purchase_invoice_id,
                used_amount=round(usable, 2),
                used_by=applied_by,
                used_at_ad=now_ad,
                used_at_bs=now_bs,
            )
            applied_total = round(applied_total + usable, 2)
            remaining_to_apply = round(remaining_to_apply - usable, 2)

        return applied_total

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, payment_id: int) -> Optional[PaymentDTO]:
        row = self._model.get_by_id(payment_id)
        if row is None:
            return None
        allocation_rows = self._model.get_allocations_by_payment_id(payment_id)
        allocations = [PaymentAllocationDTO.from_row(r) for r in allocation_rows]
        return PaymentDTO.from_row(row, allocations=allocations)

    def search(self, filters: PaymentSearchFilters) -> list[PaymentDTO]:
        rows = self._model.search(filters)
        return [PaymentDTO.from_row(row) for row in rows]

    def get_outstanding_invoices(self, supplier_id: int) -> list[dict]:
        return self._model.get_outstanding_invoices_for_supplier(supplier_id)

    def get_audit_log(self, payment_id: int) -> list[dict]:
        return self._model.get_audit_log(payment_id)

    # ------------------------------------------------------------------ #
    # EDIT -- audit-logged, in-place
    # ------------------------------------------------------------------ #
    def edit_payment(
        self,
        payment_id: int,
        updated_by: int,
        header_changes: Optional[dict[str, Any]] = None,
        new_allocations: Optional[list[dict]] = None,
    ) -> PaymentDTO:
        existing = self._model.get_by_id(payment_id)
        if existing is None:
            raise RecordNotFoundError(f"Payment {payment_id} not found.")
        if existing["status"] == "Cancelled":
            raise ValidationError("A Cancelled Payment cannot be edited.")

        now_ad = datetime.now(timezone.utc)
        now_bs = self._stamp_bs_date(now_ad.date())
        audit_entries: list[dict] = []

        if header_changes:
            merged = {**existing, **header_changes}
            header_result = self._validator.validate_header(merged)
            if not header_result.is_valid:
                raise ValidationError("; ".join(header_result.errors))

            for field_name, new_value in header_changes.items():
                old_value = existing.get(field_name)
                if str(old_value) != str(new_value):
                    audit_entries.append({
                        "payment_id": payment_id, "changed_field": field_name,
                        "old_value": str(old_value) if old_value is not None else None,
                        "new_value": str(new_value) if new_value is not None else None,
                        "changed_by": updated_by, "changed_at_ad": now_ad, "changed_at_bs": now_bs,
                    })

        final_allocation_rows = None
        if new_allocations is not None:
            existing_allocations = {
                row["purchase_invoice_id"]: row for row in self._model.get_allocations_by_payment_id(payment_id)
            }
            open_invoices = self._model.get_outstanding_invoices_for_supplier(existing["supplier_id"])
            outstanding_lookup = {inv["purchase_invoice_id"]: float(inv["outstanding_amount"]) for inv in open_invoices}
            for invoice_id, old_alloc in existing_allocations.items():
                outstanding_lookup[invoice_id] = outstanding_lookup.get(invoice_id, 0) + float(old_alloc["allocated_amount"])

            effective_amount = header_changes.get("amount", existing["amount"]) if header_changes else existing["amount"]
            alloc_result = self._validator.validate_allocations(new_allocations, float(effective_amount), outstanding_lookup)
            if not alloc_result.is_valid:
                raise ValidationError("; ".join(alloc_result.errors))

            new_by_invoice = {row["purchase_invoice_id"]: row["allocated_amount"] for row in new_allocations}
            all_invoice_ids = set(existing_allocations) | set(new_by_invoice)
            for invoice_id in all_invoice_ids:
                old_amount = existing_allocations.get(invoice_id, {}).get("allocated_amount")
                new_amount = new_by_invoice.get(invoice_id)
                if old_amount != new_amount:
                    audit_entries.append({
                        "payment_id": payment_id,
                        "changed_field": f"allocation:purchase_invoice_id={invoice_id}",
                        "old_value": str(old_amount) if old_amount is not None else "removed",
                        "new_value": str(new_amount) if new_amount is not None else "removed",
                        "changed_by": updated_by, "changed_at_ad": now_ad, "changed_at_bs": now_bs,
                    })

            for row in new_allocations:
                row.setdefault("is_auto_allocated", False)
            final_allocation_rows = new_allocations

        if not audit_entries:
            return self.get_by_id(payment_id)

        self._model.insert_audit_log_entries(audit_entries)

        if header_changes:
            self._model.update_header_fields(payment_id, header_changes, updated_by, now_ad, now_bs)

        if final_allocation_rows is not None:
            self._model.replace_allocations(payment_id, final_allocation_rows)
            allocated_amount = round(sum(a["allocated_amount"] for a in final_allocation_rows), 2)
            amount = float(header_changes.get("amount", existing["amount"])) if header_changes else float(existing["amount"])
            advance_amount = round(amount - allocated_amount, 2)
            self._model.update_header_fields(
                payment_id,
                {"allocated_amount": allocated_amount, "advance_amount": advance_amount},
                updated_by, now_ad, now_bs,
            )

        return self.get_by_id(payment_id)

    # ------------------------------------------------------------------ #
    # CANCEL -- mandatory reason, status-only
    # ------------------------------------------------------------------ #
    def cancel_payment(self, payment_id: int, cancellation_reason: str, updated_by: int) -> PaymentDTO:
        existing = self._model.get_by_id(payment_id)
        if existing is None:
            raise RecordNotFoundError(f"Payment {payment_id} not found.")
        if existing["status"] == "Cancelled":
            raise ValidationError("This Payment is already Cancelled.")

        reason_result = self._validator.validate_cancellation(cancellation_reason)
        if not reason_result.is_valid:
            raise ValidationError("; ".join(reason_result.errors))

        now_ad = datetime.now(timezone.utc)
        self._model.cancel(
            payment_id=payment_id, cancellation_reason=cancellation_reason,
            updated_by=updated_by, updated_at_ad=now_ad, updated_at_bs=self._stamp_bs_date(now_ad.date()),
        )
        return self.get_by_id(payment_id)

    # ------------------------------------------------------------------ #
    # SOFT DELETE -- Draft only
    # ------------------------------------------------------------------ #
    def delete_draft(self, payment_id: int, deleted_by: int) -> None:
        existing = self._model.get_by_id(payment_id)
        if existing is None:
            raise RecordNotFoundError(f"Payment {payment_id} not found.")
        if existing["status"] != "Draft":
            raise ValidationError("Only a Draft Payment can be deleted. Use Cancel for a Posted payment.")

        now_ad = datetime.now(timezone.utc)
        self._model.soft_delete(
            payment_id=payment_id, deleted_by=deleted_by,
            deleted_at_ad=now_ad, deleted_at_bs=self._stamp_bs_date(now_ad.date()),
        )