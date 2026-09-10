# Accounts Module — Part 3: Screens + Combined Blueprint JSON Update

**Project:** Medical ERP V2
**Layer:** Screens ("No SQL. No business logic." — collect input, call the Engine, render whatever DTO comes back)
**Depends on Part 1+2:** all Accounts tables, `ChartOfAccountsModel`, `JournalModel`, `AutoAccountingRuleModel`, `AccountingEngine`, `JournalValidator`

---

## 1. Screens Layer (`screens/`)

### 1.1 `screens/chart_of_accounts_screen.py`

```python
class ChartOfAccountsScreen(QWidget):
    """Tree view (Group -> Parent -> Ledger) built by walking
    engine.get_hierarchy()'s parent_account_id links client-side. Add/
    Edit a ledger account via a small inline form (account_code,
    account_name, account_group, parent, is_control_account,
    normal_balance). is_control_account is shown but disabled for
    editing on 1300/2100 -- toggling it on an arbitrary account is a
    structural decision, not a routine data edit, so it's add-time-only
    here (changing it later is a Manager/Admin-only action reachable
    from the same screen, gated by accounting_role_permission)."""
    def __init__(self, parent, coa_model: "ChartOfAccountsModel"): ...
    def _build_tree(self, accounts: list[dict]) -> None: ...
    def _on_add_account_clicked(self) -> None: ...
    def _on_edit_account_clicked(self, account_id: int) -> None: ...
```

### 1.2 `screens/journal_voucher_form_screen.py` (Manual journals only)

```python
class JournalVoucherFormScreen(QDialog):
    """The ONLY screen that lets a user type a journal by hand
    (source_document_type='Manual', source_document_id=None) -- every
    other journal in the system is auto-posted by AccountingEngine's
    post_*_journal() methods and is never manually entered.

    Responsibilities:
    - Header: Journal Date (BS), Narration (mandatory).
    - Line grid: Account (searchable combo from
      coa_model.get_hierarchy()), Debit, Credit (one or the other per
      row, never both), Sub-Ledger (Customer/Supplier picker -- shown
      and REQUIRED only when the selected account.is_control_account
      is True), Line Narration.
    - Running "Total Debit" / "Total Credit" footer, updated live as
      rows change -- purely a display convenience; the authoritative
      balance check is still the Engine's when Save is clicked.
    - Save -> engine._post_journal(..., source_document_type='Manual',
      source_document_id=None) (a thin public wrapper,
      post_manual_journal(), is added to AccountingEngine in Part 3's
      wiring -- Part 2 only exposed the six auto-posting methods plus
      the private choke point; a manual entry point is a Screens-layer
      need, so it's added here as the seventh, trivial public method).
    - Surfaces ValidationError messages (imbalance, missing sub-ledger,
      locked period) back to the user.
    """
    def __init__(self, parent, engine: "AccountingEngine", coa_model: "ChartOfAccountsModel"): ...
    def _add_line_row(self) -> None: ...
    def _on_account_selected(self, row_index: int) -> None:
        """Shows/hides and requires the Sub-Ledger picker for that row
        based on the selected account's is_control_account flag."""
        ...
    def _update_totals_footer(self) -> None: ...
    def _collect_lines(self) -> list[dict]: ...
    def _on_save_clicked(self) -> None: ...
```

### 1.3 `screens/journal_list_screen.py`

```python
class JournalListScreen(QWidget):
    """List/search/filter -- Source Document Type, Status, Date range,
    Account (via a join, for "show me every journal touching this
    account"). Actions:
        - View: read-only detail, every line with account code/name,
          Debit/Credit, sub-ledger name (resolved from customer/
          supplier lookup by sub_ledger_id).
        - Reverse: ONLY for status='Posted'. Opens a reason dialog
          (reuses screens/cancellation_reason_dialog.py, relabeled
          generically enough to serve both -- or a near-identical
          sibling if the "Cancellation Reason" title needs to read
          "Reversal Reason" instead; either way, no new dialog LOGIC,
          just a title parameter) -> engine.reverse_journal(...).
        - Cancel: ONLY for status='Draft' or 'Posted' AND
          source_document_type='Manual' -- an auto-posted journal
          (Sale Invoice, Receipt, etc.) is NEVER directly cancellable
          from this screen; correcting it means cancelling/editing the
          SOURCE document (Sale Return, Receipt edit, etc.), which then
          triggers its own reversal journal through the normal flow.
          This restriction is enforced in BOTH the Engine (a caller
          could still misuse cancel_journal() directly) and here in the
          Screen (the button simply doesn't render for non-Manual rows).
    """
    def __init__(self, parent, engine: "AccountingEngine"): ...
    def refresh(self) -> None: ...
    def _on_view_clicked(self, journal_entry_id: int) -> None: ...
    def _on_reverse_clicked(self, journal_entry_id: int) -> None: ...
    def _on_cancel_clicked(self, journal_entry_id: int) -> None: ...
```

