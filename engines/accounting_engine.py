"""
engines/accounting_engine.py

Accounting Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - reads auto_accounting_rule rows and builds journal_entry_line
      rows from them, substituting real transaction amounts
    - validates balance + control-account rules + period lock BEFORE
      any insert
    - generates Journal Numbers (JV-0001)
    - resolves financial_year_id/accounting_period_id from a date
    - auto-creates bank_reconciliation rows whenever a line posts
      against a Bank-series (1200) account
    - posts one journal per transaction type: Sale Invoice, Purchase
      Invoice, Sale Return, Purchase Return, Receipt, Payment
    - posts Opening Balances as a single balanced journal
    - reverses a journal (new opposite journal, never edits the old one)
    - runs Year End Closing (Period Lock -> Retained Earnings transfer
      -> new FY Opening)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.journal_validator import JournalValidator
from models.auto_accounting_rule_model import AutoAccountingRuleModel
from models.chart_of_accounts_model import ChartOfAccountsModel
from models.financial_year_model import FinancialYearModel
from models.journal_model import JournalModel, JournalSearchFilters
from models.opening_balance_model import OpeningBalanceModel

logger = logging.getLogger(__name__)

DEFAULT_JOURNAL_PREFIX = "JV-"
DEFAULT_JOURNAL_PADDING = 4  # JV-0001
BANK_ACCOUNT_CODE_PREFIX = "12"  # 1200-series accounts are Bank accounts


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning("engines.date_engine not importable; AccountingEngine falls back to AD-only stamps.")
        return None


@dataclass
class JournalLineDTO:
    journal_entry_line_id: int
    account_id: int
    account_code: Optional[str]
    account_name: Optional[str]
    debit_amount: float
    credit_amount: float
    sub_ledger_type: Optional[str]
    sub_ledger_id: Optional[int]
    line_narration: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "JournalLineDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})


@dataclass
class JournalDTO:
    journal_entry_id: int
    journal_number: str
    journal_date_ad: Any
    journal_date_bs: str
    source_document_type: str
    source_document_id: Optional[int]
    narration: str
    status: str
    reversal_of_journal_entry_id: Optional[int]
    cancellation_reason: Optional[str]
    created_by: int
    created_at_ad: Any
    created_at_bs: Optional[str]
    lines: list[JournalLineDTO] = None

    @classmethod
    def from_row(cls, row: dict, lines: Optional[list[JournalLineDTO]] = None) -> "JournalDTO":
        known_fields = {f for f in cls.__dataclass_fields__.keys() if f != "lines"}
        known = {k: row.get(k) for k in known_fields}
        return cls(**known, lines=lines or [])

    def to_dict(self) -> dict:
        return asdict(self)


class AccountingEngine:
    """Business-rule orchestration for the Accounts module."""

    def __init__(
        self,
        journal_model: Optional[JournalModel] = None,
        coa_model: Optional[ChartOfAccountsModel] = None,
        rule_model: Optional[AutoAccountingRuleModel] = None,
        period_model=None,          # models.accounting_period_model.AccountingPeriodModel -- REQUIRED, injected
        bank_recon_model=None,      # models.bank_reconciliation_model.BankReconciliationModel -- REQUIRED, injected
        financial_year_model: Optional[FinancialYearModel] = None,
        opening_balance_model: Optional[OpeningBalanceModel] = None,
        role_permission_model=None,
        role_lookup_fn: Optional[Callable[[int], Optional[str]]] = None,
        date_engine: Optional[Any] = None,
        validator: Optional[JournalValidator] = None,
    ) -> None:
        if period_model is None:
            raise ValueError("AccountingEngine requires a period_model instance.")
        if bank_recon_model is None:
            raise ValueError("AccountingEngine requires a bank_recon_model instance.")

        self._journal_model = journal_model or JournalModel()
        self._coa_model = coa_model or ChartOfAccountsModel()
        self._rule_model = rule_model or AutoAccountingRuleModel()
        self._period_model = period_model
        self._bank_recon_model = bank_recon_model
        self._financial_year_model = financial_year_model or FinancialYearModel()
        self._opening_balance_model = opening_balance_model or OpeningBalanceModel()
        self._role_permission_model = role_permission_model
        self._role_lookup_fn = role_lookup_fn
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = validator or JournalValidator(period_lookup_fn=self._period_model.get_period_for_date)

    def _require_permission(self, user_id: int, permission: str) -> None:
        if self._role_permission_model is None or self._role_lookup_fn is None:
            return
        role_name = self._role_lookup_fn(user_id)
        if not role_name:
            raise ValidationError(f"Could not resolve an accounting role for user {user_id}.")
        permissions = self._role_permission_model.get_permissions_for_role(role_name)
        if not permissions.get(permission, False):
            raise ValidationError(f"Role '{role_name}' does not have the '{permission}' accounting permission.")

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #
    def _stamp_bs_date(self, ad_value: date) -> str:
        if self._date_engine is None:
            return ad_value.isoformat()
        try:
            return self._date_engine.ad_to_bs(ad_value)
        except Exception:
            logger.warning("BS conversion failed for %s; falling back to AD string.", ad_value)
            return ad_value.isoformat()

    def _generate_journal_number(self) -> str:
        latest = self._journal_model.search(JournalSearchFilters(page_size=1, include_deleted=True))
        next_seq = 1
        if latest:
            try:
                next_seq = int(latest[0]["journal_number"].replace(DEFAULT_JOURNAL_PREFIX, "")) + 1
            except ValueError:
                next_seq = 1
        return f"{DEFAULT_JOURNAL_PREFIX}{next_seq:0{DEFAULT_JOURNAL_PADDING}d}"

    def _build_lines_from_rule(
        self,
        transaction_type: str,
        role_amounts: dict[str, float],
        sub_ledger_type: Optional[str],
        sub_ledger_id: Optional[int],
        account_overrides: Optional[dict[str, int]] = None,
    ) -> list[dict]:
        """
        Reads auto_accounting_rule rows for `transaction_type`, and for
        each rule whose `line_role` has a non-zero entry in
        `role_amounts`, builds one journal_entry_line dict. This is the
        ONE place that turns "data-driven rule" + "real transaction
        amounts" into actual postable lines -- every post_*_journal()
        method below calls this instead of hardcoding Dr/Cr itself.
        """
        rules = self._rule_model.get_active_rules_for_type(transaction_type)
        lines = []
        for order, rule in enumerate(rules, start=1):
            amount = role_amounts.get(rule["line_role"])
            if not amount or amount == 0:
                continue
            is_sub_ledger = rule["is_sub_ledger_line"]
            lines.append({
                "account_id": (account_overrides or {}).get(rule["line_role"], rule["account_id"]),
                "debit_amount": amount if rule["side"] == "Debit" else 0,
                "credit_amount": amount if rule["side"] == "Credit" else 0,
                "sub_ledger_type": sub_ledger_type if is_sub_ledger else None,
                "sub_ledger_id": sub_ledger_id if is_sub_ledger else None,
                "branch_id": None,
                "department_id": None,
                "cost_center_id": None,
                "line_narration": rule["line_role"],
                "line_order": order,
            })
        return lines

    def _cash_bank_account_override(self, payment_mode: Optional[str]) -> dict[str, int]:
        if (payment_mode or "").strip().casefold() == "cash":
            return {}
        bank_account = self._coa_model.get_by_code("1210")
        if bank_account is None or not bank_account["is_active"]:
            raise ValidationError("Configure an active bank ledger account 1210 before posting bank transactions.")
        return {"Cash/Bank": bank_account["account_id"]}

    def _post_journal(
        self,
        journal_date_ad: date,
        source_document_type: str,
        source_document_id: Optional[int],
        narration: str,
        line_rows: list[dict],
        created_by: int,
        reversal_of_journal_entry_id: Optional[int] = None,
    ) -> JournalDTO:
        """
        The SINGLE choke point every posting path funnels through --
        validates balance/control-account rules and the period lock,
        resolves financial_year_id/accounting_period_id, generates the
        journal_number, persists, then auto-creates bank_reconciliation
        rows for any line against a Bank-series account. No caller ever
        inserts a journal any other way.
        """
        period_result = self._validator.validate_period(journal_date_ad)
        if not period_result.is_valid:
            raise ValidationError("; ".join(period_result.errors))

        account_ids = {row["account_id"] for row in line_rows}
        account_lookup = {aid: self._coa_model.get_by_id(aid) for aid in account_ids}
        lines_result = self._validator.validate_lines(line_rows, account_lookup)
        if not lines_result.is_valid:
            raise ValidationError("; ".join(lines_result.errors))

        period = self._period_model.get_period_for_date(journal_date_ad)
        now_ad = datetime.now(timezone.utc)
        header_data = {
            "journal_number": self._generate_journal_number(),
            "journal_date_ad": journal_date_ad,
            "journal_date_bs": self._stamp_bs_date(journal_date_ad),
            "financial_year_id": period["financial_year_id"],
            "accounting_period_id": period["accounting_period_id"],
            "source_document_type": source_document_type,
            "source_document_id": source_document_id,
            "narration": narration,
            "status": "Posted",
            "reversal_of_journal_entry_id": reversal_of_journal_entry_id,
            "created_by": created_by,
            "created_at_ad": now_ad,
            "created_at_bs": self._stamp_bs_date(now_ad.date()),
        }

        journal_entry_id = self._journal_model.insert_with_lines(header_data, line_rows)

        # Auto-create bank_reconciliation rows for Bank-series lines
        inserted_lines = self._journal_model.get_lines_by_journal_id(journal_entry_id)
        for line in inserted_lines:
            if line["account_code"].startswith(BANK_ACCOUNT_CODE_PREFIX):
                self._bank_recon_model.insert(
                    journal_entry_line_id=line["journal_entry_line_id"],
                    account_id=line["account_id"],
                )

        return self.get_by_id(journal_entry_id)

    # ------------------------------------------------------------------ #
    # POST -- one method per transaction type, each just computes
    # role_amounts + sub_ledger key, everything else is shared via
    # _build_lines_from_rule() + _post_journal()
    # ------------------------------------------------------------------ #
    def post_sale_invoice_journal(self, sale_invoice: dict, created_by: int) -> JournalDTO:
        tax_amount = float(sale_invoice.get("tax_amount") or 0)
        invoice_total = float(sale_invoice["grand_total"])
        role_amounts = {
            "Customer Receivable": invoice_total,
            "Sales": invoice_total - tax_amount,
            "Output VAT": tax_amount,
        }
        lines = self._build_lines_from_rule(
            "Sale Invoice", role_amounts, sub_ledger_type="Customer", sub_ledger_id=sale_invoice["customer_id"]
        )
        return self._post_journal(
            journal_date_ad=sale_invoice["invoice_date_ad"],
            source_document_type="Sale Invoice",
            source_document_id=sale_invoice["sale_invoice_id"],
            narration=f"Sale Invoice {sale_invoice['invoice_number']}",
            line_rows=lines,
            created_by=created_by,
        )

    def post_purchase_invoice_journal(self, purchase_invoice: dict, created_by: int) -> JournalDTO:
        tax_amount = float(purchase_invoice.get("tax_amount") or 0)
        invoice_total = float(purchase_invoice["grand_total"])
        role_amounts = {
            "Supplier Payable": invoice_total,
            "Purchase": invoice_total - tax_amount,
            "Input VAT": tax_amount,
        }
        lines = self._build_lines_from_rule(
            "Purchase Invoice", role_amounts, sub_ledger_type="Supplier", sub_ledger_id=purchase_invoice["supplier_id"]
        )
        return self._post_journal(
            journal_date_ad=purchase_invoice["invoice_date_ad"],
            source_document_type="Purchase Invoice",
            source_document_id=purchase_invoice["purchase_invoice_id"],
            narration=f"Purchase Invoice {purchase_invoice['internal_ref_number']}",
            line_rows=lines,
            created_by=created_by,
        )

    def post_sale_return_journal(self, sale_return: dict, created_by: int) -> JournalDTO:
        tax_amount = float(sale_return.get("total_tax_amount") or 0)
        return_total = float(sale_return["grand_total"])
        role_amounts = {
            "Sales Return": return_total - tax_amount,
            "Output VAT Reversal": tax_amount,
            "Customer Receivable Reversal": return_total,
        }
        lines = self._build_lines_from_rule(
            "Sale Return", role_amounts, sub_ledger_type="Customer", sub_ledger_id=sale_return["customer_id"]
        )
        return self._post_journal(
            journal_date_ad=sale_return["return_date_ad"],
            source_document_type="Sale Return",
            source_document_id=sale_return["sale_return_id"],
            narration=f"Sale Return {sale_return['return_number']}",
            line_rows=lines,
            created_by=created_by,
        )

    def post_purchase_return_journal(self, purchase_return: dict, created_by: int) -> JournalDTO:
        tax_amount = float(purchase_return.get("total_cc_amount") or 0)
        return_total = float(purchase_return["grand_total"])
        role_amounts = {
            "Purchase Return": return_total - tax_amount,
            "Input VAT Reversal": tax_amount,
            "Supplier Payable Reversal": return_total,
        }
        lines = self._build_lines_from_rule(
            "Purchase Return", role_amounts, sub_ledger_type="Supplier", sub_ledger_id=purchase_return["supplier_id"]
        )
        return self._post_journal(
            journal_date_ad=purchase_return["return_date_ad"],
            source_document_type="Purchase Return",
            source_document_id=purchase_return["purchase_return_id"],
            narration=f"Purchase Return {purchase_return['return_number']}",
            line_rows=lines,
            created_by=created_by,
        )

    def post_receipt_journal(self, receipt: dict, created_by: int) -> JournalDTO:
        """
        Cash/Bank Dr, Customer Receivable Cr -- for the ALLOCATED portion
        only. The advance portion (receipt['advance_amount']) posts to
        Customer Advance (2300) instead of Customer Receivable, since it
        isn't yet tied to a specific invoice.
        """
        role_amounts = {
            "Cash/Bank": float(receipt["amount"]),
            "Customer Receivable": float(receipt["allocated_amount"]),
            "Customer Advance": float(receipt["advance_amount"]),
        }
        lines = self._build_lines_from_rule(
            "Receipt", role_amounts, sub_ledger_type="Customer", sub_ledger_id=receipt["customer_id"],
            account_overrides=self._cash_bank_account_override(receipt.get("payment_mode")),
        )
        return self._post_journal(
            journal_date_ad=receipt["receipt_date_ad"],
            source_document_type="Receipt",
            source_document_id=receipt["receipt_id"],
            narration=f"Receipt {receipt['receipt_number']}",
            line_rows=lines,
            created_by=created_by,
        )

    def post_payment_journal(self, payment: dict, created_by: int) -> JournalDTO:
        role_amounts = {
            "Cash/Bank": float(payment["amount"]),
            "Supplier Payable": (
                float(payment["allocated_amount"])
                + float(payment.get("opening_balance_allocated_amount") or 0)
            ),
            "Supplier Advance": float(payment["advance_amount"]),
        }
        lines = self._build_lines_from_rule(
            "Payment", role_amounts, sub_ledger_type="Supplier", sub_ledger_id=payment["supplier_id"],
            account_overrides=self._cash_bank_account_override(payment.get("payment_mode")),
        )
        return self._post_journal(
            journal_date_ad=payment["payment_date_ad"],
            source_document_type="Payment",
            source_document_id=payment["payment_id"],
            narration=f"Payment {payment['payment_number']}",
            line_rows=lines,
            created_by=created_by,
        )

    # ------------------------------------------------------------------ #
    # OPENING BALANCE
    # ------------------------------------------------------------------ #
    def post_opening_balances(self, financial_year_id: int, opening_rows: list[dict], created_by: int,
                               journal_date_ad: date) -> JournalDTO:
        """
        `opening_rows` -- each: {"account_id", "sub_ledger_type",
        "sub_ledger_id", "debit_amount", "credit_amount"} -- ALL of a
        financial year's opening balances posted as ONE balanced journal
        (Debit=Credit across the whole set, same as any other journal).
        """
        existing = self.get_journals_for_document("Opening Balance", financial_year_id)
        if existing:
            raise ValidationError("Opening balances have already been posted for this financial year.")
        if not opening_rows:
            raise ValidationError("At least one opening balance is required.")
        lines = [
            {
                "account_id": row["account_id"],
                "debit_amount": row.get("debit_amount") or 0,
                "credit_amount": row.get("credit_amount") or 0,
                "sub_ledger_type": row.get("sub_ledger_type"),
                "sub_ledger_id": row.get("sub_ledger_id"),
                "branch_id": None, "department_id": None, "cost_center_id": None,
                "line_narration": "Opening Balance",
                "line_order": index,
            }
            for index, row in enumerate(opening_rows, start=1)
        ]
        journal = self._post_journal(
            journal_date_ad=journal_date_ad,
            source_document_type="Opening Balance",
            source_document_id=financial_year_id,
            narration=f"Opening Balances for Financial Year {financial_year_id}",
            line_rows=lines,
            created_by=created_by,
        )
        now_ad = datetime.now(timezone.utc)
        now_bs = self._stamp_bs_date(now_ad.date())
        self._opening_balance_model.insert_batch([
            {
                **row,
                "financial_year_id": financial_year_id,
                "posted_journal_entry_id": journal.journal_entry_id,
                "created_by": created_by,
                "created_at_bs": now_bs,
            }
            for row in opening_rows
        ])
        return journal

    def post_manual_journal(self, journal_date_ad: date, narration: str,
                            line_rows: list[dict], created_by: int) -> JournalDTO:
        """Post a user-entered journal through the same validation choke point."""
        self._require_permission(created_by, "Create")
        self._require_permission(created_by, "Post")
        if not (narration or "").strip():
            raise ValidationError("Journal narration is required.")
        return self._post_journal(
            journal_date_ad=journal_date_ad,
            source_document_type="Manual",
            source_document_id=None,
            narration=narration.strip(),
            line_rows=line_rows,
            created_by=created_by,
        )

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, journal_entry_id: int) -> Optional[JournalDTO]:
        row = self._journal_model.get_by_id(journal_entry_id)
        if row is None:
            return None
        line_rows = self._journal_model.get_lines_by_journal_id(journal_entry_id)
        lines = [JournalLineDTO.from_row(r) for r in line_rows]
        return JournalDTO.from_row(row, lines=lines)

    def search(self, filters: JournalSearchFilters) -> list[JournalDTO]:
        rows = self._journal_model.search(filters)
        return [JournalDTO.from_row(row) for row in rows]

    def get_journals_for_document(self, source_document_type: str, source_document_id: int) -> list[JournalDTO]:
        """The 'Document -> Journal' lookup every source Screen's "View
        Journal" button calls."""
        rows = self._journal_model.get_journals_for_document(source_document_type, source_document_id)
        return [JournalDTO.from_row(row) for row in rows]

    def get_account_ledger(self, account_id: int, **kwargs) -> list[dict]:
        return self._journal_model.get_account_ledger(account_id, **kwargs)

    # ------------------------------------------------------------------ #
    # REVERSE -- new opposite journal, original marked Reversed, never edited
    # ------------------------------------------------------------------ #
    def reverse_journal(self, journal_entry_id: int, reason: str, reversed_by: int) -> JournalDTO:
        self._require_permission(reversed_by, "Reverse")
        original = self._journal_model.get_by_id(journal_entry_id)
        if original is None:
            raise RecordNotFoundError(f"Journal {journal_entry_id} not found.")
        if original["status"] != "Posted":
            raise ValidationError("Only a Posted journal can be reversed.")

        reason_result = self._validator.validate_reason(reason, action_label="Reversal")
        if not reason_result.is_valid:
            raise ValidationError("; ".join(reason_result.errors))

        original_lines = self._journal_model.get_lines_by_journal_id(journal_entry_id)
        flipped_lines = [
            {
                "account_id": line["account_id"],
                "debit_amount": line["credit_amount"],   # flipped
                "credit_amount": line["debit_amount"],    # flipped
                "sub_ledger_type": line["sub_ledger_type"],
                "sub_ledger_id": line["sub_ledger_id"],
                "branch_id": line["branch_id"],
                "department_id": line["department_id"],
                "cost_center_id": line["cost_center_id"],
                "line_narration": f"Reversal of {original['journal_number']}",
                "line_order": index,
            }
            for index, line in enumerate(original_lines, start=1)
        ]

        now_ad = datetime.now(timezone.utc)
        reversal = self._post_journal(
            journal_date_ad=now_ad.date(),
            source_document_type=original["source_document_type"],
            source_document_id=original["source_document_id"],
            narration=f"Reversal of {original['journal_number']}: {reason}",
            line_rows=flipped_lines,
            created_by=reversed_by,
            reversal_of_journal_entry_id=journal_entry_id,
        )

        self._journal_model.update_status(
            journal_entry_id=journal_entry_id, status="Reversed", cancellation_reason=None,
            updated_by=reversed_by, updated_at_ad=now_ad, updated_at_bs=self._stamp_bs_date(now_ad.date()),
        )
        return reversal

    # ------------------------------------------------------------------ #
    # CANCEL -- status-only, for a same-day mistake (never economically reversed)
    # ------------------------------------------------------------------ #
    def cancel_journal(self, journal_entry_id: int, reason: str, cancelled_by: int) -> JournalDTO:
        self._require_permission(cancelled_by, "Cancel")
        existing = self._journal_model.get_by_id(journal_entry_id)
        if existing is None:
            raise RecordNotFoundError(f"Journal {journal_entry_id} not found.")
        if existing["source_document_type"] != "Manual":
            raise ValidationError("Auto-posted journals cannot be cancelled directly; correct the source transaction.")
        if existing["status"] not in ("Draft", "Posted"):
            raise ValidationError("Only a Draft or Posted journal can be Cancelled.")

        reason_result = self._validator.validate_reason(reason, action_label="Cancellation")
        if not reason_result.is_valid:
            raise ValidationError("; ".join(reason_result.errors))

        now_ad = datetime.now(timezone.utc)
        self._journal_model.update_status(
            journal_entry_id=journal_entry_id, status="Cancelled", cancellation_reason=reason,
            updated_by=cancelled_by, updated_at_ad=now_ad, updated_at_bs=self._stamp_bs_date(now_ad.date()),
        )
        return self.get_by_id(journal_entry_id)

    def lock_period(self, accounting_period_id: int, locked_by: int) -> None:
        self._require_permission(locked_by, "Post")
        self._period_model.lock_period(accounting_period_id, locked_by)

    def reopen_period(self, accounting_period_id: int, reason: str, reopened_by: int) -> None:
        self._require_permission(reopened_by, "Period Unlock")
        result = self._validator.validate_reason(reason, action_label="Period Reopen")
        if not result.is_valid:
            raise ValidationError(result.errors)
        self._period_model.reopen_period(accounting_period_id, reopened_by, reason)

    # ------------------------------------------------------------------ #
    # YEAR END CLOSING
    # ------------------------------------------------------------------ #
    def run_year_end_closing(self, financial_year_id: int, closed_by: int) -> JournalDTO:
        """
        1. Sums every Revenue/Cost of Goods/Operating Expenses account's
           net movement for the year (via get_account_ledger per
           account, or a dedicated aggregate query in
           FinancialYearModel -- Part 3 wiring detail).
        2. Posts ONE closing journal transferring that net P&L into
           `3400 Current Year Profit/Loss` (and from there into `3300
           Retained Earnings` in the same journal).
        3. Marks the financial_year row status='Closed' and stores
           closing_journal_entry_id.
        4. Locks every accounting_period under that financial year that
           isn't already Locked.
        Actual net-P&L aggregation SQL lives in a FinancialYearModel
        method (Part 3 wiring, since it's a report-shaped query more than
        a simple CRUD one) -- this method's job is the orchestration
        (compute -> build 2-line closing journal -> post -> lock -> mark
        closed), not the aggregation itself.
        """
        self._require_permission(closed_by, "Approve")
        financial_year = self._financial_year_model.get_by_id(financial_year_id)
        if financial_year is None:
            raise RecordNotFoundError(f"Financial year {financial_year_id} not found.")
        if financial_year["status"] != "Open":
            raise ValidationError("Only an open financial year can be closed.")
        if self.get_journals_for_document("Year End Closing", financial_year_id):
            raise ValidationError("Year-end closing has already been posted for this financial year.")

        net_profit = round(self._financial_year_model.get_net_profit_for_year(financial_year_id), 2)
        accounts_by_code = {
            row["account_code"]: row
            for row in self._coa_model.get_hierarchy()
        }
        current_year_result = accounts_by_code.get("3400")
        retained_earnings = accounts_by_code.get("3300")
        if current_year_result is None or retained_earnings is None:
            raise ValidationError("Chart of Accounts must contain accounts 3300 and 3400.")

        pnl_accounts = [
            row for row in accounts_by_code.values()
            if row["account_group"] in ("Revenue", "Cost of Goods", "Operating Expenses")
            and row["parent_account_id"] is not None
        ]
        lines: list[dict[str, Any]] = []
        debit_total = 0.0
        credit_total = 0.0
        for account in pnl_accounts:
            account_lines = self._journal_model.get_account_ledger(
                account["account_id"],
                date_from_ad=financial_year["start_date_ad"],
                date_to_ad=financial_year["end_date_ad"],
            )
            debit = round(sum(float(row["debit_amount"] or 0) for row in account_lines), 2)
            credit = round(sum(float(row["credit_amount"] or 0) for row in account_lines), 2)
            balance = round(credit - debit if account["normal_balance"] == "Credit" else debit - credit, 2)
            if balance == 0:
                continue
            if account["normal_balance"] == "Credit":
                debit_amount, credit_amount = max(balance, 0), max(-balance, 0)
            else:
                debit_amount, credit_amount = max(-balance, 0), max(balance, 0)
            lines.append({
                "account_id": account["account_id"],
                "debit_amount": debit_amount,
                "credit_amount": credit_amount,
                "sub_ledger_type": None,
                "sub_ledger_id": None,
                "branch_id": None,
                "department_id": None,
                "cost_center_id": None,
                "line_narration": "Year-end P&L close",
                "line_order": len(lines) + 1,
            })
            debit_total += debit_amount
            credit_total += credit_amount

        transfer = abs(net_profit)
        if transfer > 0:
            # Close the income/expense balances to Current Year P&L, then
            # transfer the resulting balance to Retained Earnings.
            lines.extend([
                {
                    "account_id": current_year_result["account_id"],
                    "debit_amount": transfer if net_profit > 0 else 0,
                    "credit_amount": transfer if net_profit < 0 else 0,
                    "sub_ledger_type": None, "sub_ledger_id": None,
                    "branch_id": None, "department_id": None, "cost_center_id": None,
                    "line_narration": "Current year result",
                    "line_order": len(lines) + 1,
                },
                {
                    "account_id": retained_earnings["account_id"],
                    "debit_amount": transfer if net_profit < 0 else 0,
                    "credit_amount": transfer if net_profit > 0 else 0,
                    "sub_ledger_type": None, "sub_ledger_id": None,
                    "branch_id": None, "department_id": None, "cost_center_id": None,
                    "line_narration": "Transfer to retained earnings",
                    "line_order": len(lines) + 2,
                },
            ])
            debit_total += transfer
            credit_total += transfer

        if not lines:
            raise ValidationError("No posted profit-and-loss activity was found for this financial year.")
        if round(debit_total, 2) != round(credit_total, 2):
            raise ValidationError("Year-end P&L balances do not reconcile; financial year was not closed.")

        if not self._period_model.list_periods(financial_year_id):
            raise ValidationError("No accounting periods are defined for this financial year.")
        closing_date = financial_year["end_date_ad"]
        closing_journal = self._post_journal(
            journal_date_ad=closing_date,
            source_document_type="Year End Closing",
            source_document_id=financial_year_id,
            narration=f"Year-end closing for {financial_year['fy_label']}",
            line_rows=lines,
            created_by=closed_by,
        )
        self._financial_year_model.close_year(
            financial_year_id, closing_journal.journal_entry_id, closed_by
        )
        return closing_journal