# Sale Module — Part 3: Screens + Combined Purchase+Sale Blueprint JSON

**Project:** Medical ERP V2
**Layer:** Screens ("No SQL. No business logic." — collect input, call the Engine, render whatever DTO comes back)
**Depends on Part 1+2:** `sale_invoice`/`item_free_scheme` tables, `models/sale_invoice_model.py`, `models/item_free_scheme_model.py`, `engines/sale_engine.py`, `engines/item_free_scheme_engine.py`, `engines/sale_validator.py`

---

## 1. Screens Layer (`screens/`)

### 1.1 `screens/sale_invoice_form_screen.py` (Phase-1 — the core screen)

The most complex screen in the app so far — combines the Area→Customer two-combo pattern, Settings-driven column visibility, and the row-level inline-searchable-combo grid (all three confirmed requirements).

```python
"""
screens/sale_invoice_form_screen.py

Sale Invoice Add Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- "No SQL. No business logic."):
    - Area -> Customer two-combo search (confirmed requirement): Area
      combo populated from areas.list_active() equivalent
      (customer_model.get_areas()); selecting an Area repopulates the
      Customer combo via customer_model.get_active_customers_by_area().
    - Build the line-item grid's VISIBLE COLUMNS from the Settings
      group "Sale" (sale.column_show_*) -- Qty is hard-coded always
      visible; every other column is added/removed based on its
      setting. This same visible-column set is what later prints on
      the invoice (single source of truth, per confirmed requirement)
      -- no separate print-template column list exists anywhere.
    - Row-level inline item entry: the Item cell of EVERY row is itself
      a searchable combo (mirrors utils/combo_helpers.make_searchable,
      adapted to a table cell via a QComboBox set as the cell widget).
      Selecting an item in the LAST row auto-appends a new empty row.
      A conventional "+ Add Item" toolbar button also exists for users
      who prefer it.
    - On item selection in a row: calls engine.compute_line() (a PREVIEW
      call, not a save) to auto-fill Batch/Expiry (read-only cells),
      current_rate, mrp, and -- if Wholesale mode -- the free-scheme
      badge/tooltip so the user can SEE the scheme without memorizing it
      (confirmed requirement: "kaise pata chalega" -> a label like
      "Scheme: 5+1" shown next to the Free cell).
    - Per-row toggle between Free Qty mode and Net Rate mode (confirmed
      requirement) -- a small dropdown/switch per row; switching modes
      re-triggers the engine preview so Free/Rate update live.
    - Qty is the ONLY field that starts blank and is always editable;
      Rate is always editable (auto-filled, user may override); Batch/
      Expiry are always read-only.
    - Save button -> SaleEngine.create_sale_invoice() -- only rows with
      an item selected AND qty > 0 are sent.
    - Surfaces ValidationError / DuplicateRecordError / the special
      EngineErrorWithInvoice (invoice saved, but a stock line failed)
      distinctly, mirroring ItemFormScreen's existing partial-success
      handling pattern.
    """
    def __init__(self, parent, engine: "SaleEngine", customer_engine, item_free_scheme_engine): ...

    # ---- Header ----
    def _populate_area_combo(self) -> None: ...
    def _on_area_changed(self, area_id: int) -> None:
        """Repopulates the Customer combo via
        customer_model.get_active_customers_by_area(area_id) -- the
        confirmed two-combo cascade. Also pre-fills price_level_id/
        credit_limit display fields from the selected customer once
        chosen (read-only info panel, no new business logic -- purely
        displaying what customer_engine.get_customer() already returns)."""
        ...
    def _on_customer_changed(self, customer_id: int) -> None: ...

    # ---- Column visibility (built once at screen open) ----
    def _build_visible_columns(self) -> list[str]:
        """Reads every sale.column_show_* setting via settings_engine
        and returns the ordered list of column keys to render. 'qty' is
        always first-class and never conditional. This exact list is
        also what the (future) print/export routine will iterate --
        never duplicated as a separate print layout."""
        ...

    # ---- Grid ----
    def _add_empty_row(self) -> None: ...
    def _install_item_combo_on_row(self, row_index: int) -> None:
        """Sets a searchable QComboBox as the cell widget for the Item
        column of this row (not a dialog -- inline, per confirmed
        'hidden dropdown' requirement). Wires its
        currentIndexChanged/activated signal to _on_row_item_selected."""
        ...
    def _on_row_item_selected(self, row_index: int, item_id: int) -> None:
        """Calls self._engine.compute_line({...preview...}, is_wholesale)
        for a live preview (NOT a save), populates Batch/Expiry (read-
        only), current_rate/rate, mrp, and -- if a free scheme exists
        for this item -- shows the 'Scheme: X+Y' badge next to Free.
        If this was the LAST row, calls _add_empty_row()."""
        ...
    def _on_row_entry_mode_toggled(self, row_index: int) -> None:
        """Free Qty mode <-> Net Rate mode switch for one row; re-runs
        the compute_line() preview so Free/Rate refresh immediately."""
        ...
    def _on_row_qty_changed(self, row_index: int) -> None:
        """Re-runs the compute_line() preview whenever Qty changes,
        since Free/Rate/Amount all depend on it."""
        ...
    def _remove_row(self, row_index: int) -> None: ...

    # ---- Save ----
    def _collect_form_values(self) -> dict: ...
    def _on_save_clicked(self) -> None:
        """Calls engine.create_sale_invoice(). On EngineErrorWithInvoice,
        shows a distinct message: 'Invoice {number} was created, but
        stock could not be reduced for: ...' (invoice remains valid/
        saved) rather than treating it as a hard failure."""
        ...
```