### 1.4 `screens/account_ledger_screen.py`

```python
class AccountLedgerScreen(QWidget):
    """Account picker (+ optional Customer/Supplier sub-ledger picker,
    enabled only when the chosen account.is_control_account is True) +
    Date range -> calls engine.get_account_ledger(...) and renders a
    running-balance table (Date | Journal No. | Narration | Debit |
    Credit | Balance), balance computed client-side by walking the
    already-ordered rows and applying each account's normal_balance
    sign convention. This IS the General Ledger / Customer Ledger /
    Supplier Ledger report at the Accounts-module level -- the Reports
    module (next blueprint) will likely wrap this same engine call with
    print/export formatting, not duplicate the query."""
    def __init__(self, parent, engine: "AccountingEngine", coa_model: "ChartOfAccountsModel"): ...
    def _on_account_selected(self, account_id: int) -> None: ...
    def _on_search_clicked(self) -> None: ...
    def _render_running_balance(self, ledger_rows: list[dict], normal_balance: str) -> None: ...
```

### 1.5 `screens/period_lock_screen.py`

```python
class PeriodLockScreen(QWidget):
    """Lists Financial Years -> Accounting Periods (tree/expand), each
    period showing its status. Lock/Reopen buttons per period:
        - Lock: only enabled if the acting user's role has 'Post'/'Manager'-
          level permission per accounting_role_permission.
        - Reopen: only enabled for 'Period Unlock' permission; opens a
          mandatory-reason dialog (reuses the same shared dialog
          pattern) since reopen_reason is a required column."""
    def __init__(self, parent, period_model, role_permission_model): ...
    def refresh(self) -> None: ...
    def _on_lock_clicked(self, accounting_period_id: int) -> None: ...
    def _on_reopen_clicked(self, accounting_period_id: int) -> None: ...
```

### 1.6 `screens/bank_reconciliation_screen.py`

```python
class BankReconciliationScreen(QWidget):
    """Bank account picker (filtered to 1200-series accounts) -> shows
    every Unreconciled row from bank_recon_model.get_unreconciled(),
    each with a "Reconcile" action opening a small inline form
    (Bank Statement Reference, Reconciled Date, computed Difference
    Amount shown live as statement amount entered minus the ledger
    line's own amount) -> bank_recon_model.mark_reconciled(...)."""
    def __init__(self, parent, bank_recon_model, coa_model): ...
    def _on_account_selected(self, account_id: int) -> None: ...
    def _on_reconcile_clicked(self, bank_reconciliation_id: int) -> None: ...
```

### 1.7 `screens/opening_balance_screen.py`

```python
class OpeningBalanceScreen(QDialog):
    """Financial Year picker + a grid: Account (or Customer/Supplier for
    control accounts) | Debit | Credit -- same live Debit/Credit total
    footer as the Journal Voucher screen. Save ->
    engine.post_opening_balances(financial_year_id, rows, created_by,
    journal_date_ad). Only usable once per financial year (the Screen
    checks financial_year.closing_journal_entry_id / whether an Opening
    Balance journal already exists for this FY via
    engine.get_journals_for_document('Opening Balance', financial_year_id)
    before allowing a second run)."""
    def __init__(self, parent, engine: "AccountingEngine", financial_year_model, coa_model): ...
    def _add_row(self) -> None: ...
    def _update_totals_footer(self) -> None: ...
    def _on_save_clicked(self) -> None: ...
```

### 1.8 Dashboard Wiring

`screens/dashboard_screen.py` — the **"Accounts"** group (already created in Receipt Part 3, holding Receipt + Payment) gets five more entries: **"Chart of Accounts"**, **"Journal Voucher"** (opens `JournalListScreen`, whose "+ New Voucher" button opens `JournalVoucherFormScreen`), **"Account Ledger"**, **"Period Lock"**, **"Bank Reconciliation"**. "Opening Balance" is reachable from the Chart of Accounts screen or Period Lock screen (a one-time-per-year setup action, not a frequently-revisited list) rather than getting its own permanent sidebar row.

