# Accounts Module — Part 2: Validators + Engine Layer

**Project:** Medical ERP V2
**Layer:** Business Logic (Validators + Engine — "No SQL. Business logic lives ONLY here.")
**Depends on Part 1:** all Accounts tables + `ChartOfAccountsModel`, `JournalModel`
**Reuses (already built, unchanged):** `engines/date_engine.py`, `engines/exceptions.py`

---

## 0. One addition to Part 1: `models/auto_accounting_rule_model.py`

Needed by this Engine but not written out in Part 1 (only the table was defined there). Small and complete:

```python
"""models/auto_accounting_rule_model.py"""
from __future__ import annotations
from typing import Any


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class AutoAccountingRuleModel:
    def get_active_rules_for_type(self, transaction_type: str) -> list[dict[str, Any]]:
        sql = """
            SELECT aar.*, coa.account_code, coa.account_name
            FROM auto_accounting_rule aar
            JOIN chart_of_accounts coa ON coa.account_id = aar.account_id
            WHERE aar.transaction_type = %(transaction_type)s AND aar.is_active = TRUE
            ORDER BY aar.display_order;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"transaction_type": transaction_type})
                return cur.fetchall()
        finally:
            conn.close()
```

---

## 1. `engines/journal_validator.py`

```python
"""
engines/journal_validator.py

Journal Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." The
Debit=Credit balance rule and the control-account sub-ledger
requirement are cross-row/cross-table checks the DB itself can't
express, so they live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REASON = 1000


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class JournalValidator:
    """Stateless validation rules for a Journal Entry (header + lines)."""

    def __init__(self, period_lookup_fn: Callable[[Any], Optional[dict]]) -> None:
        # period_lookup_fn(journal_date_ad) -> the accounting_period row
        # that date falls into, or None if no period is defined for it
        self._period_lookup_fn = period_lookup_fn

    def validate_lines(self, line_rows: list[dict], account_lookup: dict[int, dict]) -> ValidationResult:
        """
        `account_lookup` maps account_id -> its chart_of_accounts row
        (so this never queries the database itself). Checks:
        1. At least one line.
        2. Every account_id exists and is active.
        3. Control accounts (is_control_account=TRUE) MUST carry
           sub_ledger_type + sub_ledger_id.
        4. Non-control accounts must NOT carry a sub_ledger (keeps the
           data clean -- a sub-ledger key on a non-control line is
           meaningless and almost certainly a mistake).
        5. Debit = Credit, summed across all lines.
        """
        result = ValidationResult()

        if not line_rows:
            result.add("A journal must have at least one line.")
            return result

        total_debit = 0.0
        total_credit = 0.0

        for index, row in enumerate(line_rows, start=1):
            prefix = f"Line {index}"
            account = account_lookup.get(row.get("account_id"))
            if account is None:
                result.add(f"{prefix}: Account not found or inactive.")
                continue

            debit = float(row.get("debit_amount") or 0)
            credit = float(row.get("credit_amount") or 0)
            if (debit > 0) == (credit > 0):
                result.add(f"{prefix}: Exactly one of Debit or Credit must be greater than zero.")
                continue

            sub_ledger_type = row.get("sub_ledger_type")
            sub_ledger_id = row.get("sub_ledger_id")
            if account["is_control_account"]:
                if not sub_ledger_type or not sub_ledger_id:
                    result.add(
                        f"{prefix}: Account '{account['account_name']}' is a control account and "
                        f"requires a Customer/Supplier sub-ledger reference."
                    )
            else:
                if sub_ledger_type or sub_ledger_id:
                    result.add(
                        f"{prefix}: Account '{account['account_name']}' is not a control account and "
                        f"must not carry a sub-ledger reference."
                    )

            total_debit += debit
            total_credit += credit

        if round(total_debit, 2) != round(total_credit, 2):
            result.add(
                f"Journal is not balanced: total Debit ({round(total_debit, 2)}) does not equal "
                f"total Credit ({round(total_credit, 2)})."
            )

        return result

    def validate_period(self, journal_date_ad) -> ValidationResult:
        result = ValidationResult()
        period = self._period_lookup_fn(journal_date_ad)
        if period is None:
            result.add(f"No accounting period is defined for date {journal_date_ad}.")
        elif period["status"] == "Locked":
            result.add(
                f"Accounting period '{period['period_label']}' is Locked. "
                f"This journal cannot be posted/edited unless the period is explicitly reopened."
            )
        return result

    def validate_reason(self, reason: str, action_label: str = "Cancellation") -> ValidationResult:
        result = ValidationResult()
        text = (reason or "").strip()
        if not text:
            result.add(f"{action_label} Reason is mandatory.")
        elif len(text) > MAX_LEN_REASON:
            result.add(f"{action_label} Reason must not exceed {MAX_LEN_REASON} characters.")
        return result
```

---

## 2. `engines/accounting_engine.py` — The Core Engine

