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