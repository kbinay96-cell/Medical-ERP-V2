from __future__ import annotations

import unittest
from unittest.mock import Mock

from engines.accounting_engine import AccountingEngine
from engines.exceptions import ValidationError
from engines.journal_validator import JournalValidator


class JournalValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = JournalValidator(
            period_lookup_fn=lambda _: {
                "period_label": "Oct 2026",
                "status": "Open",
                "financial_year_status": "Open",
            }
        )
        self.accounts = {
            1: {
                "account_name": "Cash",
                "is_control_account": False,
                "is_active": True,
            },
            2: {
                "account_name": "Customer Receivables",
                "is_control_account": True,
                "is_active": True,
            },
        }

    def test_accepts_balanced_lines_with_required_control_subledger(self):
        result = self.validator.validate_lines(
            [
                {"account_id": 1, "debit_amount": 100, "credit_amount": 0},
                {
                    "account_id": 2,
                    "debit_amount": 0,
                    "credit_amount": 100,
                    "sub_ledger_type": "Customer",
                    "sub_ledger_id": 12,
                },
            ],
            self.accounts,
        )
        self.assertTrue(result.is_valid, result.errors)

    def test_rejects_negative_amount(self):
        result = self.validator.validate_lines(
            [
                {"account_id": 1, "debit_amount": 100, "credit_amount": -1},
                {"account_id": 2, "debit_amount": 0, "credit_amount": 99},
            ],
            self.accounts,
        )
        self.assertFalse(result.is_valid)
        self.assertTrue(any("non-negative" in error for error in result.errors))

    def test_rejects_control_account_without_subledger(self):
        result = self.validator.validate_lines(
            [
                {"account_id": 1, "debit_amount": 25, "credit_amount": 0},
                {"account_id": 2, "debit_amount": 0, "credit_amount": 25},
            ],
            self.accounts,
        )
        self.assertFalse(result.is_valid)
        self.assertTrue(any("requires a Customer/Supplier" in error for error in result.errors))

    def test_closed_financial_year_blocks_period(self):
        self.validator._period_lookup_fn = lambda _: {
            "period_label": "FY 2025/26",
            "status": "Open",
            "financial_year_status": "Closed",
        }
        result = self.validator.validate_period("2026-10-03")
        self.assertFalse(result.is_valid)


class AccountingEngineTests(unittest.TestCase):
    def make_engine(self, journal_model=None):
        return AccountingEngine(
            journal_model=journal_model or Mock(),
            coa_model=Mock(),
            rule_model=Mock(),
            period_model=Mock(),
            bank_recon_model=Mock(),
            date_engine=Mock(),
            validator=Mock(),
        )

    def test_manual_journal_uses_shared_posting_choke_point(self):
        engine = self.make_engine()
        engine._post_journal = Mock(return_value="posted")
        rows = [{"account_id": 1, "debit_amount": 10, "credit_amount": 0}]
        result = engine.post_manual_journal("2026-10-03", "Opening cash", rows, 4)
        self.assertEqual(result, "posted")
        engine._post_journal.assert_called_once_with(
            journal_date_ad="2026-10-03",
            source_document_type="Manual",
            source_document_id=None,
            narration="Opening cash",
            line_rows=rows,
            created_by=4,
        )

    def test_auto_posted_journal_cannot_be_cancelled(self):
        journal_model = Mock()
        journal_model.get_by_id.return_value = {
            "source_document_type": "Sale Invoice",
            "status": "Posted",
        }
        engine = self.make_engine(journal_model)
        with self.assertRaisesRegex(ValidationError, "Auto-posted journals cannot be cancelled"):
            engine.cancel_journal(5, "Mistake", 4)
        journal_model.update_status.assert_not_called()

    def test_bank_payment_uses_active_bank_ledger(self):
        engine = self.make_engine()
        engine._coa_model.get_by_code.return_value = {
            "account_id": 88,
            "is_active": True,
        }
        self.assertEqual(
            engine._cash_bank_account_override("Bank Transfer"),
            {"Cash/Bank": 88},
        )
        self.assertEqual(engine._cash_bank_account_override("Cash"), {})


if __name__ == "__main__":
    unittest.main()
