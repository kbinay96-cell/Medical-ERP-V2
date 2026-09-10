# Purchase Module — Part 3: Screens + ERP-AI-Tool Blueprint Tracking + Apply Code Format

---

## 1. Screens Layer (`screens/`)

Per project rule: "No SQL. No business logic." — Screens only collect input, call the Engine, and render whatever DTO comes back. Mirrors `screens/supplier_form_screen.py` / `screens/item_form_screen.py` exactly.

### 1.1 `screens/purchase_order_form_screen.py` (Phase-1 — auto-suggest + manual)

```python
class PurchaseOrderFormScreen(QDialog):
    """The starting point of the Purchase flow. Opens showing every
    low-stock item (live query) as a checked-by-default row; user can
    uncheck items, edit suggested qty, or search-and-add any other item
    manually. One PO = one supplier.

    Responsibilities:
    - On open: engine.get_low_stock_suggestions() -> populate grid with
      checkboxes (checked = will be included), suggested_qty pre-filled
      and editable, and an inline warning icon/tooltip on any row where
      already_ordered_elsewhere is non-empty (e.g. "Already in PO-0012
      (Sent) x50 — order again?") — informational only, never blocks Save.
    - "+ Add Item" button: searchable item combo (via item_lookup_registry)
      to add any item manually, is_auto_suggested=False for that row.
    - Supplier combo (searchable, via engines.supplier_engine) — required,
      chosen once per PO.
    - Remove button per row (unchecking is enough for auto-suggested rows;
      manually-added rows get an explicit remove/delete icon).
    - Save button -> PurchaseOrderEngine.create_purchase_order()
      -- only CHECKED rows go into the payload.
    - After successful save: offers immediate "📱 Send via WhatsApp" /
      "✉ Send via Email" buttons (same handlers as the List screen,
      Section 1.3) so the user doesn't have to go find the PO again.
    """
    def __init__(self, parent, engine: "PurchaseOrderEngine", supplier_engine): ...
    def _load_low_stock_suggestions(self): ...
    def _populate_supplier_combo(self): ...
    def _on_add_item_manually_clicked(self): ...
    def _on_row_check_toggled(self, row_index: int): ...
    def _collect_form_values(self) -> dict: ...
    def _on_save_clicked(self): ...
```

### 1.2 `screens/purchase_order_list_screen.py` (Phase-1)

```python
class PurchaseOrderListScreen(QWidget):
    """List/search/filter — mirrors screens/supplier_list_screen.py.
    Filters: Supplier, Status (Draft/Sent/Received/Cancelled), Date range.

    Per-row action buttons:
    - 📱 WhatsApp  -> _on_whatsapp_clicked()
    - ✉ Email      -> _on_email_clicked()
    - View (read-only detail)
    - Cancel (soft-delete, only if status is Draft/Sent)
    """
    def __init__(self, parent, engine: "PurchaseOrderEngine", supplier_engine): ...
    def refresh(self): ...

    def _on_whatsapp_clicked(self, purchase_order_id: int) -> None:
        """1. text_map = engine.build_supplier_message(purchase_order_id)
           2. supplier = supplier_engine.get_supplier(...) -> mobile_no
           3. url = f"https://wa.me/{normalized_mobile_no}?text={urllib.parse.quote(text_map['whatsapp_text'])}"
           4. webbrowser.open(url)
           5. engine.mark_sent(purchase_order_id, sent_via='whatsapp', current_user_id)
           6. self.refresh()
        If supplier.mobile_no is blank, show a warning instead of opening
        a broken link — never silently fail."""
        ...

    def _on_email_clicked(self, purchase_order_id: int) -> None:
        """1. text_map = engine.build_supplier_message(purchase_order_id)
           2. supplier = supplier_engine.get_supplier(...) -> email
           3. url = f"mailto:{email}?subject={urllib.parse.quote(text_map['email_subject'])}&body={urllib.parse.quote(text_map['email_body'])}"
           4. webbrowser.open(url)
           5. engine.mark_sent(purchase_order_id, sent_via='email', current_user_id)
           6. self.refresh()
        If supplier.email is blank, show a warning instead."""
        ...

    def _on_cancel_clicked(self, purchase_order_id: int): ...
```

