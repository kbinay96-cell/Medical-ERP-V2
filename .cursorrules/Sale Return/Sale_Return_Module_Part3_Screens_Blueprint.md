# Sale Return Module — Part 3: Screens + Combined Blueprint JSON Update

**Project:** Medical ERP V2
**Layer:** Screens ("No SQL. No business logic." — collect input, call the Engine, render whatever DTO comes back)
**Depends on Part 1+2:** `sale_return`/`sale_return_item` tables, `models/sale_return_model.py`, `engines/sale_return_engine.py`, `engines/sale_return_validator.py`

---

## 1. Screens Layer (`screens/`)

### 1.1 `screens/sale_return_form_screen.py` (the core screen)

```python
"""
screens/sale_return_form_screen.py

Sale Return Add Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- "No SQL. No business logic."):
    - Invoice picker: a searchable combo/lookup (search by invoice_number
      or customer name) to select the ORIGINAL posted Sale Invoice this
      return is against -- confirmed rule: a return is never standalone.
    - On invoice selection, calls engine.get_returnable_lines(sale_invoice_id)
      and renders one grid row per original line, showing:
        Item | Batch | Expiry | Original Qty | Already Returned |
        Remaining Returnable Qty (all READ-ONLY) | Return Qty (the ONLY
        editable cell, per line)
      Rate/Discount/CC/Tax are intentionally NOT shown as editable --
      the Engine computes them read-only from the original line; the
      screen may show a computed-preview "Amount" column but never
      accepts user input for it.
    - Rows where the user leaves Return Qty at 0/blank are simply
      excluded when building the payload for Save -- no need to
      explicitly "remove" a row.
    - Header fields: Return Date (BS, defaults to today), Return Reason
      (free text, mandatory), Refund Mode (combo: Adjust Against Invoice
      / Advance / Cash Refund, default "Adjust Against Invoice"), Remarks
      (optional).
    - Save button -> SaleReturnEngine.create_return(). Only lines with
      Return Qty > 0 are sent. Surfaces ValidationError distinctly (e.g.
      "Line 2: Return Qty (5) exceeds remaining returnable quantity (3)")
      -- same pattern as SaleInvoiceFormScreen's error surfacing.
    """
    def __init__(self, parent, engine: "SaleReturnEngine", sale_invoice_engine): ...

    # ---- Invoice picker ----
    def _on_invoice_selected(self, sale_invoice_id: int) -> None:
        """Loads engine.get_returnable_lines(sale_invoice_id) and rebuilds
        the grid. Also pre-fills the (read-only) customer name/invoice
        date info panel from the invoice, mirroring the info-panel pattern
        already used in Sale Invoice's Area->Customer flow."""
        ...

    # ---- Grid (read-only lines, one editable cell per row) ----
    def _populate_return_grid(self, returnable_lines: list[dict]) -> None:
        """One row per line from get_returnable_lines(). A line whose
        remaining_returnable_qty is 0 is still shown (for visibility /
        audit) but its Return Qty cell is disabled -- fully returned
        lines cannot accept further input."""
        ...
    def _on_return_qty_changed(self, row_index: int) -> None:
        """Client-side sanity check only (return_qty <= remaining) for
        immediate feedback; the authoritative check still happens in
        SaleReturnValidator server-side when Save is clicked -- this is
        UX only, never a substitute for the Engine's validation."""
        ...

    # ---- Save ----
    def _collect_return_lines(self) -> list[dict]:
        """Builds [{"sale_invoice_item_id", "return_qty", "remarks"}, ...]
        from every row where Return Qty > 0. Empty/zero rows excluded."""
        ...
    def _on_save_clicked(self) -> None:
        """Calls engine.create_return(sale_invoice_id, customer_id,
        return_date_ad, return_reason, refund_mode, return_lines,
        created_by). On ValidationError, shows each error line-by-line
        in a single dialog (mirrors SaleInvoiceFormScreen's multi-error
        display)."""
        ...
```

### 1.2 `screens/sale_return_list_screen.py`