---

## 2. Wiring Checklist — all SIX accounting-posting hooks, in one place

```python
# Construction order:

from models.chart_of_accounts_model import ChartOfAccountsModel
from models.journal_model import JournalModel
from models.auto_accounting_rule_model import AutoAccountingRuleModel
from models.accounting_period_model import AccountingPeriodModel
from models.bank_reconciliation_model import BankReconciliationModel
from engines.accounting_engine import AccountingEngine

accounting_engine = AccountingEngine(
    period_model=AccountingPeriodModel(),
    bank_recon_model=BankReconciliationModel(),
)

# One trivial addition to engines/accounting_engine.py itself, a public
# wrapper for the Manual-journal Screen (Section 1.2):
#
#     def post_manual_journal(self, journal_date_ad, narration, line_rows, created_by):
#         return self._post_journal(
#             journal_date_ad=journal_date_ad, source_document_type='Manual',
#             source_document_id=None, narration=narration,
#             line_rows=line_rows, created_by=created_by,
#         )

# ---------------------------------------------------------------- #
# The SIX cross-module hooks -- same additive, optional-dependency
# pattern used throughout this project (Receipt's sale_engine.py hook
# and Payment's purchase_engine.py hook were the first two; this
# module needs the remaining four, PLUS accounting_engine ALSO needs
# adding to Receipt's and Payment's engines alongside the
# receipt_engine/payment_engine params they already gained):
# ---------------------------------------------------------------- #

# 1. engines/sale_engine.py -- create_sale_invoice(), after the
#    existing receipt_engine.apply_advance_to_invoice() call:
#        if self._accounting_engine:
#            self._accounting_engine.post_sale_invoice_journal(new_invoice_dict, created_by)
#    Constructor: + accounting_engine=None (optional)

# 2. engines/purchase_engine.py -- create_purchase_invoice(), after the
#    existing payment_engine.apply_advance_to_invoice() call:
#        if self._accounting_engine:
#            self._accounting_engine.post_purchase_invoice_journal(new_invoice_dict, created_by)
#    Constructor: + accounting_engine=None (optional)

# 3. engines/sale_return_engine.py -- create_return(), after stock
#    reversal posting:
#        if self._accounting_engine:
#            self._accounting_engine.post_sale_return_journal(new_return_dict, created_by)
#    Constructor: + accounting_engine=None (optional)

# 4. engines/purchase_return_engine.py -- create_return(), same pattern:
#        if self._accounting_engine:
#            self._accounting_engine.post_purchase_return_journal(new_return_dict, created_by)
#    Constructor: + accounting_engine=None (optional)

# 5. engines/receipt_engine.py -- create_receipt(), after the receipt
#    is saved:
#        if self._accounting_engine:
#            self._accounting_engine.post_receipt_journal(new_receipt_dict, created_by)
#    Constructor: + accounting_engine=None (optional, ADDED to the
#    receipt_engine_instance's own constructor -- separate from the
#    receipt_engine param that SaleEngine takes; these are two
#    different injection directions)

# 6. engines/payment_engine.py -- create_payment(), same pattern:
#        if self._accounting_engine:
#            self._accounting_engine.post_payment_journal(new_payment_dict, created_by)
#    Constructor: + accounting_engine=None (optional)

# Every one of these six is additive-only: omitting accounting_engine
# at construction time (passing nothing, defaulting to None) means
# ZERO behavior change to any already-working module. This is the same
# safety property every hook in this project has had since Receipt
# Part 3 first introduced the pattern.
```

---

## 3. Suggested Build Order (Accounts, step-by-step)