```python
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
from typing import Any, Optional

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.journal_validator import JournalValidator
from models.auto_accounting_rule_model import AutoAccountingRuleModel
from models.chart_of_accounts_model import ChartOfAccountsModel
from models.journal_model import JournalModel, JournalSearchFilters

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
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = validator or JournalValidator(period_lookup_fn=self._period_model.get_period_for_date)

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

    def _build_lines_from_rule(self, transaction_type: str, role_amounts: dict[str, float],
                                sub_ledger_type: Optional[str], sub_ledger_id: Optional[int]) -> list[dict]:
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
                "account_id": rule["account_id"],
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
        role_amounts = {
            "Customer Receivable": float(sale_invoice["grand_total"]),
            "Sales": float(sale_invoice["subtotal_amount"]),
            "Output VAT": float(sale_invoice.get("tax_amount") or 0),
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
        role_amounts = {
            "Supplier Payable": float(purchase_invoice["grand_total"]),
            "Purchase": float(purchase_invoice["subtotal_amount"]),
            "Input VAT": float(purchase_invoice.get("tax_amount") or 0),
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
        role_amounts = {
            "Sales Return": float(sale_return["total_gross_amount"] - sale_return["total_discount_amount"]),
            "Output VAT Reversal": float(sale_return.get("total_tax_amount") or 0),
            "Customer Receivable Reversal": float(sale_return["grand_total"]),
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
        role_amounts = {
            "Purchase Return": float(purchase_return["total_gross_amount"] - purchase_return["total_discount_amount"]),
            "Input VAT Reversal": float(purchase_return.get("total_cc_amount") or 0),
            "Supplier Payable Reversal": float(purchase_return["grand_total"]),
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
            "Receipt", role_amounts, sub_ledger_type="Customer", sub_ledger_id=receipt["customer_id"]
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
            "Supplier Payable": float(payment["allocated_amount"]),
            "Supplier Advance": float(payment["advance_amount"]),
        }
        lines = self._build_lines_from_rule(
            "Payment", role_amounts, sub_ledger_type="Supplier", sub_ledger_id=payment["supplier_id"]
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
        return self._post_journal(
            journal_date_ad=journal_date_ad,
            source_document_type="Opening Balance",
            source_document_id=financial_year_id,
            narration=f"Opening Balances for Financial Year {financial_year_id}",
            line_rows=lines,
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
        existing = self._journal_model.get_by_id(journal_entry_id)
        if existing is None:
            raise RecordNotFoundError(f"Journal {journal_entry_id} not found.")
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
        raise NotImplementedError(
            "Orchestration shape defined; wires to FinancialYearModel.get_net_profit_for_year() "
            "in Part 3 once that aggregate query is finalized against the Reports module's own "
            "P&L calculation, so the two never disagree."
        )
```

---

## 3. Wiring Notes (for Part 3)

```
Construction order:

1. ChartOfAccountsModel, JournalModel, AutoAccountingRuleModel,
   AccountingPeriodModel, BankReconciliationModel -- all built first
2. AccountingEngine -- built with the period + bank-recon models
   injected:

       accounting_engine = AccountingEngine(
           period_model=AccountingPeriodModel(),
           bank_recon_model=BankReconciliationModel(),
       )

THREE outstanding integration points -- one per money-moving module
already built, each an additive, optional-dependency hook (identical
pattern to Receipt's sale_engine.py hook and Payment's
purchase_engine.py hook):

    SaleEngine.create_sale_invoice()       -> accounting_engine.post_sale_invoice_journal(...)
    PurchaseEngine.create_purchase_invoice() -> accounting_engine.post_purchase_invoice_journal(...)
    SaleReturnEngine.create_return()        -> accounting_engine.post_sale_return_journal(...)
    PurchaseReturnEngine.create_return()     -> accounting_engine.post_purchase_return_journal(...)
    ReceiptEngine.create_receipt()            -> accounting_engine.post_receipt_journal(...)
    PaymentEngine.create_payment()             -> accounting_engine.post_payment_journal(...)

Each existing Engine gets ONE new optional constructor parameter
(`accounting_engine=None`) and ONE new call at the end of its create
method -- if accounting_engine is None, the call is skipped, so every
prior module keeps working standalone exactly as it does today. This
is now SIX small additive hooks total (two already flagged in Receipt/
Payment Part 3, four new ones flagged here for Part 3 of THIS module).
```

---

## 4. Confirmed-Rule Traceability

| Confirmed Rule | Where enforced |
|---|---|
| Debit = Credit hard rule | `JournalValidator.validate_lines()`, checked BEFORE any insert in `_post_journal()` |
| Control account requires sub-ledger | `JournalValidator.validate_lines()` checks `is_control_account` against `sub_ledger_type`/`sub_ledger_id` |
| Auto-Accounting Rules are data, not code | `_build_lines_from_rule()` reads `AutoAccountingRuleModel`, every `post_*_journal()` method only supplies amounts, never account IDs directly |
| Period Lock rejects journals in a Locked period | `JournalValidator.validate_period()`, checked in `_post_journal()` before insert |
| Cancellation vs Reversal, both require a reason | `cancel_journal()` (status-only) vs `reverse_journal()` (new opposite journal); both call `validate_reason()` |
| Bank Reconciliation rows auto-created | `_post_journal()` checks every inserted line's account code against the `12`-prefix and calls `BankReconciliationModel.insert()` |
| Document ↔ Journal traceability both directions | `get_journals_for_document()` is the reverse lookup every source Screen's "View Journal" button uses |
| Stock ↔ Accounting dual-post | Achieved structurally, not by this Engine directly -- each source Engine (Sale/Purchase/Return) calls its OWN stock-posting method AND (via the Wiring Notes hook) this Engine's journal-posting method, in the same `create_*()` call |

---

**Part 2 complete.** `run_year_end_closing()` is intentionally left as an orchestration stub with `NotImplementedError` — its net-P&L aggregation needs to be finalized jointly with the Reports module's own P&L query (so the two can never disagree), which is the very next blueprint. Waiting for your confirmation before Part 3 (Screens: Chart of Accounts maintenance, Journal Voucher entry/view, Ledger viewer, Period Lock management, Bank Reconciliation screen, wiring checklist including all six cross-module hooks, and the updated Combined Blueprint JSON).
