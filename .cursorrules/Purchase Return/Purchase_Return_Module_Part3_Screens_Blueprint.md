# Purchase Return Module — Part 3: Screens + Combined Blueprint JSON Update

**Project:** Medical ERP V2
**Layer:** Screens ("No SQL. No business logic." — collect input, call the Engine, render whatever DTO comes back)
**Depends on Part 1+2:** `purchase_return`/`purchase_return_item` tables, `models/purchase_return_model.py`, `engines/purchase_return_engine.py`, `engines/purchase_return_validator.py`

---

## 1. Screens Layer (`screens/`)

### 1.1 `screens/purchase_return_form_screen.py` (the core screen)

```python
"""
screens/purchase_return_form_screen.py

Purchase Return Add Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- "No SQL. No business logic."):
    - Invoice picker: a searchable combo/lookup (search by
      internal_ref_number, supplier's own invoice_number, or supplier
      name) to select the ORIGINAL posted Purchase Invoice this return
      is against -- a return is never standalone.
    - On invoice selection, calls engine.get_returnable_lines(purchase_invoice_id)
      and renders one grid row per original line, showing:
        Item | Batch | Expiry | Original Qty | Already Returned (Paid) |
        Remaining Returnable Qty | Original Free Qty | Already Returned
        (Free) | Remaining Returnable Free Qty  (all READ-ONLY)
        | Return Qty | Return Free Qty  (the TWO editable cells per line
        -- unlike Sale Return's single editable cell, since paid and free
        are independently returnable here)
      Rate/Discount/CC are NOT shown as editable -- the Engine computes
      them read-only from the original line; the screen may show a
      computed-preview "Amount" column but never accepts input for it.
    - Rows where BOTH Return Qty and Return Free Qty are left at 0/blank
      are simply excluded when building the payload for Save.
    - Header fields: Return Date (BS, defaults to today), Return Reason
      (free text, mandatory), Settlement Mode (combo: Adjust Against
      Payable / Supplier Advance / Cash Refund, default "Adjust Against
      Payable"), Remarks (optional).
    - Save button -> PurchaseReturnEngine.create_return(). Only lines
      with Return Qty > 0 and/or Return Free Qty > 0 are sent. Surfaces
      ValidationError distinctly (e.g. "Line 2: Return Free Qty (10)
      exceeds remaining returnable free quantity (4)") -- same pattern
      as SaleReturnFormScreen's error surfacing.
    """
    def __init__(self, parent, engine: "PurchaseReturnEngine", purchase_invoice_engine): ...

    # ---- Invoice picker ----
    def _on_invoice_selected(self, purchase_invoice_id: int) -> None:
        """Loads engine.get_returnable_lines(purchase_invoice_id) and
        rebuilds the grid. Also pre-fills the (read-only) supplier name/
        invoice date info panel from the invoice."""
        ...

    # ---- Grid (read-only lines, TWO editable cells per row) ----
    def _populate_return_grid(self, returnable_lines: list[dict]) -> None:
        """One row per line from get_returnable_lines(). A line whose
        remaining_returnable_qty is 0 disables ONLY its Return Qty cell;
        if remaining_returnable_free_qty is also 0, its Return Free Qty
        cell is disabled too -- but the two cells are disabled
        INDEPENDENTLY of each other, since one side can still have
        remaining quantity while the other doesn't."""
        ...
    def _on_return_qty_changed(self, row_index: int) -> None:
        """Client-side sanity check only (return_qty <= remaining_qty)
        for immediate feedback; authoritative check happens server-side
        in PurchaseReturnValidator when Save is clicked."""
        ...
    def _on_return_free_qty_changed(self, row_index: int) -> None:
        """Same as above, checked against remaining_returnable_free_qty
        independently."""
        ...

    # ---- Save ----
    def _collect_return_lines(self) -> list[dict]:
        """Builds [{"purchase_invoice_item_id", "return_qty",
        "return_free_qty", "remarks"}, ...] from every row where EITHER
        value is > 0. Rows where both are 0 are excluded."""
        ...
    def _on_save_clicked(self) -> None:
        """Calls engine.create_return(purchase_invoice_id, supplier_id,
        return_date_ad, return_reason, settlement_mode, return_lines,
        created_by). On ValidationError, shows each error line-by-line
        in a single dialog."""
        ...
```

### 1.2 `screens/purchase_return_list_screen.py`