```
1. database/0018_create_accounts.sql   (chart_of_accounts + seed data + journal_entry + journal_entry_line + auto_accounting_rule + seed + tax_master + financial_year + accounting_period + opening_balance + bank_reconciliation + accounting_role_permission + seed, Part 1)
2. models/chart_of_accounts_model.py, models/journal_model.py, models/auto_accounting_rule_model.py,
   models/tax_master_model.py, models/financial_year_model.py, models/accounting_period_model.py,
   models/opening_balance_model.py, models/bank_reconciliation_model.py,
   models/accounting_role_permission_model.py    (Part 1 + Part 2 addition)
3. engines/journal_validator.py                    (Part 2)
4. engines/accounting_engine.py                    (Part 2, + post_manual_journal() added in Part 3)
5. Wire AccountingEngine in main.py                  (Part 3, section 2)
6. Add the SIX accounting_engine hooks across
   sale_engine.py / purchase_engine.py / sale_return_engine.py /
   purchase_return_engine.py / receipt_engine.py / payment_engine.py   (Part 3, section 2)
7. screens/chart_of_accounts_screen.py             (Part 3)
8. screens/journal_voucher_form_screen.py          (Part 3)
9. screens/journal_list_screen.py                  (Part 3)
10. screens/account_ledger_screen.py                (Part 3)
11. screens/period_lock_screen.py                   (Part 3)
12. screens/bank_reconciliation_screen.py           (Part 3)
13. screens/opening_balance_screen.py               (Part 3)
14. Wire Dashboard "Accounts" group's 5 new entries  (Part 3, section 1.8)
15. End-to-end test: post opening balances for a new FY -> confirm
    balanced -> post a Sale Invoice -> confirm its journal auto-appears
    (Customer Receivable Dr, Sales Cr, Output VAT Cr) and balances ->
    confirm Customer Ledger shows it -> post a Sale Return against that
    invoice -> confirm its journal auto-appears and reverses the right
    amounts -> record a Receipt -> confirm Cash/Bank Dr + Customer
    Receivable Cr -> lock the current period -> attempt to post a
    back-dated Sale Invoice into it -> confirm rejection -> reopen with
    reason -> confirm it now posts -> reverse a journal -> confirm a
    new opposite journal exists and the original shows Reversed ->
    confirm an auto-posted journal cannot be Cancelled directly from
    JournalListScreen -> reconcile a bank line -> confirm it drops off
    the Unreconciled list
```

---

## 4. Combined Blueprint JSON — Update

New `Accounts` module block. Six entries (`AC-HOOK-01` through `06`) modify SIX existing files across the whole project — the largest cross-module footprint of any blueprint so far, called out explicitly so none is missed during coding:

