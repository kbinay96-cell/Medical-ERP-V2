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