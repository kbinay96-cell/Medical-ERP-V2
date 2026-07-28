import unittest
from datetime import date

from engines.date_engine import (
    validate_bs_date, get_financial_year, get_financial_year_from_bs_date,
    date_diff_days, calculate_age, get_month_name, format_for_report,
    DateEngineError,
)


class TestDateEngine(unittest.TestCase):

    def test_validate_accepts_any_common_separator(self):
        for text in ("2083/4/5", "2083-4-5", "2083.4.5", "2083-04-05"):
            is_valid, normalized = validate_bs_date(text)
            self.assertTrue(is_valid, f"Failed for {text}")
            self.assertEqual(normalized, "2083-04-05")

    def test_validate_rejects_empty(self):
        is_valid, _ = validate_bs_date("")
        self.assertFalse(is_valid)

    def test_validate_rejects_bad_month(self):
        is_valid, _ = validate_bs_date("2083-13-05")
        self.assertFalse(is_valid)

    def test_financial_year_before_shrawan(self):
        self.assertEqual(get_financial_year(2083, 2), "2082/2083")

    def test_financial_year_from_shrawan_onward(self):
        self.assertEqual(get_financial_year(2083, 4), "2083/2084")

    def test_financial_year_from_bs_date_string(self):
        self.assertEqual(get_financial_year_from_bs_date("2083-04-05"), "2083/2084")

    def test_date_diff_days(self):
        self.assertEqual(date_diff_days(date(2026, 1, 1), date(2026, 3, 1)), 59)

    def test_calculate_age_before_birthday(self):
        self.assertEqual(calculate_age(date(2000, 7, 26), date(2026, 7, 25)), 25)

    def test_calculate_age_on_birthday(self):
        self.assertEqual(calculate_age(date(2000, 7, 26), date(2026, 7, 26)), 26)

    def test_get_month_name_valid(self):
        self.assertEqual(get_month_name(4), "Shrawan")

    def test_get_month_name_invalid_raises(self):
        with self.assertRaises(DateEngineError):
            get_month_name(13)

    def test_format_for_report(self):
        self.assertEqual(format_for_report("2083-04-05"), "5 Shrawan 2083")


if __name__ == "__main__":
    unittest.main()
