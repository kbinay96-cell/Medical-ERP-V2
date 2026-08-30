# tests/test_sale_validator.py
import unittest

from engines.sale_validator import SaleValidator


class SaleValidatorTests(unittest.TestCase):
    def test_header_requires_customer(self):
        ok, msg = SaleValidator.validate_invoice_header(
            {"invoice_date_bs": "2082-04-01", "lines": [{"item_id": 1}]}
        )
        self.assertFalse(ok)
        self.assertIn("Customer", msg)

    def test_header_requires_lines(self):
        ok, msg = SaleValidator.validate_invoice_header(
            {"customer_id": 1, "invoice_date_bs": "2082-04-01", "lines": []}
        )
        self.assertFalse(ok)
        self.assertIn("line", msg.lower())

    def test_line_requires_batch(self):
        ok, msg = SaleValidator.validate_invoice_line(
            {"item_id": 1, "qty": 1, "rate": 10}
        )
        self.assertFalse(ok)
        self.assertIn("Batch", msg)

    def test_valid_line(self):
        ok, msg = SaleValidator.validate_invoice_line(
            {"item_id": 1, "item_batch_id": 9, "qty": 2, "rate": 50, "discount_percent": 10}
        )
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