```python
class SaleReturnListScreen(QWidget):
    """List/search/filter -- mirrors screens/sale_invoice_list_screen.py's
    shape. Filters: Customer, original Invoice Number, Status (Draft/
    Posted/Cancelled), Refund Mode, Date range. Actions:
        - View: read-only detail (original invoice reference, return
          reason, refund mode, every returned line with its read-only
          computed amounts).
        - Cancel: ONLY for status='Posted'. Opens a small mandatory-
          reason dialog (single required text field, same shape as
          Sale Invoice's future cancellation dialog) -> calls
          engine.cancel_return(sale_return_id, cancellation_reason,
          updated_by). Confirmed rule: reversal posting, never a delete.
        - Delete: ONLY visible/enabled for status='Draft' rows -> calls
          engine.delete_draft(). Hidden entirely for Posted/Cancelled
          rows (the confirmed rule that only a Draft may be deleted is
          enforced in BOTH the Engine and the Screen, so the option
          never even appears where it would just fail server-side).
    """
    def __init__(self, parent, engine: "SaleReturnEngine"): ...
    def refresh(self) -> None: ...
    def _on_view_clicked(self, sale_return_id: int) -> None: ...
    def _on_cancel_clicked(self, sale_return_id: int) -> None:
        """Opens CancellationReasonDialog (shared small dialog, one
        required text field) -> engine.cancel_return(...)."""
        ...
    def _on_delete_clicked(self, sale_return_id: int) -> None: ...
```

### 1.3 Shared: `screens/cancellation_reason_dialog.py` (new, small, reusable)

```python
class CancellationReasonDialog(QDialog):
    """One required multi-line text field + OK/Cancel buttons. OK is
    disabled until the text field is non-empty. Returns the entered
    reason string to the caller. Reused by SaleReturnListScreen now;
    intended to be reused again by Purchase Return, Receipt, and Payment
    list screens later, since the project-wide rule (mandatory
    cancellation reason) is identical across all of them -- built once
    here rather than duplicated per module."""
    def __init__(self, parent, title: str = "Cancellation Reason"): ...
    def get_reason(self) -> Optional[str]:
        """Returns the trimmed reason string if OK was clicked, else None."""
        ...
```

### 1.4 Dashboard Wiring

`screens/dashboard_screen.py` sidebar additions, same pattern as the existing Sale Invoice wiring:
- **"Sale"** module group → add **"Sale Return"** entry (opens `SaleReturnListScreen`), alongside the existing "Sale Invoice" entry
- `SaleReturnListScreen`'s own "+ New Return" toolbar button opens `SaleReturnFormScreen` with the Invoice picker empty (user searches/selects the invoice first) — there is deliberately no standalone "Quick Action" shortcut for Sale Return on the main Dashboard, since a return always needs an invoice chosen first (unlike Sale Invoice, which can start blank)

---

## 2. Wiring Checklist

```python
# Construction order: SaleInvoiceModel + ItemEngine (both already exist,
# shared) -> SaleReturnEngine. No new lower-level engine is needed first
# (unlike Sale Module, which needed ItemFreeSchemeEngine built before
# SaleEngine).

from models.sale_return_model import SaleReturnModel
from engines.sale_return_engine import SaleReturnEngine

sale_return_engine = SaleReturnEngine(
    model=SaleReturnModel(),
    sale_invoice_model=sale_invoice_model_instance,   # SAME SaleInvoiceModel already used by Sale module
    item_engine=item_engine_instance,                 # SAME ItemEngine already used app-wide
)

# Screens receive the engine via constructor injection, same as every
# other module:
sale_return_list_screen = SaleReturnListScreen(parent=dashboard, engine=sale_return_engine)
sale_return_form_screen = SaleReturnFormScreen(
    parent=dashboard,
    engine=sale_return_engine,
    sale_invoice_engine=sale_engine_instance,   # for the Invoice picker's search
)
```

---

## 3. Suggested Build Order (Sale Return, step-by-step)

```
1. database/0015_create_sale_return.sql          (sale_return + sale_return_item, Part 1)
2. Extend models/sale_invoice_model.py            (get_returnable_items(), Part 1)
3. models/sale_return_model.py                    (Part 1)
4. engines/sale_return_validator.py               (Part 2)
5. engines/sale_return_engine.py                  (Part 2)
6. Wire SaleReturnEngine in main.py                (Part 3, section 2 above)
7. screens/cancellation_reason_dialog.py          (Part 3 -- shared, build once)
8. screens/sale_return_form_screen.py             (Part 3)
9. screens/sale_return_list_screen.py             (Part 3)
10. Wire Dashboard sidebar "Sale Return" entry     (Part 3, section 1.4)
11. End-to-end test: post a Sale Invoice -> partially return one line ->
    confirm remaining_returnable_qty shrinks -> attempt to over-return ->
    confirm ValidationError -> Cancel the return -> confirm stock reverses
    back out and cancellation_reason is stored -> confirm a Cancelled
    return can never be deleted, only a never-posted Draft can
```

