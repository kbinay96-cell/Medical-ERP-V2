from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from screens.purchase_return_form_screen import PurchaseReturnFormScreen
from screens.purchase_return_list_screen import PurchaseReturnListScreen


APP = QApplication.instance() or QApplication([])


def _return_dto(return_id, status="Posted"):
    return SimpleNamespace(
        purchase_return_id=return_id,
        return_number=f"PRTN-{return_id:04d}",
        purchase_invoice_id=24,
        supplier_id=6,
        supplier_name="Demo Supplier",
        internal_ref_number="PINV-0024",
        return_date_bs="2083-06-17",
        settlement_mode="Adjust Against Payable",
        grand_total=125.5,
        status=status,
        cancellation_reason=None,
        return_reason="Damaged item",
        total_qty=2,
        total_free_qty=1,
        lines=[],
        remarks=None,
    )


class FakeSupplierEngine:
    def get_active_suppliers(self):
        return [SimpleNamespace(supplier_id=6, supplier_name="Demo Supplier")]


class FakePurchaseReturnEngine:
    def __init__(self):
        self.filters = []
        self.rows = [_return_dto(7)]

    def search(self, filters):
        self.filters.append(filters)
        return self.rows

    def get_by_id(self, _return_id):
        return _return_dto(7)

    def get_returnable_lines(self, _invoice_id):
        return [{
            "purchase_invoice_item_id": 91,
            "item_id": 13,
            "batch_no": "B-1",
            "expiry_month": 8,
            "expiry_year": 2027,
            "qty": 5,
            "already_returned_qty": 1,
            "remaining_returnable_qty": 4,
            "free_qty": 3,
            "already_returned_free_qty": 1,
            "remaining_returnable_free_qty": 2,
        }]

    def create_return(self, **kwargs):
        self.create_kwargs = kwargs
        return SimpleNamespace(return_number="PRTN-0008")


class TestPurchaseReturnList:
    def test_filters_and_search_results_are_wired(self):
        engine = FakePurchaseReturnEngine()
        screen = PurchaseReturnListScreen(
            None, engine, FakeSupplierEngine(), current_user_id=4
        )

        assert screen.tblReturns.rowCount() == 1
        assert screen.btnCancel.isEnabled()
        assert not screen.btnDelete.isEnabled()
        assert engine.filters[-1].page_size == 100
        assert engine.filters[-1].supplier_id is None
        screen.cmbSupplier.setCurrentIndex(1)
        assert engine.filters[-1].supplier_id == 6

    def test_only_posted_returns_can_be_cancelled_and_drafts_deleted(self):
        engine = FakePurchaseReturnEngine()
        engine.rows = [_return_dto(8, status="Draft")]
        screen = PurchaseReturnListScreen(
            None, engine, FakeSupplierEngine(), current_user_id=4
        )

        assert screen.btnDelete.isEnabled()
        assert not screen.btnCancel.isEnabled()

    def test_posted_return_cancel_requires_dialog_reason_and_refreshes(self):
        engine = FakePurchaseReturnEngine()
        screen = PurchaseReturnListScreen(
            None, engine, FakeSupplierEngine(), current_user_id=4
        )
        screen.tblReturns.selectRow(0)
        reason_dialog = SimpleNamespace(exec=lambda: 1, get_reason=lambda: "Duplicate entry")
        with (
            patch("screens.purchase_return_list_screen.CancellationReasonDialog", return_value=reason_dialog),
            patch("screens.purchase_return_list_screen.msg.show_info"),
        ):
            engine.cancel_return = lambda *args: setattr(engine, "cancelled", args)
            screen._cancel_selected()

        assert engine.cancelled == (7, "Duplicate entry", 4)
        assert len(engine.filters) == 2


class TestPurchaseReturnForm:
    def test_paid_and_free_quantities_are_limited_and_submitted_independently(self):
        return_engine = FakePurchaseReturnEngine()
        purchase_engine = SimpleNamespace(
            search_purchase_invoices=lambda **_kwargs: (
                [SimpleNamespace(
                    purchase_invoice_id=24,
                    internal_ref_number="PINV-0024",
                    invoice_number="SUP-INV-24",
                    invoice_date_bs="2083-06-15",
                )],
                1,
            )
        )
        item_engine = SimpleNamespace(
            get_item=lambda _item_id: SimpleNamespace(item_name="Demo Tablet")
        )
        screen = PurchaseReturnFormScreen(
            None,
            return_engine,
            purchase_engine,
            FakeSupplierEngine(),
            item_engine,
            current_user_id=4,
        )
        screen.cmbSupplier.setCurrentIndex(1)
        screen._load_invoices()
        screen.cmbInvoice.setCurrentIndex(1)
        screen._load_selected_invoice()

        paid = screen.tblItems.cellWidget(0, 8)
        free = screen.tblItems.cellWidget(0, 9)
        assert paid.maximum() == 4
        assert free.maximum() == 2
        paid.setValue(2)
        free.setValue(1)
        assert screen._collect_return_lines() == [{
            "purchase_invoice_item_id": 91,
            "return_qty": 2,
            "return_free_qty": 1,
        }]

        screen.txtReason.setPlainText("Damaged goods")
        with patch("screens.purchase_return_form_screen.msg.show_info"):
            screen._post_return()

        assert return_engine.create_kwargs["purchase_invoice_id"] == 24
        assert return_engine.create_kwargs["supplier_id"] == 6
        assert isinstance(return_engine.create_kwargs["return_date_ad"], date)
        assert return_engine.create_kwargs["status"] == "Posted"
        assert return_engine.create_kwargs["return_lines"][0]["return_free_qty"] == 1
