import unittest
from unittest.mock import Mock, patch

from engines.dashboard_engine import SIDEBAR_MODULES
from engines.exceptions import ValidationError
from engines.purchase_engine import PurchaseEngine, PurchaseInvoiceLineDTO
from engines.purchase_order_engine import PurchaseOrderEngine
from engines.purchase_validator import PurchaseOrderValidator, PurchaseValidator


class PurchaseValidatorTests(unittest.TestCase):
    def test_invoice_requires_supplier(self):
        valid, message = PurchaseValidator.validate_invoice_header(
            {
                "invoice_number": "BILL-1",
                "invoice_date_bs": "2082-04-01",
                "lines": [{"item_id": 1}],
            }
        )
        self.assertFalse(valid)
        self.assertEqual(message, "Supplier is required.")

    def test_invoice_line_requires_paid_or_free_quantity(self):
        valid, message = PurchaseValidator.validate_invoice_line(
            {
                "item_id": 1,
                "qty": 0,
                "free_qty": 0,
                "purchase_rate": 0,
                "expiry_month": 1,
                "expiry_year": 2083,
                "mrp": 0,
                "batch_no": "B-1",
            }
        )
        self.assertFalse(valid)
        self.assertEqual(
            message,
            "Either quantity or free quantity must be greater than zero.",
        )

    def test_purchase_order_requires_a_line(self):
        valid, message = PurchaseOrderValidator.validate_order_header(
            {"supplier_id": 1, "order_date_bs": "2082-04-01", "lines": []}
        )
        self.assertFalse(valid)
        self.assertEqual(message, "At least one line item is required.")


class PurchaseEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = PurchaseEngine(
            model=Mock(),
            date_engine=None,
            settings_engine=None,
            item_engine=Mock(),
            purchase_order_engine=Mock(),
        )

    def test_invoice_charges_are_allocated_by_total_units(self):
        lines = [
            PurchaseInvoiceLineDTO(
                item_id=1, batch_no="A", expiry_month=1, expiry_year=2085,
                qty=2, free_qty=0, purchase_rate=10, discount_percent=0,
                cc_percent=0, mrp=20, sale_rate=15,
            ),
            PurchaseInvoiceLineDTO(
                item_id=2, batch_no="B", expiry_month=1, expiry_year=2085,
                qty=1, free_qty=1, purchase_rate=20, discount_percent=0,
                cc_percent=0, mrp=30, sale_rate=25,
            ),
        ]

        allocated = self.engine._allocate_invoice_level_charges(lines, 40, 20)

        self.assertEqual(
            [(line.freight_allocated, line.other_charges_allocated) for line in allocated],
            [(20, 10), (20, 10)],
        )

    def test_landing_cost_includes_discount_cc_and_allocated_charges(self):
        line = PurchaseInvoiceLineDTO(
            item_id=1,
            batch_no="A",
            expiry_month=1,
            expiry_year=2085,
            qty=10,
            free_qty=2,
            purchase_rate=100,
            discount_percent=10,
            cc_percent=5,
            mrp=150,
            sale_rate=120,
            freight_allocated=24,
            other_charges_allocated=12,
        )

        calculated = self.engine._calculate_line_amounts(line)

        self.assertEqual(calculated.discount_amount, 100)
        self.assertEqual(calculated.cc_amount, 10)
        self.assertEqual(calculated.landing_cost_per_unit, 78.8333)

    def test_invoice_maps_persisted_freight_column(self):
        self.engine._model.get_by_id.return_value = {
            "purchase_invoice_id": 3,
            "internal_ref_number": "PINV-0003",
            "invoice_number": "BILL-3",
            "supplier_id": 7,
            "invoice_date_bs": "2082-04-01",
            "grand_total": 124,
            "status": "Posted",
            "total_freight_amount": 20,
            "total_other_charges": 10,
        }
        self.engine._model.get_items_by_invoice.return_value = [
            {
                "item_id": 1,
                "batch_no": "A",
                "expiry_month": 1,
                "expiry_year": 2085,
                "qty": 1,
                "free_qty": 0,
                "purchase_rate": 100,
                "discount_percent": 0,
                "cc_percent": 0,
                "mrp": 150,
                "sale_rate": 120,
                "discount_amount": 0,
                "cc_amount": 0,
                "freight_amount_allocated": 20,
                "other_charges_allocated": 10,
                "landing_cost_per_unit": 130,
            }
        ]

        invoice = self.engine.get_purchase_invoice(3)

        self.assertEqual(invoice.lines[0].freight_allocated, 20)
        self.assertEqual(invoice.total_freight, 20)

    @patch("engines.permission_enforcer.check_permission")
    @patch("engines.date_engine.ad_to_bs", return_value="2083-06-01")
    def test_cancel_records_reason_and_audit_user(self, _ad_to_bs, _check_permission):
        self.engine._model.get_by_id.return_value = {
            "purchase_invoice_id": 3,
            "status": "Posted",
        }
        self.engine._model.soft_delete.return_value = True

        self.engine.cancel_purchase_invoice(3, current_user_id=4, reason="  Duplicate bill  ")

        call = self.engine._model.soft_delete.call_args.kwargs
        self.assertEqual(call["purchase_invoice_id"], 3)
        self.assertEqual(call["deleted_by"], 4)
        self.assertEqual(call["reason"], "Duplicate bill")


