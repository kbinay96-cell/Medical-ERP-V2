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