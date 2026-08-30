# Payment Module — Part 3: Screens + Combined Blueprint JSON Update

**Project:** Medical ERP V2
**Layer:** Screens ("No SQL. No business logic." — collect input, call the Engine, render whatever DTO comes back)
**Depends on Part 1+2:** `payment`/`payment_allocation`/`payment_advance_usage`/`payment_audit_log` tables, `models/payment_model.py`, `engines/payment_engine.py`, `engines/payment_validator.py`

---

## 1. Screens Layer (`screens/`)

### 1.1 `screens/payment_form_screen.py` (the core screen — Add AND Edit)

```python
"""
screens/payment_form_screen.py

Payment Add/Edit Screen/Controller - Medical ERP V2

Mirrors screens/receipt_form_screen.py exactly, applied to the supplier
side. Responsibilities (and ONLY these -- "No SQL. No business logic."):
    - Supplier picker (searchable combo).
    - Header fields: Payment Date (BS, defaults to today), Payment Mode
      (combo: Cash/Bank Transfer/Cheque/Card/Other), Amount, Reference
      No. (shown/required only when Payment Mode needs it), Bank Name,
      Remarks.
    - On Supplier + Amount entered: calls engine.get_outstanding_invoices()
      and shows a FIFO-preview allocation grid, same override behavior
      as Receipt's grid -- uncheck/retype/add rows, leftover shown live
      as "Advance: Rs {x}".
    - Save (new): engine.create_payment(...).
    - Save (editing an existing Posted payment): engine.edit_payment(
      payment_id, updated_by, header_changes={...only changed fields...},
      new_allocations=... if the grid was touched, else None).
    - Surfaces ValidationError messages back to the user.
    """
    def __init__(self, parent, engine: "PaymentEngine", supplier_engine, payment_id: Optional[int] = None): ...
    def _load_existing_payment(self) -> None: ...
    def _on_supplier_or_amount_changed(self) -> None: ...
    def _load_fifo_preview(self, supplier_id: int, amount: float) -> None: ...
    def _populate_allocation_grid(self, allocation_rows: list[dict]) -> None: ...
    def _on_allocation_row_changed(self, row_index: int) -> None: ...
    def _collect_header_changes(self) -> dict: ...
    def _collect_allocations(self) -> list[dict]: ...
    def _on_save_clicked(self) -> None: ...
```

### 1.2 `screens/payment_list_screen.py`

```python
class PaymentListScreen(QWidget):
    """List/search/filter -- mirrors screens/receipt_list_screen.py's
    shape exactly. Filters: Supplier, Payment Mode, Status, Date range.
    Actions:
        - View: read-only detail (allocations with invoice numbers,
          advance_amount, link to "View Audit Log").
        - Edit: ONLY for status='Posted' -> opens
          PaymentFormScreen(payment_id=...).
        - Cancel: ONLY for status='Posted'. Opens the SAME shared
          screens/cancellation_reason_dialog.py (built in Sale Return
          Part 3, already reused by Purchase Return and Receipt) ->
          calls engine.cancel_payment(payment_id, cancellation_reason,
          updated_by).
        - Delete: ONLY visible/enabled for status='Draft' rows.
    """
    def __init__(self, parent, engine: "PaymentEngine"): ...
    def refresh(self) -> None: ...
    def _on_view_clicked(self, payment_id: int) -> None: ...
    def _on_edit_clicked(self, payment_id: int) -> None: ...
    def _on_cancel_clicked(self, payment_id: int) -> None: ...
    def _on_delete_clicked(self, payment_id: int) -> None: ...
    def _on_view_audit_log_clicked(self, payment_id: int) -> None: ...
```

### 1.3 `screens/payment_audit_log_dialog.py` (new, small)

```python
class PaymentAuditLogDialog(QDialog):
    """Read-only. Calls engine.get_audit_log(payment_id) and shows
    Changed Field | Old Value | New Value | Changed By | Changed At (BS).
    Mirrors screens/receipt_audit_log_dialog.py exactly."""
    def __init__(self, parent, engine: "PaymentEngine", payment_id: int): ...
```

