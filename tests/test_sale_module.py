import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from engines.sale_engine import SaleEngine
from engines.exceptions import ValidationError
from engines.sale_return_engine import SaleReturnEngine
from engines.sale_return_validator import SaleReturnValidator
from models.sale_invoice_model import SaleInvoiceModel, SaleInvoiceSearchFilters


class _Cursor:
    def __init__(self):
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.executions.append((sql, params))

    def fetchone(self):
        return {"total": 1}

    def fetchall(self):
        return []


class _Connection:
    def __init__(self):
        self.query_cursor = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, **_kwargs):
        return self.query_cursor


class SaleInvoiceSearchTests(unittest.TestCase):
    def test_model_applies_area_and_date_filters_to_count_and_results(self):
        connection = _Connection()
        filters = SaleInvoiceSearchFilters(
            area_id=12,
            date_from_ad="2026-09-01",
            date_to_ad="2026-10-03",
        )

        with patch("models.sale_invoice_model._get_connection", return_value=connection):
            rows, total = SaleInvoiceModel().search(filters)

        self.assertEqual(rows, [])
        self.assertEqual(total, 1)
        self.assertEqual(len(connection.query_cursor.executions), 2)
        for sql, params in connection.query_cursor.executions:
            self.assertIn("si.area_id = %s", sql)
            self.assertIn("si.invoice_date_ad >= %s", sql)
            self.assertIn("si.invoice_date_ad <= %s", sql)
            self.assertEqual(params[:3], [12, "2026-09-01", "2026-10-03"])


class SaleInvoiceCancelTests(unittest.TestCase):
    def _make_engine(self):
        engine = SaleEngine.__new__(SaleEngine)
        engine._model = MagicMock()
        engine._item_engine = MagicMock()
        engine._model.get_by_id.return_value = {
            "sale_invoice_id": 41,
            "status": "Posted",
            "amount_paid_now": 0,
        }
        engine._model.has_receipt_allocations.return_value = False
        engine._model.get_returnable_items.return_value = [{"already_returned_qty": 0}]
        engine._model.get_items_by_invoice.return_value = [
            {"item_batch_id": 8, "qty": 3, "free_qty": 1}
        ]
        engine._now_bs = MagicMock(return_value="2083-06-17")
        return engine

    def test_cancelling_posted_invoice_restores_stock_and_records_reason(self):
        engine = self._make_engine()
        with patch("engines.permission_enforcer.check_permission"):
            engine.cancel_sale_invoice(41, 9, "Duplicate invoice")

        engine._item_engine.post_stock_movement.assert_called_once_with(
            item_batch_id=8,
            transaction_type="ADJUSTMENT",
            quantity_change=4.0,
            current_user_id=9,
            reference_type="sale_invoice_cancel",
            reference_id=41,
        )
        engine._model.soft_delete.assert_called_once()
        self.assertEqual(engine._model.soft_delete.call_args.kwargs["reason"], "Duplicate invoice")

    def test_cannot_cancel_invoice_with_payments_or_returns(self):
        for update in (
            {"amount_paid_now": 10},
            {"returned_qty": 1},
        ):
            with self.subTest(update=update):
                engine = self._make_engine()
                if "returned_qty" in update:
                    engine._model.get_returnable_items.return_value = [
                        {"already_returned_qty": update["returned_qty"]}
                    ]
                else:
                    engine._model.get_by_id.return_value.update(update)

                with patch("engines.permission_enforcer.check_permission"):
                    with self.assertRaises(ValidationError):
                        engine.cancel_sale_invoice(41, 9, "Duplicate invoice")

                engine._item_engine.post_stock_movement.assert_not_called()
                engine._model.soft_delete.assert_not_called()