---

## 4. Combined Blueprint JSON — Update (replaces placeholder task S18)

The existing combined Purchase+Sale JSON (delivered in Sale Module Part 3) had a single placeholder task, `S18` ("Create sale_return + sale_return_item tables, Model, Engine, Screen", status `pending`). Replace that ONE task with this expanded block — everything else in the combined JSON (P01–P18, S01–S17, A01) stays unchanged:

```json
[
  {
    "id": "SR01",
    "module": "Sale Return",
    "phase": "Part-1 Database",
    "title": "Create sale_return + sale_return_item tables",
    "file": "database/0015_create_sale_return.sql",
    "status": "done"
  },
  {
    "id": "SR02",
    "module": "Sale Return",
    "phase": "Part-1 Models",
    "title": "Extend sale_invoice_model.py with get_returnable_items()",
    "file": "models/sale_invoice_model.py",
    "status": "done"
  },
  {
    "id": "SR03",
    "module": "Sale Return",
    "phase": "Part-1 Models",
    "title": "Create SaleReturnModel (insert_with_items, get_returned_qty_for_invoice_item, search, cancel, soft_delete)",
    "file": "models/sale_return_model.py",
    "status": "done"
  },
  {
    "id": "SR04",
    "module": "Sale Return",
    "phase": "Part-2 Engines",
    "title": "Create sale_return_validator.py (SaleReturnValidator -- header, lines, cumulative-qty check, cancellation reason)",
    "file": "engines/sale_return_validator.py",
    "status": "done"
  },
  {
    "id": "SR05",
    "module": "Sale Return",
    "phase": "Part-2 Engines",
    "title": "Create SaleReturnEngine (proportional rate/discount/cc/tax copy, create_return, cancel_return with reversal posting, delete_draft)",
    "file": "engines/sale_return_engine.py",
    "status": "done"
  },
  {
    "id": "SR06",
    "module": "Sale Return",
    "phase": "Part-3 Wiring",
    "title": "Wire SaleReturnEngine (factory/construction order, shared SaleInvoiceModel + ItemEngine)",
    "file": "main.py",
    "status": "pending"
  },
  {
    "id": "SR07",
    "module": "Sale Return",
    "phase": "Part-3 Screens",
    "title": "Create CancellationReasonDialog (shared, reusable by Purchase Return/Receipt/Payment later)",
    "file": "screens/cancellation_reason_dialog.py",
    "status": "pending"
  },
  {
    "id": "SR08",
    "module": "Sale Return",
    "phase": "Part-3 Screens",
    "title": "Create SaleReturnFormScreen (Invoice picker, returnable-lines grid, single editable Return Qty per row)",
    "file": "screens/sale_return_form_screen.py",
    "status": "pending"
  },
  {
    "id": "SR09",
    "module": "Sale Return",
    "phase": "Part-3 Screens",
    "title": "Create SaleReturnListScreen (View/Cancel/Delete-Draft-only)",
    "file": "screens/sale_return_list_screen.py",
    "status": "pending"
  },
  {
    "id": "SR10",
    "module": "Sale Return",
    "phase": "Part-3 Dashboard",
    "title": "Wire Sale Return sidebar entry under 'Sale' group",
    "file": "screens/dashboard_screen.py",
    "status": "pending"
  },
  {
    "id": "SR11",
    "module": "Sale Return",
    "phase": "Part-3 Test",
    "title": "End-to-end test: partial return -> remaining qty check -> over-return rejected -> cancel -> stock reversal + reason stored -> Cancelled/Posted never deletable",
    "file": null,
    "status": "pending"
  }
]
```

> **Note on Task Count:** this replaces the single `S18` placeholder with 11 detailed tasks (SR01–SR11), of which SR01–SR05 are already `done` (Parts 1+2 delivered in this chat). Total combined task count becomes 37 − 1 (removed S18) + 11 (added SR01–SR11) = **47 tasks**. When the final single combined JSON is assembled (after Purchase Return, Receipt, Payment, Accounts, Reports are all similarly blueprinted), this SR block slots in exactly where S18 used to sit.

---

**Part 3 complete — Sale Return blueprint (Parts 1+2+3) fully documented, matching the Sale Module's own structure exactly.**

Confirm and I'll move to the next module in the build order — **Purchase Return**.
