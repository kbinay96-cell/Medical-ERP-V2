"""
engines/receipt_engine.py

Receipt Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - generates Receipt Numbers (RCPT-0001)
    - runs the FIFO auto-allocation algorithm against
      ReceiptModel.get_outstanding_invoices_for_customer()
    - computes advance_amount (amount left over after every open
      invoice is satisfied)
    - consumes existing advance against a newly created Sale Invoice
      (apply_advance_to_invoice() -- called by the Sale Invoice flow,
      see Wiring Notes, Section 3)
    - orchestrates the audit-logged edit flow: for ANY header field or
      allocation change, writes receipt_audit_log rows FIRST, then
      applies the change -- never the other way around
    - enforces Cancel = mandatory reason, status-only (never deletes
      allocations; they simply stop counting once status='Cancelled',
      per ReceiptModel's queries already filtering on that)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.receipt_validator import ReceiptValidator
from models.receipt_model import ReceiptModel, ReceiptSearchFilters

logger = logging.getLogger(__name__)

DEFAULT_RECEIPT_PREFIX = "RCPT-"
DEFAULT_RECEIPT_PADDING = 4  # RCPT-0001


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning("engines.date_engine not importable; ReceiptEngine falls back to AD-only stamps.")
        return None


@dataclass
class ReceiptAllocationDTO:
    receipt_allocation_id: int
    sale_invoice_id: int
    allocated_amount: float
    is_auto_allocated: bool
    remarks: Optional[str]
    invoice_number: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "ReceiptAllocationDTO":
        known_fields = cls.__dataclass_fields__.keys()
        return cls(**{k: row.get(k) for k in known_fields})


@dataclass
class ReceiptDTO:
    receipt_id: int
    receipt_number: str
    customer_id: int
    receipt_date_ad: Any
    receipt_date_bs: str
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
    customer_name: Optional[str] = None    # only populated by search() (joined)
    allocations: list[ReceiptAllocationDTO] = None

    @classmethod
    def from_row(cls, row: dict, allocations: Optional[list[ReceiptAllocationDTO]] = None) -> "ReceiptDTO":
        known_fields = {f for f in cls.__dataclass_fields__.keys() if f != "allocations"}
        known = {k: row.get(k) for k in known_fields}
        return cls(**known, allocations=allocations or [])

    def to_dict(self) -> dict:
        return asdict(self)


class ReceiptEngine:
    """Business-rule orchestration for the Receipt module."""

    def __init__(
        self,
        model: Optional[ReceiptModel] = None,
        date_engine: Optional[Any] = None,
        validator: Optional[ReceiptValidator] = None,
    ) -> None:
        self._model = model or ReceiptModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = validator or ReceiptValidator(receipt_number_exists_fn=self._receipt_number_exists)

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #
    def _receipt_number_exists(self, receipt_number: str, exclude_id: Optional[int] = None) -> bool:
        existing = self._model.search(ReceiptSearchFilters(search_text=receipt_number, page_size=1))
        for row in existing:
            if row["receipt_number"] == receipt_number and row["receipt_id"] != exclude_id:
                return True
        return False

    def _generate_receipt_number(self) -> str:
        latest = self._model.search(ReceiptSearchFilters(page_size=1, include_deleted=True))
        next_seq = 1
        if latest:
            try:
                next_seq = int(latest[0]["receipt_number"].replace(DEFAULT_RECEIPT_PREFIX, "")) + 1
            except ValueError:
                next_seq = 1
        return f"{DEFAULT_RECEIPT_PREFIX}{next_seq:0{DEFAULT_RECEIPT_PADDING}d}"

    def _stamp_bs_date(self, ad_value: date) -> str:
        if self._date_engine is None:
            return ad_value.isoformat()
        try:
            return self._date_engine.ad_to_bs(ad_value)
        except Exception:
            logger.warning("BS conversion failed for %s; falling back to AD string.", ad_value)
            return ad_value.isoformat()

    def _run_fifo_allocation(self, customer_id: int, amount: float) -> list[dict]:
        """
        Walks get_outstanding_invoices_for_customer() (already ordered
        oldest-first) and greedily fills each invoice's outstanding until
        `amount` is exhausted or invoices run out. Returns a list of
        {"sale_invoice_id", "allocated_amount", "is_auto_allocated": True}.
        """
        remaining = amount
        allocations: list[dict] = []
        open_invoices = self._model.get_outstanding_invoices_for_customer(customer_id)

        for invoice in open_invoices:
            if remaining <= 0:
                break
            outstanding = float(invoice["outstanding_amount"])
            take = min(remaining, outstanding)
            if take <= 0:
                continue
            allocations.append({
                "sale_invoice_id": invoice["sale_invoice_id"],
                "allocated_amount": round(take, 2),
                "is_auto_allocated": True,
                "remarks": None,
            })
            remaining = round(remaining - take, 2)

        return allocations

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_receipt(
        self,
        customer_id: int,
        receipt_date_ad: date,
        payment_mode: str,
        amount: float,
        created_by: int,
        reference_no: Optional[str] = None,
        bank_name: Optional[str] = None,
        remarks: Optional[str] = None,
        manual_allocations: Optional[list[dict]] = None,   # None = auto FIFO; [] = pure advance, no allocation; [...] = user-chosen
        status: str = "Posted",
    ) -> ReceiptDTO:
        header_data = {
            "customer_id": customer_id,
            "receipt_date_bs": self._stamp_bs_date(receipt_date_ad),
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

        # Decide allocations: FIFO by default, or the caller's explicit choice
        if manual_allocations is None:
            allocation_rows = self._run_fifo_allocation(customer_id, amount)
        else:
            for row in manual_allocations:
                row.setdefault("is_auto_allocated", False)
            allocation_rows = manual_allocations

        # Validate manual/mixed allocations against live outstanding
        # (FIFO output is validated too, defensively -- cheap and safe)
        open_invoices = self._model.get_outstanding_invoices_for_customer(customer_id)
        outstanding_lookup = {inv["sale_invoice_id"]: float(inv["outstanding_amount"]) for inv in open_invoices}
        alloc_result = self._validator.validate_allocations(allocation_rows, amount, outstanding_lookup)
        if not alloc_result.is_valid:
            raise ValidationError("; ".join(alloc_result.errors))

        allocated_amount = round(sum(a["allocated_amount"] for a in allocation_rows), 2)
        advance_amount = round(amount - allocated_amount, 2)

        receipt_number = self._generate_receipt_number()
        number_result = self._validator.validate_receipt_number_unique(receipt_number)
        if not number_result.is_valid:
            raise DuplicateRecordError("; ".join(number_result.errors))

        now_ad = datetime.now(timezone.utc)
        header_data.update({
            "receipt_number": receipt_number,
            "receipt_date_ad": receipt_date_ad,
            "allocated_amount": allocated_amount,
            "advance_amount": advance_amount,
            "created_by": created_by,
            "created_at_ad": now_ad,
            "created_at_bs": self._stamp_bs_date(now_ad.date()),
        })

        receipt_id = self._model.insert_with_allocations(header_data, allocation_rows)
        return self.get_by_id(receipt_id)

    # ------------------------------------------------------------------ #
    # ADVANCE CONSUMPTION -- called by the Sale Invoice flow (see Wiring Notes)
    # ------------------------------------------------------------------ #
    def apply_advance_to_invoice(self, customer_id: int, sale_invoice_id: int,
                                  requested_amount: float, applied_by: int) -> float:
        """
        Consumes the customer's available advance (oldest receipt first,
        via get_available_advance_for_customer()) against a NEW invoice,
        up to `requested_amount` or however much advance actually
        exists, whichever is smaller. Returns the amount actually
        applied (caller reduces the invoice's own outstanding by this).

        NOT called automatically by this Engine -- Sale Invoice creation
        lives in SaleEngine, which was built before Receipt existed in
        this project's timeline. Wiring Notes (Section 3) describes the
        one-line hook SaleEngine.create_sale_invoice() needs to call this
        after saving a new invoice, offering any available advance to
        the customer automatically.
        """
        remaining_to_apply = requested_amount
        applied_total = 0.0
        now_ad = datetime.now(timezone.utc)
        now_bs = self._stamp_bs_date(now_ad.date())

        available = self._model.get_available_advance_for_customer(customer_id)
        for advance_row in available:
            if remaining_to_apply <= 0:
                break
            usable = min(remaining_to_apply, float(advance_row["remaining_advance"]))
            if usable <= 0:
                continue
            self._model.insert_advance_usage(
                receipt_id=advance_row["receipt_id"],
                sale_invoice_id=sale_invoice_id,
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
    def get_by_id(self, receipt_id: int) -> Optional[ReceiptDTO]:
        row = self._model.get_by_id(receipt_id)
        if row is None:
            return None
        allocation_rows = self._model.get_allocations_by_receipt_id(receipt_id)
        allocations = [ReceiptAllocationDTO.from_row(r) for r in allocation_rows]
        return ReceiptDTO.from_row(row, allocations=allocations)

    def search(self, filters: ReceiptSearchFilters) -> list[ReceiptDTO]:
        rows = self._model.search(filters)
        return [ReceiptDTO.from_row(row) for row in rows]

    def get_outstanding_invoices(self, customer_id: int) -> list[dict]:
        """Pass-through for the Screen's manual-allocation picker."""
        return self._model.get_outstanding_invoices_for_customer(customer_id)

    def get_audit_log(self, receipt_id: int) -> list[dict]:
        return self._model.get_audit_log(receipt_id)

    # ------------------------------------------------------------------ #
    # EDIT -- audit-logged, in-place (confirmed design, NOT append-only)
    # ------------------------------------------------------------------ #
    def edit_receipt(
        self,
        receipt_id: int,
        updated_by: int,
        header_changes: Optional[dict[str, Any]] = None,   # e.g. {"payment_mode": "Bank Transfer", "reference_no": "TXN999"}
        new_allocations: Optional[list[dict]] = None,       # None = allocations unchanged; a list = full replacement set
    ) -> ReceiptDTO:
        existing = self._model.get_by_id(receipt_id)
        if existing is None:
            raise RecordNotFoundError(f"Receipt {receipt_id} not found.")
        if existing["status"] == "Cancelled":
            raise ValidationError("A Cancelled Receipt cannot be edited.")

        now_ad = datetime.now(timezone.utc)
        now_bs = self._stamp_bs_date(now_ad.date())
        audit_entries: list[dict] = []

        # --- Header field changes: validate the WOULD-BE state, log each diff ---
        if header_changes:
            merged = {**existing, **header_changes}
            header_result = self._validator.validate_header(merged)
            if not header_result.is_valid:
                raise ValidationError("; ".join(header_result.errors))

            for field_name, new_value in header_changes.items():
                old_value = existing.get(field_name)
                if str(old_value) != str(new_value):
                    audit_entries.append({
                        "receipt_id": receipt_id, "changed_field": field_name,
                        "old_value": str(old_value) if old_value is not None else None,
                        "new_value": str(new_value) if new_value is not None else None,
                        "changed_by": updated_by, "changed_at_ad": now_ad, "changed_at_bs": now_bs,
                    })

        # --- Allocation changes: recompute outstanding EXCLUDING this receipt's
        #     own current allocations (so re-targeting the same invoice at a
        #     different amount doesn't falsely look over-limit) ---
        final_allocation_rows = None
        if new_allocations is not None:
            existing_allocations = {
                row["sale_invoice_id"]: row for row in self._model.get_allocations_by_receipt_id(receipt_id)
            }
            open_invoices = self._model.get_outstanding_invoices_for_customer(existing["customer_id"])
            outstanding_lookup = {inv["sale_invoice_id"]: float(inv["outstanding_amount"]) for inv in open_invoices}
            # Add back this receipt's own existing allocation for each invoice,
            # since get_outstanding_invoices_for_customer() already subtracted it.
            for invoice_id, old_alloc in existing_allocations.items():
                outstanding_lookup[invoice_id] = outstanding_lookup.get(invoice_id, 0) + float(old_alloc["allocated_amount"])

            effective_amount = header_changes.get("amount", existing["amount"]) if header_changes else existing["amount"]
            alloc_result = self._validator.validate_allocations(new_allocations, float(effective_amount), outstanding_lookup)
            if not alloc_result.is_valid:
                raise ValidationError("; ".join(alloc_result.errors))

            new_by_invoice = {row["sale_invoice_id"]: row["allocated_amount"] for row in new_allocations}
            all_invoice_ids = set(existing_allocations) | set(new_by_invoice)
            for invoice_id in all_invoice_ids:
                old_amount = existing_allocations.get(invoice_id, {}).get("allocated_amount")
                new_amount = new_by_invoice.get(invoice_id)
                if old_amount != new_amount:
                    audit_entries.append({
                        "receipt_id": receipt_id,
                        "changed_field": f"allocation:sale_invoice_id={invoice_id}",
                        "old_value": str(old_amount) if old_amount is not None else "removed",
                        "new_value": str(new_amount) if new_amount is not None else "removed",
                        "changed_by": updated_by, "changed_at_ad": now_ad, "changed_at_bs": now_bs,
                    })

            for row in new_allocations:
                row.setdefault("is_auto_allocated", False)
            final_allocation_rows = new_allocations

        # --- Nothing actually changed? Don't touch the audit log or the record. ---
        if not audit_entries:
            return self.get_by_id(receipt_id)

        # --- Audit log written FIRST, then the actual update applied ---
        self._model.insert_audit_log_entries(audit_entries)

        if header_changes:
            self._model.update_header_fields(receipt_id, header_changes, updated_by, now_ad, now_bs)

        if final_allocation_rows is not None:
            self._model.replace_allocations(receipt_id, final_allocation_rows)
            allocated_amount = round(sum(a["allocated_amount"] for a in final_allocation_rows), 2)
            amount = float(header_changes.get("amount", existing["amount"])) if header_changes else float(existing["amount"])
            advance_amount = round(amount - allocated_amount, 2)
            self._model.update_header_fields(
                receipt_id,
                {"allocated_amount": allocated_amount, "advance_amount": advance_amount},
                updated_by, now_ad, now_bs,
            )

        return self.get_by_id(receipt_id)

    # ------------------------------------------------------------------ #
    # CANCEL -- mandatory reason, status-only (allocations simply stop
    # counting -- ReceiptModel's queries already filter status != 'Cancelled')
    # ------------------------------------------------------------------ #
    def cancel_receipt(self, receipt_id: int, cancellation_reason: str, updated_by: int) -> ReceiptDTO:
        existing = self._model.get_by_id(receipt_id)
        if existing is None:
            raise RecordNotFoundError(f"Receipt {receipt_id} not found.")
        if existing["status"] == "Cancelled":
            raise ValidationError("This Receipt is already Cancelled.")

        reason_result = self._validator.validate_cancellation(cancellation_reason)
        if not reason_result.is_valid:
            raise ValidationError("; ".join(reason_result.errors))

        now_ad = datetime.now(timezone.utc)
        self._model.cancel(
            receipt_id=receipt_id, cancellation_reason=cancellation_reason,
            updated_by=updated_by, updated_at_ad=now_ad, updated_at_bs=self._stamp_bs_date(now_ad.date()),
        )
        return self.get_by_id(receipt_id)

    # ------------------------------------------------------------------ #
    # SOFT DELETE -- Draft only
    # ------------------------------------------------------------------ #
    def delete_draft(self, receipt_id: int, deleted_by: int) -> None:
        existing = self._model.get_by_id(receipt_id)
        if existing is None:
            raise RecordNotFoundError(f"Receipt {receipt_id} not found.")
        if existing["status"] != "Draft":
            raise ValidationError("Only a Draft Receipt can be deleted. Use Cancel for a Posted receipt.")

        now_ad = datetime.now(timezone.utc)
        self._model.soft_delete(
            receipt_id=receipt_id, deleted_by=deleted_by,
            deleted_at_ad=now_ad, deleted_at_bs=self._stamp_bs_date(now_ad.date()),
        )