### 1.4 Dashboard Wiring

`screens/dashboard_screen.py` — add **"Payment"** entry to the existing **"Accounts"** sidebar group created in Receipt Part 3 (now: Receipt, Payment). `PaymentListScreen`'s own "+ New Payment" toolbar button opens `PaymentFormScreen` with no `payment_id` (Add mode).

---

## 2. Wiring Checklist

```python
# Construction order -- PaymentEngine has NO required external engine
# dependency, mirrors ReceiptEngine:

from models.payment_model import PaymentModel
from engines.payment_engine import PaymentEngine

payment_engine = PaymentEngine(model=PaymentModel())

payment_list_screen = PaymentListScreen(parent=dashboard, engine=payment_engine)
payment_form_screen = PaymentFormScreen(
    parent=dashboard,
    engine=payment_engine,
    supplier_engine=supplier_engine_instance,   # for the Supplier picker's search
)

# ---------------------------------------------------------------- #
# REQUIRED cross-module hook -- mirrors Receipt's sale_engine.py hook:
# ---------------------------------------------------------------- #
#
# In engines/purchase_engine.py, inside PurchaseEngine.create_purchase_invoice(),
# AFTER the invoice is successfully saved, add:
#
#     applied_advance = self._payment_engine.apply_advance_to_invoice(
#         supplier_id=supplier_id,
#         purchase_invoice_id=new_purchase_invoice_id,
#         requested_amount=grand_total,
#         applied_by=current_user_id,
#     )
#
# PurchaseEngine's constructor needs ONE new optional injected
# dependency, `payment_engine=None`:
#
#     purchase_engine = PurchaseEngine(
#         ...,  # every existing argument unchanged (including
#               # purchase_order_engine from Purchase Module Part 3)
#         payment_engine=payment_engine,   # NEW, optional
#     )
#
# If payment_engine is None, PurchaseEngine simply skips the
# advance-apply call -- no crash, no behavior change to existing
# Purchase Module functionality.
```

---

## 3. Suggested Build Order (Payment, step-by-step)

```
1. database/0017_create_payment.sql              (payment + payment_allocation + payment_advance_usage + payment_audit_log, Part 1)
2. models/payment_model.py                        (Part 1)
3. engines/payment_validator.py                   (Part 2)
4. engines/payment_engine.py                      (Part 2)
5. Wire PaymentEngine in main.py                    (Part 3, section 2 above)
6. Add optional payment_engine param + advance-apply
   call to engines/purchase_engine.py                (Part 3, section 2 -- the ONE cross-module change)
7. screens/payment_audit_log_dialog.py            (Part 3 -- new, small)
8. screens/payment_form_screen.py                 (Part 3 -- FIFO preview + override grid, Add+Edit modes)
9. screens/payment_list_screen.py                 (Part 3 -- reuses cancellation_reason_dialog.py)
10. Add "Payment" entry to Dashboard "Accounts" group (Part 3, section 1.4)
11. End-to-end test: post 2 open Purchase Invoices for a supplier
    (older + newer) -> payment for less than the older invoice's total
    -> confirm it allocates only to the older one -> payment for MORE
    than both combined -> confirm both close out and the remainder
    becomes advance_amount -> edit that payment's payment_mode ->
    confirm payment_audit_log has the entry -> re-target one allocation
    to a different invoice via edit -> confirm audit log captures both
    the removal and the addition -> post a NEW Purchase Invoice for the
    same supplier -> confirm the earlier advance auto-applies via the
    purchase_engine.py hook -> cancel a payment -> confirm its invoices'
    outstanding amounts go back up immediately -> confirm a Cancelled
    payment cannot be edited
```

---

## 4. Combined Blueprint JSON — Update

Adds a `Payment` module block, joining `Receipt` in the same "Accounts" Dashboard group. One entry (`PY06`) modifies `engines/purchase_engine.py`, mirroring `RC06`'s modification of `sale_engine.py`:

```json
[
  {
    "id": "PY01",
    "module": "Payment",
    "phase": "Part-1 Database",
    "title": "Create payment + payment_allocation + payment_advance_usage + payment_audit_log tables",
    "file": "database/0017_create_payment.sql",
    "status": "done"
  },
  {
    "id": "PY02",
    "module": "Payment",
    "phase": "Part-1 Models",
    "title": "Create PaymentModel (insert_with_allocations, FIFO-ordered get_outstanding_invoices_for_supplier, advance queries, audit-log read/write, cancel, soft_delete)",
    "file": "models/payment_model.py",
    "status": "done"
  },
  {
    "id": "PY03",
    "module": "Payment",
    "phase": "Part-2 Engines",
    "title": "Create payment_validator.py (PaymentValidator -- header, allocation-vs-outstanding checks, cancellation reason)",
    "file": "engines/payment_validator.py",
    "status": "done"
  },
  {
    "id": "PY04",
    "module": "Payment",
    "phase": "Part-2 Engines",
    "title": "Create PaymentEngine (FIFO auto-allocation, advance computation/consumption, audit-logged edit_payment, cancel_payment, delete_draft)",
    "file": "engines/payment_engine.py",
    "status": "done"
  },
  {
    "id": "PY05",
    "module": "Payment",
    "phase": "Part-3 Wiring",
    "title": "Wire PaymentEngine (factory/construction order)",
    "file": "main.py",
    "status": "pending"
  },
  {
    "id": "PY06",
    "module": "Payment",
    "phase": "Part-3 Wiring",
    "title": "Add optional payment_engine dependency + advance-auto-apply call to PurchaseEngine.create_purchase_invoice() (additive only, existing Purchase Module behavior unchanged if omitted)",
    "file": "engines/purchase_engine.py",
    "status": "pending"
  },
  {
    "id": "PY07",
    "module": "Payment",
    "phase": "Part-3 Screens",
    "title": "Create PaymentAuditLogDialog (read-only edit-history viewer)",
    "file": "screens/payment_audit_log_dialog.py",
    "status": "pending"
  },
  {
    "id": "PY08",
    "module": "Payment",
    "phase": "Part-3 Screens",
    "title": "Create PaymentFormScreen (Add + Edit modes, FIFO preview grid with manual override)",
    "file": "screens/payment_form_screen.py",
    "status": "pending"
  },
  {
    "id": "PY09",
    "module": "Payment",
    "phase": "Part-3 Screens",
    "title": "Create PaymentListScreen (View/Edit/Cancel via shared CancellationReasonDialog/Delete-Draft-only/View Audit Log)",
    "file": "screens/payment_list_screen.py",
    "status": "pending"
  },
  {
    "id": "PY10",
    "module": "Payment",
    "phase": "Part-3 Dashboard",
    "title": "Add 'Payment' entry to the 'Accounts' sidebar group (created by RC10)",
    "file": "screens/dashboard_screen.py",
    "status": "pending"
  },
  {
    "id": "PY11",
    "module": "Payment",
    "phase": "Part-3 Test",
    "title": "End-to-end test: FIFO allocation across multiple invoices, advance creation, edit with audit-log verification, advance auto-apply to new Purchase Invoice, cancel with immediate outstanding reversal, Cancelled payment un-editable",
    "file": null,
    "status": "pending"
  }
]
```

> **Running total:** 66 (after Receipt, per Receipt Part 3) + 11 (PY01–PY11, all new) = **77 tasks**. Both halves of the money-collection system (customer-side Receipt, supplier-side Payment) are now blueprinted with fully symmetric design — same FIFO logic, same advance mechanism, same audit-log approach, same shared dialogs.

---

**Part 3 complete — Payment blueprint (Parts 1+2+3) fully documented, a complete mirror of Receipt for the supplier side.**

With Sale Return, Purchase Return, Receipt, and Payment all now fully blueprinted, the remaining modules before the single combined JSON + coding phase are **Accounts (double-entry)** and **Reports**. Confirm and I'll move to **Accounts** next.