```json
[
  { "id": "AC01", "module": "Accounts", "phase": "Part-1 Database", "title": "Create chart_of_accounts + seed 6-group structure", "file": "database/0018_create_accounts.sql", "status": "done" },
  { "id": "AC02", "module": "Accounts", "phase": "Part-1 Database", "title": "Create journal_entry + journal_entry_line", "file": "database/0018_create_accounts.sql", "status": "done" },
  { "id": "AC03", "module": "Accounts", "phase": "Part-1 Database", "title": "Create auto_accounting_rule + seed Dr/Cr templates for all 6 transaction types", "file": "database/0018_create_accounts.sql", "status": "done" },
  { "id": "AC04", "module": "Accounts", "phase": "Part-1 Database", "title": "Create tax_master, financial_year, accounting_period, opening_balance, bank_reconciliation, accounting_role_permission", "file": "database/0018_create_accounts.sql", "status": "done" },
  { "id": "AC05", "module": "Accounts", "phase": "Part-1 Models", "title": "Create ChartOfAccountsModel + JournalModel (full)", "file": "models/chart_of_accounts_model.py / models/journal_model.py", "status": "done" },
  { "id": "AC06", "module": "Accounts", "phase": "Part-1 Models", "title": "Create remaining 6 models (tax/FY/period/opening-balance/bank-recon/role-permission) + AutoAccountingRuleModel", "file": "models/*.py", "status": "done" },
  { "id": "AC07", "module": "Accounts", "phase": "Part-2 Engines", "title": "Create journal_validator.py (balance rule, control-account rule, period lock)", "file": "engines/journal_validator.py", "status": "done" },
  { "id": "AC08", "module": "Accounts", "phase": "Part-2 Engines", "title": "Create AccountingEngine (rule-driven posting for all 6 transaction types, opening balances, reverse, cancel)", "file": "engines/accounting_engine.py", "status": "done" },
  { "id": "AC09", "module": "Accounts", "phase": "Part-2 Engines", "title": "Finalize run_year_end_closing() net-P&L aggregation jointly with Reports module's P&L query", "file": "engines/accounting_engine.py", "status": "pending" },
  { "id": "AC10", "module": "Accounts", "phase": "Part-3 Wiring", "title": "Wire AccountingEngine + add post_manual_journal() wrapper", "file": "main.py / engines/accounting_engine.py", "status": "pending" },
  { "id": "AC-HOOK-01", "module": "Accounts", "phase": "Part-3 Wiring", "title": "Add optional accounting_engine dependency + post_sale_invoice_journal() call to SaleEngine.create_sale_invoice()", "file": "engines/sale_engine.py", "status": "pending" },
  { "id": "AC-HOOK-02", "module": "Accounts", "phase": "Part-3 Wiring", "title": "Add optional accounting_engine dependency + post_purchase_invoice_journal() call to PurchaseEngine.create_purchase_invoice()", "file": "engines/purchase_engine.py", "status": "pending" },
  { "id": "AC-HOOK-03", "module": "Accounts", "phase": "Part-3 Wiring", "title": "Add optional accounting_engine dependency + post_sale_return_journal() call to SaleReturnEngine.create_return()", "file": "engines/sale_return_engine.py", "status": "pending" },
  { "id": "AC-HOOK-04", "module": "Accounts", "phase": "Part-3 Wiring", "title": "Add optional accounting_engine dependency + post_purchase_return_journal() call to PurchaseReturnEngine.create_return()", "file": "engines/purchase_return_engine.py", "status": "pending" },
  { "id": "AC-HOOK-05", "module": "Accounts", "phase": "Part-3 Wiring", "title": "Add optional accounting_engine dependency + post_receipt_journal() call to ReceiptEngine.create_receipt()", "file": "engines/receipt_engine.py", "status": "pending" },
  { "id": "AC-HOOK-06", "module": "Accounts", "phase": "Part-3 Wiring", "title": "Add optional accounting_engine dependency + post_payment_journal() call to PaymentEngine.create_payment()", "file": "engines/payment_engine.py", "status": "pending" },
  { "id": "AC11", "module": "Accounts", "phase": "Part-3 Screens", "title": "Create ChartOfAccountsScreen", "file": "screens/chart_of_accounts_screen.py", "status": "pending" },
  { "id": "AC12", "module": "Accounts", "phase": "Part-3 Screens", "title": "Create JournalVoucherFormScreen (Manual journals)", "file": "screens/journal_voucher_form_screen.py", "status": "pending" },
  { "id": "AC13", "module": "Accounts", "phase": "Part-3 Screens", "title": "Create JournalListScreen (View/Reverse/Cancel-Manual-only)", "file": "screens/journal_list_screen.py", "status": "pending" },
  { "id": "AC14", "module": "Accounts", "phase": "Part-3 Screens", "title": "Create AccountLedgerScreen (running-balance viewer)", "file": "screens/account_ledger_screen.py", "status": "pending" },
  { "id": "AC15", "module": "Accounts", "phase": "Part-3 Screens", "title": "Create PeriodLockScreen (lock/reopen with reason)", "file": "screens/period_lock_screen.py", "status": "pending" },
  { "id": "AC16", "module": "Accounts", "phase": "Part-3 Screens", "title": "Create BankReconciliationScreen", "file": "screens/bank_reconciliation_screen.py", "status": "pending" },
  { "id": "AC17", "module": "Accounts", "phase": "Part-3 Screens", "title": "Create OpeningBalanceScreen (once-per-FY)", "file": "screens/opening_balance_screen.py", "status": "pending" },
  { "id": "AC18", "module": "Accounts", "phase": "Part-3 Dashboard", "title": "Add 5 new entries to the 'Accounts' sidebar group (Chart of Accounts, Journal Voucher, Account Ledger, Period Lock, Bank Reconciliation)", "file": "screens/dashboard_screen.py", "status": "pending" },
  { "id": "AC19", "module": "Accounts", "phase": "Part-3 Test", "title": "End-to-end test: opening balances, auto-posted journals for all 6 transaction types balance and appear on ledgers, period lock rejection + reopen, reversal vs cancel distinction, bank reconciliation", "file": null, "status": "pending" }
]
```

> **Running total:** 77 (after Payment) + 19 (AC01–AC19, including the 6 hook tasks) = **96 tasks**.

---

**Part 3 complete — Accounts blueprint (Parts 1+2+3) fully documented.** This is the module that finally activates every "reserved" field left in Sale Return's `refund_mode`, Purchase Return's `settlement_mode`, and Receipt/Payment's advance system — none of those were wasted design, they were built for exactly this moment.

Only **Reports** remains before all module blueprints are complete and the single combined JSON can be assembled. Confirm and I'll move to **Reports** next.