### 1.2 `screens/sale_invoice_list_screen.py` (Phase-1)

```python
class SaleInvoiceListScreen(QWidget):
    """List/search/filter -- mirrors screens/purchase_invoice_list_screen.py
    exactly. Filters: Area, Customer, Status, Sale Mode (Retail/Wholesale),
    Date range. Actions: View (read-only detail, showing exactly the
    columns that were visible/printed at save time -- sale_invoice.sale_mode
    plus the per-line stored values ARE the historical record; a later
    Settings change never rewrites past invoices), Cancel (soft-delete,
    Draft/Posted only, per confirmed add-only + Sale Return correction
    rule)."""
    def __init__(self, parent, engine: "SaleEngine"): ...
    def refresh(self) -> None: ...
    def _on_view_clicked(self, sale_invoice_id: int) -> None: ...
    def _on_cancel_clicked(self, sale_invoice_id: int) -> None: ...
```

### 1.3 `screens/item_free_scheme_list_screen.py` + `item_free_scheme_form_screen.py` (Master screen, small)

Same shape as `screens/master_manage_screen.py`'s `MasterManageDialog` — but item-scoped rather than a plain code/name master (needs an Item combo + two numeric fields instead of code/name), so it is its OWN small dialog rather than reusing `MasterManageDialog` directly (mirrors how Manufacturer got its own dedicated screen instead of being forced through the generic `SimpleMasterEngine` pattern, per `engines/item_lookup_registry.py`'s documented reasoning).

```python
class ItemFreeSchemeFormScreen(QDialog):
    """Add/Edit dialog for a single item's Free Scheme.
    Fields: Item (searchable combo, via item_lookup_registry-style search),
    Buy Qty, Free Qty (together read as 'X+Y' -- shown live as a preview
    label while typing, e.g. 'Reads as: 5+1'), Active toggle, Remarks.
    Save -> ItemFreeSchemeEngine.create_scheme()/update_scheme()."""
    def __init__(self, parent, item_free_scheme_id, engine, item_engine): ...
    def _on_save_clicked(self) -> None: ...


class ItemFreeSchemeListScreen(QWidget):
    """List/search -- mirrors screens/supplier_manufacturer_discount_list_screen.py
    (no Status Filter combo, since this table only has is_active/is_deleted,
    same reasoning already documented there)."""
    def __init__(self, parent, engine, item_engine): ...
    def refresh(self) -> None: ...
```

### 1.4 Dashboard Wiring

