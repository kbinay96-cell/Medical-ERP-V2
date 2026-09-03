"""
engines/report_validator.py

Report Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model/Engine
execution." Checks a report request is permitted and structurally
complete BEFORE the Engine ever calls ReportQueryExecutor.run().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# The fixed standard filter list -- confirmed scope, section 4/8. Every
# report_definition.applicable_filters entry MUST be one of these.
STANDARD_FILTERS = (
    "financial_year", "date_from", "date_to", "branch_id", "status",
    "customer_id", "supplier_id", "manufacturer_id", "country_id",
    "category_id", "item_id", "batch_id", "account_id", "transaction_type",
    "payment_mode", "tax_type",
)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class ReportValidator:
    """Stateless validation rules for a report/widget run request."""

    def validate_filter_keys(self, applicable_filters: list[str], provided_filter_keys: set[str]) -> ValidationResult:
        """
        Every key the caller provided must be one this report actually
        declares as applicable (prevents silently ignored typos, e.g.
        passing 'customer' instead of 'customer_id'). Provided keys are
        allowed to be a SUBSET of applicable_filters -- an optional
        filter left blank is fine, the Engine fills it with None.
        """
        result = ValidationResult()
        unknown = provided_filter_keys - set(applicable_filters)
        if unknown:
            result.add(f"These filters are not applicable to this report: {sorted(unknown)}.")
        return result

    def validate_date_range(self, date_from, date_to) -> ValidationResult:
        result = ValidationResult()
        if date_from and date_to and date_from > date_to:
            result.add("Date From cannot be after Date To.")
        return result

    def validate_permission(self, required_permission: str, granted_permissions: dict[str, bool],
                             is_financial_statement: bool = False) -> ValidationResult:
        """
        `granted_permissions` is the caller's role's permission dict
        from ReportPermissionModel.get_permissions_for_role(). A
        financial-statement report ALSO requires 'View Financial
        Statements' specifically, on top of its own required_permission
        -- the confirmed extra gate ("Profit/financial reports normal
        user ko automatically nahi dikhenge").
        """
        result = ValidationResult()
        if not granted_permissions.get(required_permission, False):
            result.add(f"You do not have permission '{required_permission}' to view this report.")
        if is_financial_statement and not granted_permissions.get("View Financial Statements", False):
            result.add("This is a financial statement -- 'View Financial Statements' permission is required.")
        return result