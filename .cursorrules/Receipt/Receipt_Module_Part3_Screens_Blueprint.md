# Receipt Module — Part 3: Screens + Combined Blueprint JSON Update

**Project:** Medical ERP V2
**Layer:** Screens ("No SQL. No business logic." — collect input, call the Engine, render whatever DTO comes back)
**Depends on Part 1+2:** `receipt`/`receipt_allocation`/`receipt_advance_usage`/`receipt_audit_log` tables, `models/receipt_model.py`, `engines/receipt_engine.py`, `engines/receipt_validator.py`

---

## 1. Screens Layer (`screens/`)

### 1.1 `screens/receipt_form_screen.py` (the core screen — Add AND Edit)

```python
"""
screens/receipt_form_screen.py

Receipt Add/Edit Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- "No SQL. No business logic."):
    - Customer picker (searchable combo).
    - Header fields: Receipt Date (BS, defaults to today), Payment Mode
      (combo: Cash/Bank Transfer/Cheque/Card/Other), Amount, Reference
      No. (shown/required only when Payment Mode needs it -- Bank
      Transfer/Cheque/Card), Bank Name (shown only for those modes too),
      Remarks.
    - On Customer + Amount entered: calls
      engine.get_outstanding_invoices() and shows a PREVIEW allocation
      grid, pre-filled with the FIFO result (as if the user had called
      create_receipt with manual_allocations=None) -- computed
      CLIENT-SIDE here purely for preview (same oldest-first walk,
      simple enough to mirror in the Screen for instant feedback) BUT
      the authoritative allocation is always whatever the Engine
      actually computes/accepts when Save is clicked.
    - User can override the preview: uncheck an invoice, retype an
      amount, or add an invoice the FIFO pass skipped -- switching the
      Save call from manual_allocations=None (pure auto) to an explicit
      list (whatever is now on screen).
    - Any amount left unallocated after the grid is shown live as
      "Advance: Rs {x}" -- informational only, never blocks Save (a
      pure-advance receipt with zero allocations is valid).
    - Save (new): engine.create_receipt(...).
    - Save (editing an existing Posted receipt): engine.edit_receipt(
      receipt_id, updated_by, header_changes={...only changed fields...},
      new_allocations=... if the grid was touched, else None). The
      Screen tracks which fields the user actually changed so it only
      sends a diff, not the whole form, keeping the audit log clean.
    - Surfaces ValidationError messages back to the user, same pattern
      as every other module's form screen.
    """
    def __init__(self, parent, engine: "ReceiptEngine", customer_engine, receipt_id: Optional[int] = None): ...
    def _load_existing_receipt(self) -> None:
        """Only when receipt_id was passed (Edit mode) -- populates every
        field AND the allocation grid from engine.get_by_id()."""
        ...
    def _on_customer_or_amount_changed(self) -> None: ...
    def _load_fifo_preview(self, customer_id: int, amount: float) -> None: ...
    def _populate_allocation_grid(self, allocation_rows: list[dict]) -> None: ...
    def _on_allocation_row_changed(self, row_index: int) -> None: ...
    def _collect_header_changes(self) -> dict:
        """Edit mode only -- diff current form values against the
        originally loaded receipt, returns ONLY the changed keys."""
        ...
    def _collect_allocations(self) -> list[dict]: ...
    def _on_save_clicked(self) -> None: ...
```

### 1.2 `screens/receipt_list_screen.py`

```python
class ReceiptListScreen(QWidget):
    """List/search/filter -- mirrors screens/sale_return_list_screen.py's
    shape. Filters: Customer, Payment Mode, Status, Date range. Actions:
        - View: read-only detail (allocations with invoice numbers,
          advance_amount, and a link to "View Audit Log" -- section 1.3).
        - Edit: ONLY for status='Posted' (a Cancelled receipt is never
          editable, enforced in both Engine and Screen) -> opens
          ReceiptFormScreen(receipt_id=...).
        - Cancel: ONLY for status='Posted'. Opens the SAME shared
          screens/cancellation_reason_dialog.py already built (Sale
          Return Part 3) and reused again in Purchase Return -> calls
          engine.cancel_receipt(receipt_id, cancellation_reason, updated_by).
        - Delete: ONLY visible/enabled for status='Draft' rows.
    """
    def __init__(self, parent, engine: "ReceiptEngine"): ...
    def refresh(self) -> None: ...
    def _on_view_clicked(self, receipt_id: int) -> None: ...
    def _on_edit_clicked(self, receipt_id: int) -> None: ...
    def _on_cancel_clicked(self, receipt_id: int) -> None: ...
    def _on_delete_clicked(self, receipt_id: int) -> None: ...
    def _on_view_audit_log_clicked(self, receipt_id: int) -> None:
        """Opens ReceiptAuditLogDialog (section 1.3)."""
        ...
```