```python
class PurchaseReturnListScreen(QWidget):
    """List/search/filter -- mirrors screens/sale_return_list_screen.py's
    shape (same List/View/Cancel/Delete-Draft-only pattern). Filters:
    Supplier, original Invoice (internal_ref_number), Status (Draft/
    Posted/Cancelled), Settlement Mode, Date range. Actions:
        - View: read-only detail (original invoice reference, return
          reason, settlement mode, every returned line with its
          read-only computed amounts, paid qty AND free qty shown
          separately).
        - Cancel: ONLY for status='Posted'. Opens the SAME shared
          screens/cancellation_reason_dialog.py already built for Sale
          Return (Sale Return Part 3, section 1.3) -- reused as-is, no
          duplicate dialog code -> calls engine.cancel_return(
          purchase_return_id, cancellation_reason, updated_by).
        - Delete: ONLY visible/enabled for status='Draft' rows -> calls
          engine.delete_draft(). Hidden entirely for Posted/Cancelled
          rows, same reasoning as Sale Return's list screen.
    """
    def __init__(self, parent, engine: "PurchaseReturnEngine"): ...
    def refresh(self) -> None: ...
    def _on_view_clicked(self, purchase_return_id: int) -> None: ...
    def _on_cancel_clicked(self, purchase_return_id: int) -> None:
        """Opens the shared CancellationReasonDialog (built in Sale
        Return Part 3) -> engine.cancel_return(...)."""
        ...
    def _on_delete_clicked(self, purchase_return_id: int) -> None: ...
```

> **Reuse note:** `screens/cancellation_reason_dialog.py` was deliberately built generic in Sale Return Part 3 precisely for this — Purchase Return needs ZERO new dialog code, just an import.

### 1.3 Dashboard Wiring

`screens/dashboard_screen.py` — add **"Purchase Return"** entry under the existing "Purchase" module group (alongside "Purchase Order" and "Purchase Invoice"), same pattern as Sale Return's wiring under "Sale". `PurchaseReturnListScreen`'s own "+ New Return" toolbar button opens `PurchaseReturnFormScreen` with the Invoice picker empty — no standalone Dashboard quick-action, same reasoning as Sale Return (a return always needs an invoice chosen first).

---

## 2. Wiring Checklist

```python
# Construction order: PurchaseInvoiceModel + ItemEngine (both already
# exist, shared) -> PurchaseReturnEngine. No new lower-level engine
# needed first.

from models.purchase_return_model import PurchaseReturnModel
from engines.purchase_return_engine import PurchaseReturnEngine

purchase_return_engine = PurchaseReturnEngine(
    model=PurchaseReturnModel(),
    purchase_invoice_model=purchase_invoice_model_instance,   # SAME PurchaseInvoiceModel already used by Purchase module
    item_engine=item_engine_instance,                          # SAME ItemEngine already used app-wide
)

# Screens receive the engine via constructor injection, same as every
# other module:
purchase_return_list_screen = PurchaseReturnListScreen(parent=dashboard, engine=purchase_return_engine)
purchase_return_form_screen = PurchaseReturnFormScreen(
    parent=dashboard,
    engine=purchase_return_engine,
    purchase_invoice_engine=purchase_engine_instance,   # for the Invoice picker's search
)
```

---

## 3. Suggested Build Order (Purchase Return, step-by-step)

```
1. database/0010_create_purchase_return.sql        (purchase_return + purchase_return_item, Part 1 -- replaces the old Phase-2 placeholder sketch)
2. Extend models/purchase_invoice_model.py          (get_returnable_items(), Part 1)
3. models/purchase_return_model.py                  (Part 1)
4. engines/purchase_return_validator.py             (Part 2)
5. engines/purchase_return_engine.py                (Part 2)
6. Wire PurchaseReturnEngine in main.py              (Part 3, section 2 above)
7. screens/purchase_return_form_screen.py           (Part 3 -- reuses cancellation_reason_dialog.py, built once in Sale Return Part 3, no new dialog)
8. screens/purchase_return_list_screen.py           (Part 3)
9. Wire Dashboard sidebar "Purchase Return" entry    (Part 3, section 1.3)
10. End-to-end test: post a Purchase Invoice with both paid AND free qty
    on a line -> partially return the paid portion -> confirm remaining
    paid qty shrinks while free qty is untouched -> return the free
    portion separately -> confirm both remaining trackers are
    independent -> attempt to over-return either side -> confirm
    ValidationError -> Cancel the return -> confirm stock (both paid +
    free units) reverses back IN and cancellation_reason is stored ->
    confirm a Cancelled return can never be deleted, only a
    never-posted Draft can
```