### 1.3 `screens/purchase_invoice_form_screen.py` (Phase-1 — GRN + Bill)

```python
class PurchaseInvoiceFormScreen(QDialog):
    """Add-only screen (Purchase Invoices are not edited after posting —
    corrections go through Purchase Return, per accounting best-practice
    already implied by stock_transaction_model.py's append-only design).

    Responsibilities:
    - Header fields: Supplier (searchable combo), Invoice Number,
      Invoice Date (BS), optional "Link to Purchase Order" combo
      (searchable, filtered to this supplier's Draft/Sent POs — pre-fills
      line items from the selected PO if chosen, still fully editable)
    - Line-item grid: Item, Batch No, Expiry Month/Year, Qty, Free Qty,
      Purchase Rate, Discount %, MRP, Sale Rate — CC% and Landing Cost
      are READ-ONLY, Engine-computed, shown live as the user types
    - Invoice-level: Freight Amount, Other Charges (split across lines by Engine)
    - Save button -> PurchaseEngine.create_purchase_invoice()
      (payload includes purchase_order_id if one was linked — Engine
      marks that PO 'Received' automatically, see Part-2 Section 2)
    - Surfaces ValidationError/DuplicateRecordError messages back to user
    """
    def __init__(self, parent, engine: "PurchaseEngine", purchase_order_engine): ...
    def _connect_signals(self): ...
    def _populate_supplier_combo(self): ...
    def _on_link_po_selected(self, purchase_order_id: int): ...
    def _add_line_row(self): ...
    def _recalculate_line_preview(self, row_index: int): ...
    def _collect_form_values(self) -> dict: ...
    def _on_save_clicked(self): ...
```

### 1.4 `screens/purchase_invoice_list_screen.py` (Phase-1)

```python
class PurchaseInvoiceListScreen(QWidget):
    """List/search/filter — mirrors screens/supplier_list_screen.py exactly.
    Filters: Supplier, Status, Date range. Actions: View (read-only detail),
    Cancel (soft-delete with reason), Print (future — not in this phase)."""
    def __init__(self, parent, engine: "PurchaseEngine"): ...
    def refresh(self): ...
    def _on_cancel_clicked(self, purchase_invoice_id: int): ...
```

### 1.5 `screens/purchase_return_form_screen.py` (Phase-2)

Same shape as `screens/item_batch_dialog.py` — small, single-purpose, references an existing `item_batch_id`, collects return qty/reason, calls `PurchaseReturnEngine.create_return()`.

### 1.6 Dashboard Wiring

`screens/dashboard_screen.py` needs **two** sidebar entries — "Purchase Order" (opens `PurchaseOrderListScreen`) and "Purchase Invoice" (opens `PurchaseInvoiceListScreen`) — same pattern as the existing `open_supplier_form()` / `open_customer_form()` methods.

---

## 2. Wiring Checklist (what has to be constructed where)

```python
# Wherever engines are constructed (likely main.py or a lazy factory,
# mirroring how item_engine.py wires ItemEngine's dependencies):

from models.purchase_order_model import PurchaseOrderModel
from models.purchase_invoice_model import PurchaseInvoiceModel
from models.item_model import ItemModel
from engines.purchase_order_engine import PurchaseOrderEngine
from engines.purchase_engine import PurchaseEngine
from engines.item_engine import ItemEngine  # already exists — reuse the same instance
from engines.item_lookup_registry import manufacturer_lookup, country_tax_lookup

# 1. PurchaseOrderEngine built FIRST — PurchaseEngine depends on it
purchase_order_engine = PurchaseOrderEngine(
    model=PurchaseOrderModel(),
    item_model=ItemModel(),    # reuse existing ItemModel, don't build a second one
    date_engine=None,          # lazy-loaded inside, same pattern as SupplierEngine
    settings_engine=None,      # lazy-loaded inside
)

# 2. PurchaseEngine built SECOND — needs both item_engine AND purchase_order_engine
purchase_engine = PurchaseEngine(
    model=PurchaseInvoiceModel(),
    date_engine=None,
    settings_engine=None,
    item_engine=item_engine_instance,           # MUST be the same ItemEngine the app already uses
    purchase_order_engine=purchase_order_engine, # from step 1
    country_tax_lookup_fn=country_tax_lookup,
    manufacturer_lookup_fn=manufacturer_lookup,
)
```