class PurchaseOrderEngineTests(unittest.TestCase):
    def setUp(self):
        self.model = Mock()
        self.engine = PurchaseOrderEngine(
            model=self.model,
            item_model=Mock(),
            date_engine=None,
            settings_engine=None,
        )

    @patch("engines.settings_engine.get_setting", return_value="PO-")
    def test_po_number_uses_configured_prefix_and_model_sequence(self, _get_setting):
        self.model.get_last_po_number_sequence.return_value = 7

        self.assertEqual(self.engine.generate_po_number(), "PO-0008")
        self.model.get_last_po_number_sequence.assert_called_once_with("PO-")

    @patch("engines.permission_enforcer.check_permission")
    @patch("engines.purchase_order_engine.PurchaseOrderValidator.validate_order_header", return_value=(True, ""))
    @patch("engines.purchase_order_engine.PurchaseOrderValidator.validate_order_line", return_value=(True, ""))
    @patch("engines.date_engine.ad_to_bs", return_value="2083-06-01")
    def test_create_order_uses_model_data_contract(
        self, _ad_to_bs, _validate_line, _validate_header, _check_permission
    ):
        self.model.insert_order.return_value = 9
        self.engine.generate_po_number = Mock(return_value="PO-0009")

        order = self.engine.create_purchase_order(
            {
                "supplier_id": 2,
                "order_date_bs": "2083-06-01",
                "lines": [
                    {
                        "item_id": 5,
                        "ordered_qty": 12,
                        "rate": 20,
                        "is_auto_suggested": True,
                    }
                ],
            },
            current_user_id=4,
        )

        self.assertEqual(order.purchase_order_id, 9)
        self.assertEqual(order.status, "Draft")
        self.model.insert_order_item.assert_called_once()
        call = self.model.insert_order_item.call_args.kwargs
        self.assertEqual(call["purchase_order_id"], 9)
        self.assertEqual(call["data"]["item_id"], 5)
        self.assertEqual(call["data"]["ordered_qty"], 12.0)

    @patch("engines.permission_enforcer.check_permission")
    def test_received_order_cannot_be_cancelled(self, _check_permission):
        self.model.get_by_id.return_value = {"status": "Received"}

        with self.assertRaises(ValidationError):
            self.engine.cancel_purchase_order(9, current_user_id=4)

        self.model.soft_delete.assert_not_called()


class PurchaseDashboardTests(unittest.TestCase):
    def test_purchase_invoice_list_is_exposed_in_sidebar(self):
        self.assertIn("Purchase Invoice List", SIDEBAR_MODULES["Purchase"])


if __name__ == "__main__":
    unittest.main()
