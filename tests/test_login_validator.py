import unittest

from utils.login_validator import validate_login_input


class TestLoginValidator(unittest.TestCase):

    def test_rejects_empty_username(self):
        is_valid, msg = validate_login_input("", "x", "C1", "FY1")
        self.assertFalse(is_valid)
        self.assertIn("Username", msg)

    def test_rejects_leading_trailing_spaces(self):
        is_valid, _ = validate_login_input(" bob", "x", "C1", "FY1")
        self.assertFalse(is_valid)

    def test_rejects_empty_password(self):
        is_valid, msg = validate_login_input("bob", "", "C1", "FY1")
        self.assertFalse(is_valid)
        self.assertIn("Password", msg)

    def test_rejects_missing_company(self):
        is_valid, msg = validate_login_input("bob", "x", "", "FY1")
        self.assertFalse(is_valid)
        self.assertIn("Company", msg)

    def test_rejects_missing_financial_year(self):
        is_valid, msg = validate_login_input("bob", "x", "C1", "")
        self.assertFalse(is_valid)
        self.assertIn("Financial Year", msg)

    def test_accepts_valid_input(self):
        is_valid, msg = validate_login_input("bob", "x", "C1", "FY1")
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    def test_rejects_username_over_max_length(self):
        is_valid, msg = validate_login_input("a" * 51, "x", "C1", "FY1")
        self.assertFalse(is_valid)
        self.assertIn("50", msg)


if __name__ == "__main__":
    unittest.main()