> **Order matters:** `purchase_order_engine` must exist before `purchase_engine` is constructed, since it's an injected dependency (see Part-2, Section 2.2 constructor signature).

---

## 3. ERP-AI-Tool Blueprint JSON (auto-progress tracking)

Ye JSON file **as-is** ERP-AI-Tool mein load ho sakti hai — "📋 Load Blueprint" button se ya seedha chat window mein **drag-and-drop** karke. Load hote hi ERP-AI-Tool har task ke `file` field ko dekh kar check karega ki wo file Medical-ERP-V2 folder mein exist karti hai ya nahi — exist karti hai to task automatically "done" mark ho jayega (jaisa `_auto_load_blueprint()` already karta hai).

**File:** `purchase_module_blueprint.json` — updated version, alag file ke roop mein diya ja raha hai, seedha download karke ERP-AI-Tool mein load karo (purani wali replace kar dena).

Iske andar ke tasks (18 total, updated):
- **T01–T06**: Part-1 (Database migrations for `purchase_order`+`purchase_invoice`, `ItemModel.get_low_stock_items()` extension, Model files, Settings seed)
- **T07–T11**: Part-2 (`purchase_validator.py`, `purchase_order_engine.py`, `purchase_engine.py`, Phase-2 `purchase_return_engine.py`)
- **T12–T18**: Part-3 (PO Screens, Invoice Screens, wiring, Dashboard, end-to-end test)

---

## 4. Apply Code Format — Isi Format Mein Code Doonga

Jab bhi hum in files ko actual likhna shuru karenge, main **teen modes** mein se koi ek use karoonga (yaad dilane ke liye — ERP-AI-Tool ke "📜 Show Format Rules" button se bhi ye hamesha mil jayega):

**Naya file (jaise `engines/purchase_order_engine.py` pehli baar):**
```
FILE: engines/purchase_order_engine.py
#start#
...poora file content...
#end#
```

**Function/Method replace naam se (jab kisi ek method mein sudhaar karna ho):**
```
FILE: engines/purchase_engine.py
#find#
PurchaseEngine.create_purchase_invoice
#replace#
    def create_purchase_invoice(self, payload, current_user_id):
        ...naya poora method...
#end#
```

**Chhoti si line replace (literal exact match):**
```
FILE: engines/purchase_engine.py
#find#
...exact purani line(s)...
#replace#
...nayi line(s)...
#end#
```

Tum isi text ko copy karke `Apply Code` tab mein paste karoge, "Apply" dabaoge — file seedha likhi jayegi, backup automatic banega, koi API cost nahi.

---

## 5. Suggested Build Order (Step-by-Step, ek baar mein ek)

**Part 1 — Database & Models:**
1. `database/0007_create_purchase_order.sql` (purchase_order + purchase_order_item)
2. `database/0008_create_purchase_invoice.sql` (purchase_invoice + purchase_invoice_item)
3. `database/0009_purchase_settings_seed.sql` (Settings group "Purchase")
4. Extension to existing `models/item_model.py` — add `get_low_stock_items()`
5. `models/purchase_order_model.py`
6. `models/purchase_invoice_model.py`

**Part 2 — Engines & Validators:**
7. `engines/purchase_validator.py` (both `PurchaseValidator` + `PurchaseOrderValidator`)
8. `engines/purchase_order_engine.py`
9. `engines/purchase_engine.py`

**Part 3 — Screens & Wiring:**
10. Wiring/factory code (Section 2 above)
11. `screens/purchase_order_form_screen.py`
12. `screens/purchase_order_list_screen.py`
13. `screens/purchase_invoice_form_screen.py`
14. `screens/purchase_invoice_list_screen.py`
15. Dashboard sidebar entries (2 items)
16. Test: low-stock item dikhta hai PO screen mein → PO banao → WhatsApp/Email link khulta hai → Purchase Invoice banao (PO se link karke) → confirm PO "Received" ho gaya → confirm `item_batch` + stock sahi bana

**Phase-2 (baad mein):** `database/0010_create_purchase_return.sql`, `models/purchase_return_model.py`, `engines/purchase_return_engine.py`, `screens/purchase_return_form_screen.py`

---

**Part 3 complete.**