class SaleFreeSchemeTests(unittest.TestCase):
    def _make_engine(self):
        item = SimpleNamespace(
            item_name="Medicine",
            sale_rate=100,
            mrp=120,
            purchase_rate=50,
            manufacturer_id=3,
            packing="10 tablets",
        )
        item_engine = MagicMock()
        item_engine.get_item.return_value = item
        item_free_scheme_engine = MagicMock()
        item_free_scheme_engine.get_scheme_for_item.return_value = (10, 1)

        engine = SaleEngine(
            model=MagicMock(),
            item_engine=item_engine,
            item_free_scheme_engine=item_free_scheme_engine,
            country_tax_lookup_fn=MagicMock(return_value=(0, 0)),
            manufacturer_lookup_fn=MagicMock(return_value={}),
        )
        engine._pick_nearest_expiry_batch = lambda _item_id: {
            "item_batch_id": 8,
            "batch_no": "B-1",
            "expiry_month": 12,
            "expiry_year": 2027,
        }
        return engine, item_free_scheme_engine

    def test_disabled_free_scheme_does_not_apply_free_qty_or_net_rate(self):
        engine, scheme_engine = self._make_engine()
        engine.is_free_scheme_enabled = lambda: False

        free_qty_line = engine.compute_line(
            {"item_id": 1, "qty": 10, "entry_mode": "free_qty"},
            is_wholesale=True,
        )
        net_rate_line = engine.compute_line(
            {"item_id": 1, "qty": 10, "entry_mode": "net_rate"},
            is_wholesale=True,
        )

        self.assertEqual(free_qty_line["free_qty"], 0)
        self.assertEqual(net_rate_line["free_qty"], 0)
        self.assertEqual(net_rate_line["rate"], 100)
        scheme_engine.get_scheme_for_item.assert_not_called()

    def test_enabled_free_scheme_still_applies_in_wholesale(self):
        engine, scheme_engine = self._make_engine()
        engine.is_free_scheme_enabled = lambda: True

        line = engine.compute_line(
            {"item_id": 1, "qty": 10, "entry_mode": "free_qty"},
            is_wholesale=True,
        )

        self.assertEqual(line["free_qty"], 1)
        scheme_engine.get_scheme_for_item.assert_called_once_with(1)


class SaleReturnDraftTests(unittest.TestCase):
    def _make_engine(self):
        model = MagicMock()
        model.get_by_id.return_value = {
            "sale_return_id": 9,
            "status": "Draft",
            "is_deleted": False,
        }
        model.update_draft_with_items.return_value = True
        model.get_returned_qty_for_invoice_item.return_value = 0

        sale_invoice_model = MagicMock()
        sale_invoice_model.get_by_id.return_value = {
            "sale_invoice_id": 4,
            "customer_id": 2,
            "status": "Posted",
        }
        sale_invoice_model.get_returnable_items.return_value = [
            {
                "sale_invoice_item_id": 30,
                "item_id": 12,
                "item_batch_id": 55,
                "batch_no": "B-55",
                "expiry_month": 12,
                "expiry_year": 2027,
                "qty": 5,
                "rate": 20,
                "discount_percent": 10,
                "discount_amount": 10,
                "cc_percent": 0,
                "cc_amount": 0,
                "tax_percent": 0,
                "tax_amount": 0,
            }
        ]
        item_engine = MagicMock()
        date_engine = MagicMock()
        date_engine.ad_to_bs.return_value = "2083-06-17"
        engine = SaleReturnEngine(
            model=model,
            sale_invoice_model=sale_invoice_model,
            item_engine=item_engine,
            date_engine=date_engine,
        )
        engine.get_by_id = MagicMock(return_value=SimpleNamespace(sale_return_id=9))
        return engine, model, sale_invoice_model, item_engine

    def test_update_draft_validates_excluding_current_return(self):
        engine, model, invoice_model, item_engine = self._make_engine()

        result = engine.update_draft_return(
            sale_return_id=9,
            sale_invoice_id=4,
            customer_id=2,
            return_date_ad=date(2026, 10, 3),
            return_reason="Damaged",
            refund_mode="Advance",
            return_lines=[{"sale_invoice_item_id": 30, "return_qty": 2}],
            updated_by=6,
        )

        self.assertEqual(result.sale_return_id, 9)
        invoice_model.get_returnable_items.assert_called_once_with(
            4, exclude_return_id=9
        )
        model.get_returned_qty_for_invoice_item.assert_called_once_with(30, 9)
        model.update_draft_with_items.assert_called_once()
        item_engine.post_stock_movement.assert_not_called()

    def test_posting_edited_draft_adds_returned_stock(self):
        engine, _model, _invoice_model, item_engine = self._make_engine()

        engine.update_draft_return(
            sale_return_id=9,
            sale_invoice_id=4,
            customer_id=2,
            return_date_ad=date(2026, 10, 3),
            return_reason="Damaged",
            refund_mode="Cash Refund",
            return_lines=[{"sale_invoice_item_id": 30, "return_qty": 2}],
            updated_by=6,
            status="Posted",
        )

        item_engine.post_stock_movement.assert_called_once_with(
            item_batch_id=55,
            quantity_change=2.0,
            transaction_type="SALE_RETURN",
            reference_id=9,
            created_by=6,
        )

    def test_validator_excludes_existing_draft_from_returned_quantity(self):
        returned_qty = MagicMock(return_value=2)
        validator = SaleReturnValidator(
            return_number_exists_fn=MagicMock(return_value=False),
            returned_qty_fn=returned_qty,
        )

        result = validator.validate_lines(
            [{"sale_invoice_item_id": 30, "return_qty": 3}],
            {30: {"qty": 5}},
            exclude_return_id=9,
        )

        self.assertTrue(result.is_valid)
        returned_qty.assert_called_once_with(30, 9)


if __name__ == "__main__":
    unittest.main()