`screens/dashboard_screen.py` sidebar additions, same pattern as the existing `open_supplier_form()` / PO wiring:
- **"Sale"** module group → **"Sale Invoice"** (opens `SaleInvoiceListScreen`), **"Item Free Scheme"** (opens `ItemFreeSchemeListScreen`, likely nested under "Masters" instead, since it's a master table not a transaction)
- Quick Action button `btnNewSale` (already present in `ui/dashboard.ui`, currently unwired) → opens `SaleInvoiceFormScreen` directly, mirroring how `btnAddSupplier`/`btnAddCustomer` already work

---

## 2. Wiring Checklist

```python
# Construction order: ItemFreeSchemeEngine -> SaleEngine (SaleEngine depends
# on both item_engine [existing, shared] and item_free_scheme_engine [new]).

from models.item_free_scheme_model import ItemFreeSchemeModel
from models.sale_invoice_model import SaleInvoiceModel
from engines.item_free_scheme_engine import ItemFreeSchemeEngine
from engines.sale_engine import SaleEngine
from engines.item_lookup_registry import manufacturer_lookup, country_tax_lookup

item_free_scheme_engine = ItemFreeSchemeEngine(model=ItemFreeSchemeModel())

sale_engine = SaleEngine(
    model=SaleInvoiceModel(),
    item_engine=item_engine_instance,               # SAME ItemEngine already used app-wide
    item_free_scheme_engine=item_free_scheme_engine,
    country_tax_lookup_fn=country_tax_lookup,
    manufacturer_lookup_fn=manufacturer_lookup,
)
```

---

## 3. Suggested Build Order (Sale Module, step-by-step)

**Part 1 — Database & Models:**
1. `database/0011_create_sale_invoice.sql` (`sale_invoice` + `sale_invoice_item`)
2. `database/0012_create_item_free_scheme.sql`
3. `database/0013_sale_settings_seed.sql` (Settings group "Sale")
4. Extension to `models/customer_model.py` — `get_active_customers_by_area()`
5. Extension to `models/item_model.py` — `get_nearest_expiry_batch()`
6. `models/sale_invoice_model.py`
7. `models/item_free_scheme_model.py`

**Part 2 — Engines & Validators:**
8. `engines/sale_validator.py` (both `SaleInvoiceValidator` + `ItemFreeSchemeValidator`)
9. `engines/item_free_scheme_engine.py`
10. `engines/sale_engine.py`

**Part 3 — Screens & Wiring:**
11. Wiring/factory code
12. `screens/item_free_scheme_form_screen.py` + `item_free_scheme_list_screen.py` (build BEFORE the Sale Invoice screen, since the scheme badge preview depends on this master having data to show)
13. `screens/sale_invoice_form_screen.py` (the big one — row-level combo grid)
14. `screens/sale_invoice_list_screen.py`
15. Dashboard sidebar entries + `btnNewSale` wiring
16. Test: create a Free Scheme (e.g. 5+1) → open Sale Invoice, Wholesale mode ON → pick Area→Customer → add item in-row → qty triggers auto free_qty → toggle to Net Rate mode, confirm rate recalculates → Save → confirm stock reduced by qty+free_qty → confirm CC appears in Wholesale, absent in Retail

**Phase-2 (later):** `sale_order` + `sale_order_item` screens (quotation → convert-to-invoice)
**Phase-3 (later):** `sale_return` + `sale_return_item` screens
**Separate future blueprint (Option A, Accounts module):** `receipt_payment` Engine + Screens, covering both Sale Receipts and Purchase Payments together

---

## 4. Combined Purchase + Sale Blueprint JSON

This is the **single JSON file** requested — replaces the old 14-task Purchase-only blueprint and adds every Sale task, so ERP-AI-Tool tracks BOTH modules' progress together via one drag-and-drop load.

**File:** `purchase_and_sale_blueprint.json`

```json
{
  "blueprint_name": "Purchase & Sale Modules - Medical ERP V2",
  "version": "1.0",
  "generated_for": "ERP-AI-Tool auto-progress tracking",
  "project_root": "C:\\Users\\Medical\\Desktop\\Medical-ERP-V2",
  "tasks": [
    {
      "id": "P01",
      "module": "Purchase",
      "phase": "Part-1 Database",
      "title": "Create purchase_order + purchase_order_item tables",
      "file": "database/0007_create_purchase_order.sql",
      "status": "pending"
    },
    {
      "id": "P02",
      "module": "Purchase",
      "phase": "Part-1 Database",
      "title": "Create purchase_invoice + purchase_invoice_item tables",
      "file": "database/0008_create_purchase_invoice.sql",
      "status": "pending"
    },
    {
      "id": "P03",
      "module": "Purchase",
      "phase": "Part-1 Database",
      "title": "Seed Purchase settings group",
      "file": "database/0009_purchase_settings_seed.sql",
      "status": "pending"
    },
    {
      "id": "P04",
      "module": "Purchase",
      "phase": "Part-1 Models",
      "title": "Extend ItemModel with get_low_stock_items()",
      "file": "models/item_model.py",
      "status": "pending"
    },
    {
      "id": "P05",
      "module": "Purchase",
      "phase": "Part-1 Models",
      "title": "Create PurchaseOrderModel",
      "file": "models/purchase_order_model.py",
      "status": "pending"
    },
    {
      "id": "P06",
      "module": "Purchase",
      "phase": "Part-1 Models",
      "title": "Create PurchaseInvoiceModel",
      "file": "models/purchase_invoice_model.py",
      "status": "pending"
    },
    {
      "id": "P07",
      "module": "Purchase",
      "phase": "Part-2 Engines",
      "title": "Create purchase_validator.py (PurchaseValidator + PurchaseOrderValidator)",
      "file": "engines/purchase_validator.py",
      "status": "pending"
    },
    {
      "id": "P08",
      "module": "Purchase",
      "phase": "Part-2 Engines",
      "title": "Create PurchaseOrderEngine",
      "file": "engines/purchase_order_engine.py",
      "status": "pending"
    },
    {
      "id": "P09",
      "module": "Purchase",
      "phase": "Part-2 Engines",
      "title": "Create PurchaseEngine",
      "file": "engines/purchase_engine.py",
      "status": "pending"
    },
    {
      "id": "P10",
      "module": "Purchase",
      "phase": "Part-3 Wiring",
      "title": "Wire PurchaseOrderEngine + PurchaseEngine (factory/construction order)",
      "file": "main.py",
      "status": "pending"
    },
    {
      "id": "P11",
      "module": "Purchase",
      "phase": "Part-3 Screens",
      "title": "Create PurchaseOrderFormScreen (auto low-stock suggestions + manual add)",
      "file": "screens/purchase_order_form_screen.py",
      "status": "pending"
    },
    {
      "id": "P12",
      "module": "Purchase",
      "phase": "Part-3 Screens",
      "title": "Create PurchaseOrderListScreen (WhatsApp/Email send buttons)",
      "file": "screens/purchase_order_list_screen.py",
      "status": "pending"
    },
    {
      "id": "P13",
      "module": "Purchase",
      "phase": "Part-3 Screens",
      "title": "Create PurchaseInvoiceFormScreen (GRN + Bill, link-to-PO)",
      "file": "screens/purchase_invoice_form_screen.py",
      "status": "pending"
    },
    {
      "id": "P14",
      "module": "Purchase",
      "phase": "Part-3 Screens",
      "title": "Create PurchaseInvoiceListScreen",
      "file": "screens/purchase_invoice_list_screen.py",
      "status": "pending"
    },
    {
      "id": "P15",
      "module": "Purchase",
      "phase": "Part-3 Dashboard",
      "title": "Wire Purchase Order + Purchase Invoice sidebar entries",
      "file": "screens/dashboard_screen.py",
      "status": "pending"
    },
    {
      "id": "P16",
      "module": "Purchase",
      "phase": "Part-3 Test",
      "title": "End-to-end test: low-stock -> PO -> WhatsApp/Email -> Invoice linked to PO -> PO marked Received -> stock/batch correct",
      "file": null,
      "status": "pending"
    },
    {
      "id": "P17",
      "module": "Purchase",
      "phase": "Phase-2 (Return)",
      "title": "Create purchase_return + purchase_return_item tables",
      "file": "database/0010_create_purchase_return.sql",
      "status": "pending"
    },
    {
      "id": "P18",
      "module": "Purchase",
      "phase": "Phase-2 (Return)",
      "title": "Create PurchaseReturnModel + PurchaseReturnEngine + Screen",
      "file": "engines/purchase_return_engine.py",
      "status": "pending"
    },
    {
      "id": "S01",
      "module": "Sale",
      "phase": "Part-1 Database",
      "title": "Create sale_invoice + sale_invoice_item tables",
      "file": "database/0011_create_sale_invoice.sql",
      "status": "pending"
    },
    {
      "id": "S02",
      "module": "Sale",
      "phase": "Part-1 Database",
      "title": "Create item_free_scheme table",
      "file": "database/0012_create_item_free_scheme.sql",
      "status": "pending"
    },
    {
      "id": "S03",
      "module": "Sale",
      "phase": "Part-1 Database",
      "title": "Seed Sale settings group (column visibility + free-scheme behaviour)",
      "file": "database/0013_sale_settings_seed.sql",
      "status": "pending"
    },
    {
      "id": "S04",
      "module": "Sale",
      "phase": "Part-1 Models",
      "title": "Extend customer_model.py with get_active_customers_by_area()",
      "file": "models/customer_model.py",
      "status": "pending"
    },
    {
      "id": "S05",
      "module": "Sale",
      "phase": "Part-1 Models",
      "title": "Extend item_model.py with get_nearest_expiry_batch()",
      "file": "models/item_model.py",
      "status": "pending"
    },
    {
      "id": "S06",
      "module": "Sale",
      "phase": "Part-1 Models",
      "title": "Create SaleInvoiceModel",
      "file": "models/sale_invoice_model.py",
      "status": "pending"
    },
    {
      "id": "S07",
      "module": "Sale",
      "phase": "Part-1 Models",
      "title": "Create ItemFreeSchemeModel",
      "file": "models/item_free_scheme_model.py",
      "status": "pending"
    },
    {
      "id": "S08",
      "module": "Sale",
      "phase": "Part-2 Engines",
      "title": "Create sale_validator.py (SaleInvoiceValidator + ItemFreeSchemeValidator)",
      "file": "engines/sale_validator.py",
      "status": "pending"
    },
    {
      "id": "S09",
      "module": "Sale",
      "phase": "Part-2 Engines",
      "title": "Create ItemFreeSchemeEngine",
      "file": "engines/item_free_scheme_engine.py",
      "status": "pending"
    },
    {
      "id": "S10",
      "module": "Sale",
      "phase": "Part-2 Engines",
      "title": "Create SaleEngine (free-scheme resolution, Net Rate formula, CC on Free Goods, stock deduction orchestration)",
      "file": "engines/sale_engine.py",
      "status": "pending"
    },
    {
      "id": "S11",
      "module": "Sale",
      "phase": "Part-3 Wiring",
      "title": "Wire ItemFreeSchemeEngine + SaleEngine (factory/construction order)",
      "file": "main.py",
      "status": "pending"
    },
    {
      "id": "S12",
      "module": "Sale",
      "phase": "Part-3 Screens",
      "title": "Create ItemFreeSchemeFormScreen + ItemFreeSchemeListScreen",
      "file": "screens/item_free_scheme_form_screen.py",
      "status": "pending"
    },
    {
      "id": "S13",
      "module": "Sale",
      "phase": "Part-3 Screens",
      "title": "Create SaleInvoiceFormScreen (Area->Customer combo, Settings-driven columns, row-level inline item combo grid, Free Qty/Net Rate mode toggle)",
      "file": "screens/sale_invoice_form_screen.py",
      "status": "pending"
    },
    {
      "id": "S14",
      "module": "Sale",
      "phase": "Part-3 Screens",
      "title": "Create SaleInvoiceListScreen",
      "file": "screens/sale_invoice_list_screen.py",
      "status": "pending"
    },
    {
      "id": "S15",
      "module": "Sale",
      "phase": "Part-3 Dashboard",
      "title": "Wire Sale Invoice + Item Free Scheme sidebar entries, wire btnNewSale",
      "file": "screens/dashboard_screen.py",
      "status": "pending"
    },
    {
      "id": "S16",
      "module": "Sale",
      "phase": "Part-3 Test",
      "title": "End-to-end test: create Free Scheme -> Sale Invoice Wholesale mode -> Area/Customer select -> inline item entry -> auto free_qty -> Net Rate mode toggle -> Save -> confirm stock reduced by qty+free_qty -> confirm CC present in Wholesale/absent in Retail",
      "file": null,
      "status": "pending"
    },
    {
      "id": "S17",
      "module": "Sale",
      "phase": "Phase-2 (Sale Order)",
      "title": "Create sale_order + sale_order_item tables, Model, Engine, Screens",
      "file": "database/0014_create_sale_order.sql",
      "status": "pending"
    },
    {
      "id": "S18",
      "module": "Sale",
      "phase": "Phase-3 (Sale Return)",
      "title": "Create sale_return + sale_return_item tables, Model, Engine, Screen",
      "file": "database/0015_create_sale_return.sql",
      "status": "pending"
    },
    {
      "id": "A01",
      "module": "Accounts",
      "phase": "Future (separate blueprint, Option A)",
      "title": "Create receipt_payment table (shared shape for Sale Receipts + Purchase Payments)",
      "file": "database/0016_create_receipt_payment.sql",
      "status": "pending"
    }
  ]
}
```

> **Note on Task Count:** 18 Purchase tasks (P01–P18) + 18 Sale tasks (S01–S18) + 1 Accounts placeholder (A01) = **37 tasks total**, replacing the old standalone 14-task Purchase-only blueprint. Load this file into ERP-AI-Tool via "📋 Load Blueprint" or drag-and-drop — it will auto-check any task whose `file` already exists in the Medical-ERP-V2 folder, exactly as `_auto_load_blueprint()` already does.

---

**Part 3 complete — Sale Module blueprint (Parts 1+2+3) fully documented, matching the Purchase Module's structure exactly.**

Combined blueprint JSON is ready to drop into ERP-AI-Tool. **No code has been written yet for either module** — both are design/blueprint only. Confirm and I'll begin actual implementation, starting with `database/0007_create_purchase_order.sql` (Purchase, since it was confirmed first) unless you'd prefer to start with Sale instead.