---

## 4. Combined Blueprint JSON — Update

The Purchase Module's own Part 3 listed 4 un-numbered Phase-2 tasks at the bottom ("baad mein"): `database/0010_create_purchase_return.sql`, `models/purchase_return_model.py`, `engines/purchase_return_engine.py`, `screens/purchase_return_form_screen.py`. Replace those 4 informal entries — and the `P17`/`P18` placeholder pair carried in the combined Purchase+Sale JSON — with this expanded, numbered block. Everything else in the combined JSON stays unchanged:

```json
[
  {
    "id": "PR01",
    "module": "Purchase Return",
    "phase": "Part-1 Database",
    "title": "Create purchase_return + purchase_return_item tables (supersedes old placeholder sketch)",
    "file": "database/0010_create_purchase_return.sql",
    "status": "done"
  },
  {
    "id": "PR02",
    "module": "Purchase Return",
    "phase": "Part-1 Models",
    "title": "Extend purchase_invoice_model.py with get_returnable_items() (paid + free qty tracked independently)",
    "file": "models/purchase_invoice_model.py",
    "status": "done"
  },
  {
    "id": "PR03",
    "module": "Purchase Return",
    "phase": "Part-1 Models",
    "title": "Create PurchaseReturnModel (insert_with_items, get_returned_qty_for_invoice_item returning both paid+free sums, search, cancel, soft_delete)",
    "file": "models/purchase_return_model.py",
    "status": "done"
  },
  {
    "id": "PR04",
    "module": "Purchase Return",
    "phase": "Part-2 Engines",
    "title": "Create purchase_return_validator.py (PurchaseReturnValidator -- header, lines, independent paid/free cumulative-qty checks, cancellation reason)",
    "file": "engines/purchase_return_validator.py",
    "status": "done"
  },
  {
    "id": "PR05",
    "module": "Purchase Return",
    "phase": "Part-2 Engines",
    "title": "Create PurchaseReturnEngine (proportional discount/cc copy, create_return with stock-OUT posting, cancel_return with stock-IN reversal, delete_draft)",
    "file": "engines/purchase_return_engine.py",
    "status": "done"
  },
  {
    "id": "PR06",
    "module": "Purchase Return",
    "phase": "Part-3 Wiring",
    "title": "Wire PurchaseReturnEngine (factory/construction order, shared PurchaseInvoiceModel + ItemEngine)",
    "file": "main.py",
    "status": "pending"
  },
  {
    "id": "PR07",
    "module": "Purchase Return",
    "phase": "Part-3 Screens",
    "title": "Create PurchaseReturnFormScreen (Invoice picker, returnable-lines grid with TWO editable cells per row -- paid + free)",
    "file": "screens/purchase_return_form_screen.py",
    "status": "pending"
  },
  {
    "id": "PR08",
    "module": "Purchase Return",
    "phase": "Part-3 Screens",
    "title": "Create PurchaseReturnListScreen (View/Cancel via shared CancellationReasonDialog/Delete-Draft-only)",
    "file": "screens/purchase_return_list_screen.py",
    "status": "pending"
  },
  {
    "id": "PR09",
    "module": "Purchase Return",
    "phase": "Part-3 Dashboard",
    "title": "Wire Purchase Return sidebar entry under 'Purchase' group",
    "file": "screens/dashboard_screen.py",
    "status": "pending"
  },
  {
    "id": "PR10",
    "module": "Purchase Return",
    "phase": "Part-3 Test",
    "title": "End-to-end test: independent paid/free return + over-return rejection on each side + cancel reversal (both qty types) + reason stored + Cancelled/Posted never deletable",
    "file": null,
    "status": "pending"
  }
]
```

> **Note on Task Count:** this replaces the old un-numbered Phase-2 sketch (4 items) plus the `P17`/`P18` combined-JSON placeholders with 10 detailed tasks (PR01–PR10), of which PR01–PR05 are already `done` (Parts 1+2 delivered in this chat). Running combined total after Sale Return (47, per Sale Return Part 3) + this replacement: 47 − 2 (removed P17/P18) + 10 (added PR01–PR10) = **55 tasks**.

---

**Part 3 complete — Purchase Return blueprint (Parts 1+2+3) fully documented, matching Sale Return's own structure exactly, with the paid/free independence difference carried through consistently at every layer.**

Confirm and I'll move to the next module in the build order — **Receipt**.
