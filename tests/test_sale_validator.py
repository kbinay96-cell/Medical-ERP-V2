# tests/test_sale_validator.py
import unittest

from engines.sale_validator import (
    ItemFreeSchemeValidator,
    SaleInvoiceValidator,
    ValidationResult,
)


def _number_always_false(number: str, exclude_id: int | None = None) -> bool:
    return False


def _number_always_true(number: str, exclude_id: int | None = None) -> bool:
    return True


def _scheme_always_false(item_id: int, exclude_id: int | None = None) -> bool:
    return False


def _scheme_always_true(item_id: int, exclude_id: int | None = None) -> bool:
    return True


class ValidationResultTests(unittest.TestCase):
    def test_empty_is_valid(self):
        result = ValidationResult()
        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])

    def test_add_error(self):
        result = ValidationResult()
        result.add("Something went wrong.")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.errors, ["Something went wrong."])

    def test_multiple_errors(self):
        result = ValidationResult()
        result.add("Error 1")
        result.add("Error 2")
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 2)


class SaleInvoiceValidatorHeaderTests(unittest.TestCase):
    def setUp(self):
        self.validator = SaleInvoiceValidator(number_exists_fn=_number_always_false)

    def test_header_requires_customer(self):
        result = self.validator.validate_header({
            "invoice_date_bs": "2082-04-01",
            "sale_mode": "Retail",
        })
        self.assertFalse(result.is_valid)
        self.assertIn("Customer is mandatory.", result.errors)

    def test_header_requires_invoice_date(self):
        result = self.validator.validate_header({
            "customer_id": 1,
            "sale_mode": "Retail",
        })
        self.assertFalse(result.is_valid)
        self.assertIn("Invoice Date (BS) is mandatory.", result.errors)

    def test_header_rejects_invalid_sale_mode(self):
        result = self.validator.validate_header({
            "customer_id": 1,
            "invoice_date_bs": "2082-04-01",
            "sale_mode": "Invalid",
        })
        self.assertFalse(result.is_valid)
        self.assertIn("Sale Mode must be either 'Retail' or 'Wholesale'.", result.errors)

    def test_header_rejects_invalid_payment_type(self):
        result = self.validator.validate_header({
            "customer_id": 1,
            "invoice_date_bs": "2082-04-01",
            "sale_mode": "Retail",
            "payment_type": "Cheque",
        })
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Payment Type" in e for e in result.errors))

    def test_header_rejects_negative_amount_paid(self):
        result = self.validator.validate_header({
            "customer_id": 1,
            "invoice_date_bs": "2082-04-01",
            "sale_mode": "Retail",
            "amount_paid_now": -10,
        })
        self.assertFalse(result.is_valid)
        self.assertIn("Amount paid now cannot be negative.", result.errors)

    def test_header_rejects_paid_exceeding_total(self):
        result = self.validator.validate_header({
            "customer_id": 1,
            "invoice_date_bs": "2082-04-01",
            "sale_mode": "Retail",
            "grand_total": 100,
            "amount_paid_now": 200,
        })
        self.assertFalse(result.is_valid)
        self.assertIn("Amount paid now cannot exceed grand total.", result.errors)

    def test_header_rejects_duplicate_invoice_number(self):
        validator = SaleInvoiceValidator(number_exists_fn=_number_always_true)
        result = validator.validate_header({
            "customer_id": 1,
            "invoice_date_bs": "2082-04-01",
            "sale_mode": "Retail",
            "invoice_number": "SINV-0001",
        })
        self.assertFalse(result.is_valid)
        self.assertIn("Invoice Number already exists.", result.errors)

    def test_valid_header(self):
        result = self.validator.validate_header({
            "customer_id": 1,
            "invoice_date_bs": "2082-04-01",
            "sale_mode": "Retail",
            "payment_type": "Cash",
            "status": "Posted",
            "amount_paid_now": 0,
            "grand_total": 100,
        })
        self.assertTrue(result.is_valid, result.errors)
        self.assertEqual(result.errors, [])
class SaleInvoiceValidatorLineTests(unittest.TestCase):
    def setUp(self):
        self.validator = SaleInvoiceValidator(number_exists_fn=_number_always_false)

    def test_rejects_empty_lines(self):
        result = self.validator.validate_lines([])
        self.assertFalse(result.is_valid)
        self.assertIn("At least one line item is required.", result.errors)

    def test_line_requires_item(self):
        result = self.validator.validate_lines([
            {"item_id": None, "qty": 1, "rate": 10},
        ])
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Item is mandatory" in e for e in result.errors))

    def test_line_rejects_negative_rate(self):
        result = self.validator.validate_lines([
            {"item_id": 1, "qty": 1, "rate": -5},
        ])
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Rate cannot be negative" in e for e in result.errors))

    def test_line_rejects_invalid_discount(self):
        result = self.validator.validate_lines([
            {"item_id": 1, "qty": 1, "rate": 10, "discount_percent": 150},
        ])
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Discount percent" in e for e in result.errors))

    def test_line_rejects_zero_qty_and_free(self):
        result = self.validator.validate_lines([
            {"item_id": 1, "qty": 0, "free_qty": 0, "rate": 10},
        ])
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Either quantity or free quantity" in e for e in result.errors))

    def test_net_rate_mode_rejects_free_qty(self):
        result = self.validator.validate_lines([
            {"item_id": 1, "entry_mode": "net_rate", "qty": 5, "free_qty": 1, "rate": 10},
        ])
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Free Qty must be 0 in Net Rate mode" in e for e in result.errors))

    def test_valid_free_qty_line(self):
        result = self.validator.validate_lines([
            {"item_id": 1, "entry_mode": "free_qty", "qty": 2, "free_qty": 0, "rate": 50, "discount_percent": 10},
        ])
        self.assertTrue(result.is_valid, result.errors)

    def test_valid_net_rate_line(self):
        result = self.validator.validate_lines([
            {"item_id": 1, "entry_mode": "net_rate", "qty": 5, "free_qty": 0, "rate": 8.33},
        ])
        self.assertTrue(result.is_valid, result.errors)


class ItemFreeSchemeValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = ItemFreeSchemeValidator(scheme_exists_fn=_scheme_always_false)

    def test_requires_item(self):
        result = self.validator.validate({"scheme_qty": 5, "scheme_free": 1})
        self.assertFalse(result.is_valid)
        self.assertIn("Item is mandatory.", result.errors)

    def test_requires_positive_scheme_qty(self):
        result = self.validator.validate({"item_id": 1, "scheme_qty": 0, "scheme_free": 1})
        self.assertFalse(result.is_valid)
        self.assertIn("Scheme qty (Buy Qty) must be greater than zero.", result.errors)

    def test_requires_positive_scheme_free(self):
        result = self.validator.validate({"item_id": 1, "scheme_qty": 5, "scheme_free": 0})
        self.assertFalse(result.is_valid)
        self.assertIn("Scheme free (Free Qty) must be greater than zero.", result.errors)

    def test_rejects_duplicate_item(self):
        validator = ItemFreeSchemeValidator(scheme_exists_fn=_scheme_always_true)
        result = validator.validate({"item_id": 1, "scheme_qty": 5, "scheme_free": 1})
        self.assertFalse(result.is_valid)
        self.assertIn("An active free scheme already exists for this item.", result.errors)

    def test_valid_scheme(self):
        result = self.validator.validate({"item_id": 1, "scheme_qty": 5, "scheme_free": 1})
        self.assertTrue(result.is_valid, result.errors)
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