### 1.3 `screens/receipt_audit_log_dialog.py` (new, small)

```python
class ReceiptAuditLogDialog(QDialog):
    """Read-only. Calls engine.get_audit_log(receipt_id) and shows a
    simple table: Changed Field | Old Value | New Value | Changed By |
    Changed At (BS). This is the ONLY place a user can see a Receipt's
    edit history -- the confirmed 'edit allowed but nothing lost'
    design depends on this screen actually being reachable, not just on
    the data existing in the database."""
    def __init__(self, parent, engine: "ReceiptEngine", receipt_id: int): ...
```

### 1.4 Dashboard Wiring

`screens/dashboard_screen.py` — add a new **"Accounts"** module group (first entry to exist in it, since Accounts itself isn't built yet) with a **"Receipt"** entry (opens `ReceiptListScreen`). "Payment" will be added to this same group next module. `ReceiptListScreen`'s own "+ New Receipt" toolbar button opens `ReceiptFormScreen` with no `receipt_id` (Add mode).

---

## 2. Wiring Checklist

```python
# Construction order -- ReceiptEngine has NO required external engine
# dependency, unlike Sale/Purchase Return:

from models.receipt_model import ReceiptModel
from engines.receipt_engine import ReceiptEngine

receipt_engine = ReceiptEngine(model=ReceiptModel())

receipt_list_screen = ReceiptListScreen(parent=dashboard, engine=receipt_engine)
receipt_form_screen = ReceiptFormScreen(
    parent=dashboard,
    engine=receipt_engine,
    customer_engine=customer_engine_instance,   # for the Customer picker's search
)

# ---------------------------------------------------------------- #
# REQUIRED cross-module hook -- the ONE piece of Part 2 that touches
# a file OUTSIDE this module:
# ---------------------------------------------------------------- #
#
# In engines/sale_engine.py, inside SaleEngine.create_sale_invoice(),
# AFTER the invoice is successfully saved and its ID is known, add:
#
#     applied_advance = self._receipt_engine.apply_advance_to_invoice(
#         customer_id=customer_id,
#         sale_invoice_id=new_sale_invoice_id,
#         requested_amount=grand_total,
#         applied_by=created_by,
#     )
#
# This means SaleEngine's constructor needs ONE new optional injected
# dependency, `receipt_engine=None` (lazy/optional so Sale Module keeps
# working standalone if Receipt somehow isn't wired yet -- mirrors how
# other optional engines are injected elsewhere in this codebase):
#
#     sale_engine = SaleEngine(
#         ...,  # every existing argument unchanged
#         receipt_engine=receipt_engine,   # NEW, optional
#     )
#
# If receipt_engine is None, SaleEngine simply skips the advance-apply
# call (advance still sits safely on the customer's receipt record,
# just not auto-offered on that particular invoice) -- no crash, no
# behavior change to existing Sale Module functionality.
```

---

## 3. Suggested Build Order (Receipt, step-by-step)

```
1. database/0016_create_receipt.sql              (receipt + receipt_allocation + receipt_advance_usage + receipt_audit_log, Part 1)
2. models/receipt_model.py                        (Part 1)
3. engines/receipt_validator.py                   (Part 2)
4. engines/receipt_engine.py                      (Part 2)
5. Wire ReceiptEngine in main.py                    (Part 3, section 2 above)
6. Add optional receipt_engine param + advance-apply
   call to engines/sale_engine.py                  (Part 3, section 2 -- the ONE cross-module change)
7. screens/receipt_audit_log_dialog.py            (Part 3 -- new, small)
8. screens/receipt_form_screen.py                 (Part 3 -- FIFO preview + override grid, Add+Edit modes)
9. screens/receipt_list_screen.py                 (Part 3 -- reuses cancellation_reason_dialog.py)
10. Wire Dashboard "Accounts" group -> "Receipt" entry (Part 3, section 1.4)
11. End-to-end test: create 2 open invoices for a customer (older +
    newer) -> receipt for less than older invoice's total -> confirm
    it allocates only to the older one -> receipt for MORE than both
    invoices combined -> confirm both close out and the remainder
    becomes advance_amount -> edit that receipt's payment_mode ->
    confirm receipt_audit_log has the entry -> re-target one
    allocation to a different invoice via edit -> confirm audit log
    captures both the removal and the addition -> create a NEW invoice
    for the same customer -> confirm the earlier advance auto-applies
    via the sale_engine.py hook -> cancel a receipt -> confirm its
    invoices' outstanding amounts go back up immediately (no separate
    reversal step needed) -> confirm a Cancelled receipt cannot be
    edited
```

---

## 4. Combined Blueprint JSON — Update

Adds a brand-new `Receipt` module block (no prior placeholder existed for it, since Receipt wasn't part of the original Purchase+Sale combined JSON). One entry (`RC06`) explicitly modifies `engines/sale_engine.py`, an existing file from an earlier module:

```json
[
  {
    "id": "RC01",
    "module": "Receipt",
    "phase": "Part-1 Database",
    "title": "Create receipt + receipt_allocation + receipt_advance_usage + receipt_audit_log tables",
    "file": "database/0016_create_receipt.sql",
    "status": "done"
  },
  {
    "id": "RC02",
    "module": "Receipt",
    "phase": "Part-1 Models",
    "title": "Create ReceiptModel (insert_with_allocations, FIFO-ordered get_outstanding_invoices_for_customer, advance queries, audit-log read/write, cancel, soft_delete)",
    "file": "models/receipt_model.py",
    "status": "done"
  },
  {
    "id": "RC03",
    "module": "Receipt",
    "phase": "Part-2 Engines",
    "title": "Create receipt_validator.py (ReceiptValidator -- header, allocation-vs-outstanding checks, cancellation reason)",
    "file": "engines/receipt_validator.py",
    "status": "done"
  },
  {
    "id": "RC04",
    "module": "Receipt",
    "phase": "Part-2 Engines",
    "title": "Create ReceiptEngine (FIFO auto-allocation, advance computation/consumption, audit-logged edit_receipt, cancel_receipt, delete_draft)",
    "file": "engines/receipt_engine.py",
    "status": "done"
  },
  {
    "id": "RC05",
    "module": "Receipt",
    "phase": "Part-3 Wiring",
    "title": "Wire ReceiptEngine (factory/construction order)",
    "file": "main.py",
    "status": "pending"
  },
  {
    "id": "RC06",
    "module": "Receipt",
    "phase": "Part-3 Wiring",
    "title": "Add optional receipt_engine dependency + advance-auto-apply call to SaleEngine.create_sale_invoice() (additive only, existing Sale Module behavior unchanged if omitted)",
    "file": "engines/sale_engine.py",
    "status": "pending"
  },
  {
    "id": "RC07",
    "module": "Receipt",
    "phase": "Part-3 Screens",
    "title": "Create ReceiptAuditLogDialog (read-only edit-history viewer)",
    "file": "screens/receipt_audit_log_dialog.py",
    "status": "pending"
  },
  {
    "id": "RC08",
    "module": "Receipt",
    "phase": "Part-3 Screens",
    "title": "Create ReceiptFormScreen (Add + Edit modes, FIFO preview grid with manual override)",
    "file": "screens/receipt_form_screen.py",
    "status": "pending"
  },
  {
    "id": "RC09",
    "module": "Receipt",
    "phase": "Part-3 Screens",
    "title": "Create ReceiptListScreen (View/Edit/Cancel via shared CancellationReasonDialog/Delete-Draft-only/View Audit Log)",
    "file": "screens/receipt_list_screen.py",
    "status": "pending"
  },
  {
    "id": "RC10",
    "module": "Receipt",
    "phase": "Part-3 Dashboard",
    "title": "Wire new 'Accounts' sidebar group with 'Receipt' entry",
    "file": "screens/dashboard_screen.py",
    "status": "pending"
  },
  {
    "id": "RC11",
    "module": "Receipt",
    "phase": "Part-3 Test",
    "title": "End-to-end test: FIFO allocation across multiple invoices, advance creation, edit with audit-log verification, advance auto-apply to new invoice, cancel with immediate outstanding reversal, Cancelled receipt un-editable",
    "file": null,
    "status": "pending"
  }
]
```

> **Running total:** 55 (after Purchase Return, per Purchase Return Part 3) + 11 (RC01–RC11, all new) = **66 tasks**. When Payment is blueprinted next, its tasks will slot in immediately after this Receipt block, and its module will join the same "Accounts" Dashboard group created by RC10.

---

**Part 3 complete — Receipt blueprint (Parts 1+2+3) fully documented.** This is also the first module needing a small, explicitly-flagged change to an existing file from an earlier module (`sale_engine.py`) — called out clearly in both the Wiring Notes and the combined JSON so it's never missed or silently skipped during actual coding.

Confirm and I'll move to the next module in the build order — **Payment**.
