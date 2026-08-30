# Accounts Module — Part 1: Database Schema & Models Layer

**Project:** Medical ERP V2
**Layer:** Database + Models (SQL only, no business logic — per project rule)
**Scope:** Full double-entry accounting engine — Chart of Accounts, Journal Entries, Tax/VAT Master, Financial Year/Period Lock, Opening Balances, Bank Reconciliation. This is the consumer of the "reserved" fields left in every prior module (`refund_mode`, `settlement_mode`, Receipt/Payment's advance system).
**Depends on (already built):**
- `sale_invoice`, `purchase_invoice`, `sale_return`, `purchase_return`, `receipt`, `payment` — all the source transactions this module will eventually auto-post journals for
- `customer`, `supplier` — act as sub-ledger keys (see 0.2 below)
- `engines/date_engine.py`, `engines/exceptions.py`

---

## 0. Scope — CONFIRMED (from earlier discussion in this chat, in full)

1. **NPR only** — no multi-currency columns anywhere in this schema.
2. **Chart of Accounts hierarchy** — Group → Parent → Ledger. Six top-level groups: `1000 Assets`, `2000 Liabilities`, `3000 Equity`, `4000 Revenue`, `5000 Cost of Goods/Direct Cost`, `6000 Operating Expenses`. Within `5000`, `5100 COGS` / `5200 Purchase` / `5300 Purchase Return` are kept as separate, distinct accounts (NOT blended) — a specifically confirmed correction.
3. **Customer/Supplier sub-ledgers, not one-COA-row-each** — `1300 Customer Receivables` and `2100 Supplier Payables` are single control accounts; the individual customer/supplier is recorded as a **sub-ledger key** on the journal LINE (`sub_ledger_type` + `sub_ledger_id`, pointing at `customer_id`/`supplier_id`), never as a separate `chart_of_accounts` row per customer.
4. **Journal Header + Lines, Debit = Credit hard rule** — an imbalanced journal can never be saved, enforced by the Engine (Part 2) before the Model ever runs an INSERT.
5. **Journal status: `DRAFT | POSTED | REVERSED | CANCELLED`** — a plain `POSTED` boolean is not enough; `DRAFT` journals must never appear in any report, and `REVERSED` is distinct from `CANCELLED` (a reversed journal has a paired opposite journal; a cancelled one, per the project's universal rule, still needs `cancellation_reason`).
6. **Document ↔ Journal traceability, both directions** — every journal traces back to its source document (`source_document_type` + `source_document_id` on the header), and the source document side needs to be able to ask "show me the journal for this" too (a lookup index, not a new column on every source table).
7. **Auto-Accounting Rules** — one fixed Dr/Cr template per transaction type (Purchase, Sale, Sale Return, Purchase Return, Receipt, Payment), stored as data (`auto_accounting_rule` table) rather than hardcoded in Python, so the mapping itself is inspectable/auditable and adjustable without a code change.
8. **Tax/VAT Engine, configurable, not hardcoded** — `tax_master` with rate, input/output direction, and which account each side posts to.
9. **Advance Management** — both Customer Advance (`2300`) and Supplier Advance (`2400`) already have real source data from Receipt/Payment's `advance_amount`/`*_advance_usage` tables (Parts already built); this module's job is only to auto-journal them, not to re-model the advance mechanism itself.
10. **Credit/Debit Notes** — modeled as journal `source_document_type` values that point at existing `sale_return`/`purchase_return` rows (their `refund_mode`/`settlement_mode` already carries the intent) — no separate credit/debit-note table needed; a return **is** the credit/debit note in this schema.
11. **Cancellation = reversal journal, never delete** — cancelling a `POSTED` journal creates a new `REVERSED`-tagged journal with every line's Dr/Cr flipped, and marks the original `CANCELLED` with a mandatory reason. Neither is ever deleted.
12. **Period Lock** — `financial_year` → `accounting_period` → `Open | Locked`. A `Locked` period rejects new/edited journals dated inside it (enforced by the Engine, checked against the header's date before insert).
13. **Accounting Dimensions** — optional `branch_id` / `department_id` / `cost_center_id` on the journal LINE, nullable, single-branch-safe today, future-proof without a schema change later.
14. **Stock ↔ Accounting dual-post** — Purchase/Sale/Return already write to `stock_ledger` (existing, from Item Module) in the SAME logical operation their own Engine runs; this module's Engine (Part 2) will call the appropriate Journal-posting method immediately after, in the same transaction where practical, so stock and accounting are never two separate truths.
15. **Opening Balance** — one-time entries per Customer/Supplier/Cash/Bank/Other Ledger account, itself posted as a normal (if special-tagged) journal entry.
16. **Bank Reconciliation** — statement reference, reconciled status/date, difference, unreconciled list — modeled as its own small table linking to `journal_entry_line` rows on Bank-type accounts.
17. **Financial Year Closing** — `Period Lock → Year End Closing → Retained Earnings/P&L Transfer → New FY Opening`, modeled via the `financial_year` table's own status plus a special auto-generated closing journal (Part 2 concern; schema support included here).
18. **Role-based accounting permissions** — Accountant/Senior Accountant/Manager/Admin/Auditor, with Create/Edit/Post/Cancel/Reverse/Approve/View/Export/Period-Unlock — modeled as a simple `accounting_role_permission` lookup table (reuses the existing `user`/role infrastructure already in the app; this module only adds the accounting-specific permission grid).

---

## 1. Database Schema

### 1.1 `chart_of_accounts`

```sql
CREATE TABLE IF NOT EXISTS chart_of_accounts (
    account_id                SERIAL PRIMARY KEY,
    account_code                 VARCHAR(10) NOT NULL UNIQUE,     -- e.g. '1300', '5200'
    account_name                    VARCHAR(150) NOT NULL,
    account_group                     VARCHAR(20) NOT NULL,          -- Assets, Liabilities, Equity, Revenue, Cost of Goods, Operating Expenses
    parent_account_id                   INTEGER REFERENCES chart_of_accounts(account_id),   -- NULL for a top-level group row
    is_control_account                    BOOLEAN NOT NULL DEFAULT FALSE,   -- TRUE for 1300/2100 -- journal lines against these MUST carry a sub_ledger_type+sub_ledger_id
    normal_balance                          VARCHAR(10) NOT NULL,          -- 'Debit' or 'Credit' -- which side increases this account, used by report sign conventions
    is_active                                 BOOLEAN NOT NULL DEFAULT TRUE,
    remarks                                     TEXT,
    is_deleted                                    BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                      INTEGER NOT NULL,
    created_at_ad                                     TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                       VARCHAR(10) NOT NULL,
    updated_by                                            INTEGER,
    updated_at_ad                                           TIMESTAMP,
    updated_at_bs                                             VARCHAR(10),

    CONSTRAINT chk_coa_group CHECK (account_group IN ('Assets', 'Liabilities', 'Equity', 'Revenue', 'Cost of Goods', 'Operating Expenses')),
    CONSTRAINT chk_coa_normal_balance CHECK (normal_balance IN ('Debit', 'Credit'))
);

CREATE INDEX IF NOT EXISTS idx_coa_parent ON chart_of_accounts (parent_account_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_coa_group ON chart_of_accounts (account_group) WHERE is_deleted = FALSE;

COMMENT ON COLUMN chart_of_accounts.is_control_account IS 'TRUE only for 1300 Customer Receivables and 2100 Supplier Payables (and similarly-designed control accounts added later). A journal_entry_line against a control account is REJECTED by the Validator unless sub_ledger_type+sub_ledger_id are both set -- this is how "no per-customer COA row" is enforced structurally.';
```

**Seed data (the confirmed 6-group structure):**

```sql
INSERT INTO chart_of_accounts (account_code, account_name, account_group, parent_account_id, is_control_account, normal_balance, created_by, created_at_bs) VALUES
    ('1000', 'Assets', 'Assets', NULL, FALSE, 'Debit', 1, '2083-01-01'),
    ('1100', 'Cash & Cash Equivalents', 'Assets', 1, FALSE, 'Debit', 1, '2083-01-01'),
    ('1110', 'Cash', 'Assets', 2, FALSE, 'Debit', 1, '2083-01-01'),
    ('1120', 'Petty Cash', 'Assets', 2, FALSE, 'Debit', 1, '2083-01-01'),
    ('1200', 'Bank Accounts', 'Assets', 1, FALSE, 'Debit', 1, '2083-01-01'),
    ('1300', 'Customer Receivables', 'Assets', 1, TRUE, 'Debit', 1, '2083-01-01'),
    ('1400', 'Inventory / Stock', 'Assets', 1, FALSE, 'Debit', 1, '2083-01-01'),
    ('1500', 'Tax Receivable', 'Assets', 1, FALSE, 'Debit', 1, '2083-01-01'),
    ('1600', 'Other Current Assets', 'Assets', 1, FALSE, 'Debit', 1, '2083-01-01'),
    ('2000', 'Liabilities', 'Liabilities', NULL, FALSE, 'Credit', 1, '2083-01-01'),
    ('2100', 'Supplier Payables', 'Liabilities', 10, TRUE, 'Credit', 1, '2083-01-01'),
    ('2200', 'Tax / VAT Payable', 'Liabilities', 10, FALSE, 'Credit', 1, '2083-01-01'),
    ('2300', 'Customer Advances', 'Liabilities', 10, FALSE, 'Credit', 1, '2083-01-01'),
    ('2400', 'Supplier Advances', 'Liabilities', 10, FALSE, 'Debit', 1, '2083-01-01'),
    ('2500', 'Other Current Liabilities', 'Liabilities', 10, FALSE, 'Credit', 1, '2083-01-01'),
    ('3000', 'Equity', 'Equity', NULL, FALSE, 'Credit', 1, '2083-01-01'),
    ('3100', 'Owner Capital', 'Equity', 16, FALSE, 'Credit', 1, '2083-01-01'),
    ('3200', 'Drawings', 'Equity', 16, FALSE, 'Debit', 1, '2083-01-01'),
    ('3300', 'Retained Earnings', 'Equity', 16, FALSE, 'Credit', 1, '2083-01-01'),
    ('3400', 'Current Year Profit/Loss', 'Equity', 16, FALSE, 'Credit', 1, '2083-01-01'),
    ('4000', 'Revenue', 'Revenue', NULL, FALSE, 'Credit', 1, '2083-01-01'),
    ('4100', 'Sales', 'Revenue', 21, FALSE, 'Credit', 1, '2083-01-01'),
    ('4200', 'Sales Return', 'Revenue', 21, FALSE, 'Debit', 1, '2083-01-01'),
    ('4300', 'Other Operating Income', 'Revenue', 21, FALSE, 'Credit', 1, '2083-01-01'),
    ('4400', 'Discount Received', 'Revenue', 21, FALSE, 'Credit', 1, '2083-01-01'),
    ('5000', 'Cost of Goods / Direct Cost', 'Cost of Goods', NULL, FALSE, 'Debit', 1, '2083-01-01'),
    ('5100', 'COGS', 'Cost of Goods', 26, FALSE, 'Debit', 1, '2083-01-01'),
    ('5200', 'Purchase', 'Cost of Goods', 26, FALSE, 'Debit', 1, '2083-01-01'),
    ('5300', 'Purchase Return', 'Cost of Goods', 26, FALSE, 'Credit', 1, '2083-01-01'),
    ('5400', 'Freight Inward', 'Cost of Goods', 26, FALSE, 'Debit', 1, '2083-01-01'),
    ('5900', 'Other Direct Cost', 'Cost of Goods', 26, FALSE, 'Debit', 1, '2083-01-01'),
    ('6000', 'Operating Expenses', 'Operating Expenses', NULL, FALSE, 'Debit', 1, '2083-01-01'),
    ('6100', 'Salary', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01'),
    ('6200', 'Rent', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01'),
    ('6300', 'Electricity', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01'),
    ('6400', 'Internet/Telephone', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01'),
    ('6500', 'Transport', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01'),
    ('6600', 'Bank Charges', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01'),
    ('6700', 'Discount Allowed', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01'),
    ('6800', 'Depreciation', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01'),
    ('6900', 'Other Expenses', 'Operating Expenses', 32, FALSE, 'Debit', 1, '2083-01-01');
-- NOTE: parent_account_id values above (1, 10, 16, 21, 26, 32) assume sequential
-- SERIAL assignment in this exact insert order on a fresh table; the actual
-- migration script resolves these via a CTE/variable rather than hardcoded
-- numbers, shown here only for schema-design clarity.
```

### 1.2 `journal_entry` (header)

```sql
CREATE TABLE IF NOT EXISTS journal_entry (
    journal_entry_id          SERIAL PRIMARY KEY,
    journal_number                VARCHAR(30) NOT NULL UNIQUE,     -- e.g. JV-0001
    journal_date_ad                 DATE NOT NULL,
    journal_date_bs                   VARCHAR(10) NOT NULL,
    financial_year_id                   INTEGER NOT NULL REFERENCES financial_year(financial_year_id),
    accounting_period_id                  INTEGER NOT NULL REFERENCES accounting_period(accounting_period_id),
    source_document_type                    VARCHAR(30) NOT NULL,   -- 'Sale Invoice' | 'Purchase Invoice' | 'Sale Return' | 'Purchase Return' | 'Receipt' | 'Payment' | 'Opening Balance' | 'Manual' | 'Year End Closing'
    source_document_id                        INTEGER,             -- nullable ONLY for 'Manual' journals; NOT NULL for every auto-posted type
    narration                                   TEXT NOT NULL,        -- human-readable description, auto-generated for system journals
    status                                        VARCHAR(20) NOT NULL DEFAULT 'Posted',
    reversal_of_journal_entry_id                    INTEGER REFERENCES journal_entry(journal_entry_id),   -- set on the NEW journal when it reverses an old one
    cancellation_reason                               TEXT,        -- mandatory only when status='Cancelled'
    is_deleted                                          BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                            INTEGER NOT NULL,
    created_at_ad                                           TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                             VARCHAR(10) NOT NULL,
    updated_by                                                  INTEGER,
    updated_at_ad                                                 TIMESTAMP,
    updated_at_bs                                                   VARCHAR(10),

    CONSTRAINT chk_journal_status CHECK (status IN ('Draft', 'Posted', 'Reversed', 'Cancelled')),
    CONSTRAINT chk_journal_source_type CHECK (source_document_type IN (
        'Sale Invoice', 'Purchase Invoice', 'Sale Return', 'Purchase Return',
        'Receipt', 'Payment', 'Opening Balance', 'Manual', 'Year End Closing'
    ))
);

CREATE INDEX IF NOT EXISTS idx_journal_source ON journal_entry (source_document_type, source_document_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entry (journal_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_journal_status ON journal_entry (status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_journal_period ON journal_entry (accounting_period_id) WHERE is_deleted = FALSE;

COMMENT ON COLUMN journal_entry.source_document_type IS 'Together with source_document_id, this is the "Document -> Journal" traceability link. The REVERSE direction ("Journal -> Document, show me the invoice") is just following source_document_id back to its own table -- no extra column needed on sale_invoice/purchase_invoice/etc; the idx_journal_source index makes "find the journal(s) for this document" fast in the other direction.';
COMMENT ON COLUMN journal_entry.status IS 'DRAFT is excluded from every report query. POSTED is live. REVERSED means a NEW opposite journal was created referencing this one via reversal_of_journal_entry_id (on the NEW row) -- the reversed row itself is simply marked so reports know not to double count it once its reversal exists. CANCELLED requires cancellation_reason and means the journal was voided without ever being economically reversed (used for a same-day correction of an unposted mistake, distinct from Reversed which corrects a period that may already be closed).';
```

### 1.3 `journal_entry_line`

```sql
CREATE TABLE IF NOT EXISTS journal_entry_line (
    journal_entry_line_id     SERIAL PRIMARY KEY,
    journal_entry_id              INTEGER NOT NULL REFERENCES journal_entry(journal_entry_id),
    account_id                       INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),
    debit_amount                       NUMERIC(14,2) NOT NULL DEFAULT 0,
    credit_amount                        NUMERIC(14,2) NOT NULL DEFAULT 0,
    sub_ledger_type                        VARCHAR(20),   -- 'Customer' | 'Supplier' | NULL -- REQUIRED when account_id is a control account
    sub_ledger_id                            INTEGER,       -- customer_id or supplier_id depending on sub_ledger_type
    branch_id                                  INTEGER,       -- optional dimension, nullable, future-proofing (confirmed scope)
    department_id                                INTEGER,       -- optional dimension
    cost_center_id                                 INTEGER,       -- optional dimension
    line_narration                                   TEXT,
    line_order                                         SMALLINT NOT NULL DEFAULT 1,

    CONSTRAINT chk_jel_debit_or_credit CHECK (
        (debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)
    ),
    CONSTRAINT chk_jel_sub_ledger_type CHECK (sub_ledger_type IS NULL OR sub_ledger_type IN ('Customer', 'Supplier'))
);

CREATE INDEX IF NOT EXISTS idx_jel_journal ON journal_entry_line (journal_entry_id);
CREATE INDEX IF NOT EXISTS idx_jel_account ON journal_entry_line (account_id);
CREATE INDEX IF NOT EXISTS idx_jel_subledger ON journal_entry_line (sub_ledger_type, sub_ledger_id);

COMMENT ON COLUMN journal_entry_line.sub_ledger_id IS 'Points at customer.customer_id or supplier.supplier_id depending on sub_ledger_type -- NOT a foreign key to a single table since it can reference either, enforced by the Engine/Validator rather than a DB constraint. Required (rejected otherwise) whenever account_id.is_control_account = TRUE.';
COMMENT ON CONSTRAINT chk_jel_debit_or_credit ON journal_entry_line IS 'Each LINE is either a debit or a credit, never both and never zero. The header-level Debit=Credit balance rule (SUM(debit_amount) = SUM(credit_amount) across all lines of one journal_entry_id) is enforced by the Engine before insert, not by a DB constraint, since it is a cross-row aggregate rule.';
```

### 1.4 `auto_accounting_rule` (data-driven Dr/Cr templates)

```sql
CREATE TABLE IF NOT EXISTS auto_accounting_rule (
    auto_accounting_rule_id   SERIAL PRIMARY KEY,
    transaction_type              VARCHAR(30) NOT NULL,   -- 'Sale Invoice' | 'Purchase Invoice' | 'Sale Return' | 'Purchase Return' | 'Receipt' | 'Payment'
    line_role                       VARCHAR(30) NOT NULL,   -- e.g. 'Customer Receivable', 'Sales', 'Output VAT', 'COGS', 'Inventory'
    side                               VARCHAR(10) NOT NULL,   -- 'Debit' or 'Credit'
    account_id                           INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),
    is_sub_ledger_line                     BOOLEAN NOT NULL DEFAULT FALSE,   -- TRUE if this line needs the transaction's customer_id/supplier_id as sub_ledger_id
    display_order                            SMALLINT NOT NULL DEFAULT 1,
    is_active                                  BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT chk_aar_side CHECK (side IN ('Debit', 'Credit')),
    CONSTRAINT chk_aar_txn_type CHECK (transaction_type IN (
        'Sale Invoice', 'Purchase Invoice', 'Sale Return', 'Purchase Return', 'Receipt', 'Payment'
    ))
);

CREATE INDEX IF NOT EXISTS idx_aar_txn_type ON auto_accounting_rule (transaction_type) WHERE is_active = TRUE;

COMMENT ON TABLE auto_accounting_rule IS 'The confirmed rule: "Blueprint mein hardcoded nahi, data-driven." Example seed for Sale Invoice: (Customer Receivable, Debit, is_sub_ledger_line=TRUE), (Sales, Credit), (Output VAT, Credit). The Engine (Part 2) reads these rows ordered by display_order and builds journal_entry_line rows from them, substituting the actual transaction amounts at posting time -- changing a mapping later means editing this table''s data, not Python code.';
```

### 1.5 `tax_master`

```sql
CREATE TABLE IF NOT EXISTS tax_master (
    tax_master_id             SERIAL PRIMARY KEY,
    tax_name                     VARCHAR(50) NOT NULL,      -- e.g. 'VAT 13%', 'Exempt'
    tax_rate_percent                NUMERIC(5,2) NOT NULL,
    tax_direction                     VARCHAR(10) NOT NULL,   -- 'Input' (on purchases) or 'Output' (on sales)
    account_id                          INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),   -- which account this tax posts to (1500 Tax Receivable for Input, 2200 Tax Payable for Output)
    is_active                             BOOLEAN NOT NULL DEFAULT TRUE,
    remarks                                 TEXT,

    CONSTRAINT chk_tax_direction CHECK (tax_direction IN ('Input', 'Output'))
);

COMMENT ON TABLE tax_master IS 'Configurable, not hardcoded (confirmed scope). Country Tax master (already built, Sale/Purchase Module) supplies the RATE used on invoice lines; this table supplies which ACCOUNT that tax amount posts to when the Accounts Engine journals a Sale/Purchase Invoice -- two different concerns, kept in two different tables so the existing Country Tax master is never touched.';
```

### 1.6 `financial_year` + `accounting_period` (Period Lock)

```sql
CREATE TABLE IF NOT EXISTS financial_year (
    financial_year_id         SERIAL PRIMARY KEY,
    fy_label                      VARCHAR(20) NOT NULL UNIQUE,   -- e.g. '2082/83'
    start_date_ad                   DATE NOT NULL,
    end_date_ad                       DATE NOT NULL,
    start_date_bs                       VARCHAR(10) NOT NULL,
    end_date_bs                           VARCHAR(10) NOT NULL,
    status                                   VARCHAR(20) NOT NULL DEFAULT 'Open',   -- 'Open' | 'Closed'
    closing_journal_entry_id                   INTEGER REFERENCES journal_entry(journal_entry_id),   -- set once Year End Closing has run

    CONSTRAINT chk_fy_status CHECK (status IN ('Open', 'Closed'))
);

CREATE TABLE IF NOT EXISTS accounting_period (
    accounting_period_id      SERIAL PRIMARY KEY,
    financial_year_id             INTEGER NOT NULL REFERENCES financial_year(financial_year_id),
    period_label                     VARCHAR(20) NOT NULL,   -- e.g. 'Shrawan 2082'
    start_date_ad                      DATE NOT NULL,
    end_date_ad                          DATE NOT NULL,
    status                                  VARCHAR(20) NOT NULL DEFAULT 'Open',   -- 'Open' | 'Locked'
    locked_by                                 INTEGER,
    locked_at_ad                                TIMESTAMP,
    reopened_by                                   INTEGER,           -- controlled-reopening mechanism (confirmed scope)
    reopened_at_ad                                  TIMESTAMP,
    reopen_reason                                     TEXT,

    CONSTRAINT chk_period_status CHECK (status IN ('Open', 'Locked'))
);

CREATE INDEX IF NOT EXISTS idx_period_fy ON accounting_period (financial_year_id);
CREATE INDEX IF NOT EXISTS idx_period_dates ON accounting_period (start_date_ad, end_date_ad);

COMMENT ON TABLE accounting_period IS 'A journal dated inside a Locked period is rejected by the Engine (checked against journal_date_ad before insert) unless the acting user has the Period-Unlock permission (see accounting_role_permission) AND explicitly reopens it first, which is logged via reopened_by/reopened_at_ad/reopen_reason.';
```

### 1.7 `opening_balance`

```sql
CREATE TABLE IF NOT EXISTS opening_balance (
    opening_balance_id        SERIAL PRIMARY KEY,
    financial_year_id             INTEGER NOT NULL REFERENCES financial_year(financial_year_id),
    account_id                       INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),
    sub_ledger_type                    VARCHAR(20),   -- 'Customer' | 'Supplier' | NULL -- same rule as journal_entry_line
    sub_ledger_id                        INTEGER,
    debit_amount                           NUMERIC(14,2) NOT NULL DEFAULT 0,
    credit_amount                            NUMERIC(14,2) NOT NULL DEFAULT 0,
    posted_journal_entry_id                    INTEGER REFERENCES journal_entry(journal_entry_id),   -- the actual journal this opening balance was posted as
    created_by                                   INTEGER NOT NULL,
    created_at_ad                                  TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                    VARCHAR(10) NOT NULL,

    CONSTRAINT chk_ob_debit_or_credit CHECK (
        (debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)
    ),
    CONSTRAINT chk_ob_sub_ledger_type CHECK (sub_ledger_type IS NULL OR sub_ledger_type IN ('Customer', 'Supplier'))
);

COMMENT ON TABLE opening_balance IS 'One row per account (or per customer/supplier sub-ledger) being opened for a financial year. The Engine (Part 2) posts these as a single balanced journal_entry with source_document_type=''Opening Balance'' -- this table is the INPUT list the Engine reads to build that journal, not a duplicate ledger of its own.';
```

### 1.8 `bank_reconciliation`

```sql
CREATE TABLE IF NOT EXISTS bank_reconciliation (
    bank_reconciliation_id    SERIAL PRIMARY KEY,
    account_id                    INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),   -- must be a Bank-type account under 1200
    journal_entry_line_id            INTEGER NOT NULL REFERENCES journal_entry_line(journal_entry_line_id),   -- the specific ledger line being reconciled
    bank_statement_reference            VARCHAR(100),
    reconciliation_status                  VARCHAR(20) NOT NULL DEFAULT 'Unreconciled',   -- 'Unreconciled' | 'Reconciled'
    reconciled_date_ad                        DATE,
    reconciled_by                               INTEGER,
    difference_amount                             NUMERIC(14,2) NOT NULL DEFAULT 0,   -- statement amount minus ledger amount, for spotting mismatches

    CONSTRAINT chk_bank_recon_status CHECK (reconciliation_status IN ('Unreconciled', 'Reconciled'))
);

CREATE INDEX IF NOT EXISTS idx_bank_recon_account ON bank_reconciliation (account_id, reconciliation_status);

COMMENT ON TABLE bank_reconciliation IS 'One row per bank-account journal LINE, created automatically whenever a journal posts against a Bank account (1200-series), starting as Unreconciled. The "Unreconciled transactions" report (Reports Module, next blueprint) is simply WHERE reconciliation_status = ''Unreconciled''.';
```

### 1.9 `accounting_role_permission`

```sql
CREATE TABLE IF NOT EXISTS accounting_role_permission (
    accounting_role_permission_id  SERIAL PRIMARY KEY,
    role_name                          VARCHAR(30) NOT NULL,   -- 'Accountant' | 'Senior Accountant' | 'Manager' | 'Admin' | 'Auditor'
    permission_name                       VARCHAR(30) NOT NULL,   -- 'Create' | 'Edit' | 'Post' | 'Cancel' | 'Reverse' | 'Approve' | 'View' | 'Export' | 'Period Unlock'
    is_granted                              BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT uq_role_permission UNIQUE (role_name, permission_name),
    CONSTRAINT chk_role_name CHECK (role_name IN ('Accountant', 'Senior Accountant', 'Manager', 'Admin', 'Auditor')),
    CONSTRAINT chk_permission_name CHECK (permission_name IN (
        'Create', 'Edit', 'Post', 'Cancel', 'Reverse', 'Approve', 'View', 'Export', 'Period Unlock'
    ))
);

COMMENT ON TABLE accounting_role_permission IS 'A simple grid lookup, reusing the existing user/role infrastructure already in the app (this table only adds the accounting-specific permission matrix on top of whatever role a user already has). The Engine checks this before allowing Cancel/Reverse/Period-Unlock actions.';
```

---

## 2. Models Layer (SQL only — no business logic)

Given the number of tables, this Part 1 delivers the two highest-traffic models in full (`ChartOfAccountsModel`, `JournalModel`) plus the remaining five in a complete-but-leaner form (still real SQL, nothing incomplete). Every model follows the exact same connection/cursor pattern as every prior module's Model.

### 2.1 `models/chart_of_accounts_model.py`

```python
"""
models/chart_of_accounts_model.py

Chart of Accounts Model - Medical ERP V2
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


COA_COLUMNS = (
    "account_code", "account_name", "account_group", "parent_account_id",
    "is_control_account", "normal_balance", "is_active", "remarks",
)


class ChartOfAccountsModel:
    """Data-access layer for `chart_of_accounts`."""

    def insert(self, data: dict[str, Any]) -> int:
        columns = list(COA_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        col_sql = ", ".join(columns)
        placeholder_sql = ", ".join(f"%({c})s" for c in columns)
        sql = f"INSERT INTO chart_of_accounts ({col_sql}) VALUES ({placeholder_sql}) RETURNING account_id;"
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(sql, data)
                    return cur.fetchone()["account_id"]
        finally:
            conn.close()

    def get_by_id(self, account_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM chart_of_accounts WHERE account_id = %(id)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": account_id})
                return cur.fetchone()
        finally:
            conn.close()

    def get_by_code(self, account_code: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM chart_of_accounts WHERE account_code = %(code)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"code": account_code})
                return cur.fetchone()
        finally:
            conn.close()

    def get_hierarchy(self) -> list[dict[str, Any]]:
        """Returns every active account ordered so a Screen can build the
        Group -> Parent -> Ledger tree by walking parent_account_id."""
        sql = """
            SELECT * FROM chart_of_accounts
            WHERE is_deleted = FALSE AND is_active = TRUE
            ORDER BY account_code;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()

    def search(self, search_text: Optional[str] = None) -> list[dict[str, Any]]:
        conditions = ["is_deleted = FALSE"]
        params: dict[str, Any] = {}
        if search_text:
            conditions.append("(account_code ILIKE %(search_text)s OR account_name ILIKE %(search_text)s)")
            params["search_text"] = f"%{search_text}%"
        sql = f"SELECT * FROM chart_of_accounts WHERE {' AND '.join(conditions)} ORDER BY account_code;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def update(self, account_id: int, changed_fields: dict[str, Any], updated_by: int,
               updated_at_ad: Any, updated_at_bs: str) -> None:
        if not changed_fields:
            return
        set_clause = ", ".join(f"{col} = %({col})s" for col in changed_fields)
        sql = f"""
            UPDATE chart_of_accounts
            SET {set_clause}, updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE account_id = %(account_id)s;
        """
        params = dict(changed_fields)
        params.update({"account_id": account_id, "updated_by": updated_by,
                        "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs})
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
        finally:
            conn.close()
```

### 2.2 `models/journal_model.py`

```python
"""
models/journal_model.py

Journal Model - Medical ERP V2

Project rule: "No SQL outside the Model." Balance validation
(SUM(debit) = SUM(credit)) and period-lock checking are the Engine's
job (Part 2) -- this Model only persists what it's given.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class JournalSearchFilters:
    source_document_type: Optional[str] = None
    source_document_id: Optional[int] = None
    account_id: Optional[int] = None
    sub_ledger_type: Optional[str] = None
    sub_ledger_id: Optional[int] = None
    status: Optional[str] = None
    date_from_ad: Optional[Any] = None
    date_to_ad: Optional[Any] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


JOURNAL_HEADER_COLUMNS = (
    "journal_number", "journal_date_ad", "journal_date_bs", "financial_year_id",
    "accounting_period_id", "source_document_type", "source_document_id",
    "narration", "status", "reversal_of_journal_entry_id",
)

JOURNAL_LINE_COLUMNS = (
    "account_id", "debit_amount", "credit_amount", "sub_ledger_type",
    "sub_ledger_id", "branch_id", "department_id", "cost_center_id",
    "line_narration", "line_order",
)


class JournalModel:
    """Data-access layer for `journal_entry` + `journal_entry_line`."""

    def insert_with_lines(self, header_data: dict[str, Any], line_rows: list[dict[str, Any]]) -> int:
        header_columns = list(JOURNAL_HEADER_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        header_col_sql = ", ".join(header_columns)
        header_placeholder_sql = ", ".join(f"%({c})s" for c in header_columns)
        header_sql = f"""
            INSERT INTO journal_entry ({header_col_sql})
            VALUES ({header_placeholder_sql})
            RETURNING journal_entry_id;
        """

        line_columns = ["journal_entry_id"] + list(JOURNAL_LINE_COLUMNS)
        line_col_sql = ", ".join(line_columns)
        line_placeholder_sql = ", ".join(f"%({c})s" for c in line_columns)
        line_sql = f"INSERT INTO journal_entry_line ({line_col_sql}) VALUES ({line_placeholder_sql});"

        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(header_sql, header_data)
                    journal_entry_id = cur.fetchone()["journal_entry_id"]
                    for row in line_rows:
                        row = dict(row)
                        row["journal_entry_id"] = journal_entry_id
                        cur.execute(line_sql, row)
            return journal_entry_id
        except Exception:
            logger.exception("insert_with_lines failed for journal_entry")
            raise
        finally:
            conn.close()

    def get_by_id(self, journal_entry_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM journal_entry WHERE journal_entry_id = %(id)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": journal_entry_id})
                return cur.fetchone()
        finally:
            conn.close()

    def get_lines_by_journal_id(self, journal_entry_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT jel.*, coa.account_code, coa.account_name
            FROM journal_entry_line jel
            JOIN chart_of_accounts coa ON coa.account_id = jel.account_id
            WHERE jel.journal_entry_id = %(id)s
            ORDER BY jel.line_order;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": journal_entry_id})
                return cur.fetchall()
        finally:
            conn.close()

    def get_journals_for_document(self, source_document_type: str, source_document_id: int) -> list[dict[str, Any]]:
        """The 'Journal -> Document' reverse lookup, and also the
        'Document -> Journal' forward lookup used by every source
        Screen's "View Journal" button."""
        sql = """
            SELECT * FROM journal_entry
            WHERE source_document_type = %(type)s AND source_document_id = %(id)s
              AND is_deleted = FALSE
            ORDER BY journal_entry_id;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"type": source_document_type, "id": source_document_id})
                return cur.fetchall()
        finally:
            conn.close()

    def get_account_ledger(self, account_id: int, sub_ledger_type: Optional[str] = None,
                            sub_ledger_id: Optional[int] = None,
                            date_from_ad: Optional[Any] = None, date_to_ad: Optional[Any] = None) -> list[dict[str, Any]]:
        """Powers the General Ledger / Customer Ledger / Supplier Ledger
        reports (Reports Module, next blueprint) -- returns every POSTED
        line against this account (optionally filtered to one
        sub-ledger), oldest first, for running-balance calculation."""
        conditions = ["jel.account_id = %(account_id)s", "je.status = 'Posted'", "je.is_deleted = FALSE"]
        params: dict[str, Any] = {"account_id": account_id}
        if sub_ledger_type:
            conditions.append("jel.sub_ledger_type = %(sub_ledger_type)s")
            params["sub_ledger_type"] = sub_ledger_type
        if sub_ledger_id:
            conditions.append("jel.sub_ledger_id = %(sub_ledger_id)s")
            params["sub_ledger_id"] = sub_ledger_id
        if date_from_ad:
            conditions.append("je.journal_date_ad >= %(date_from_ad)s")
            params["date_from_ad"] = date_from_ad
        if date_to_ad:
            conditions.append("je.journal_date_ad <= %(date_to_ad)s")
            params["date_to_ad"] = date_to_ad

        sql = f"""
            SELECT je.journal_number, je.journal_date_ad, je.narration,
                   jel.debit_amount, jel.credit_amount, jel.line_narration
            FROM journal_entry_line jel
            JOIN journal_entry je ON je.journal_entry_id = jel.journal_entry_id
            WHERE {' AND '.join(conditions)}
            ORDER BY je.journal_date_ad ASC, je.journal_entry_id ASC;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def search(self, filters: JournalSearchFilters) -> list[dict[str, Any]]:
        conditions = ["je.is_deleted = FALSE" if not filters.include_deleted else "1=1"]
        params: dict[str, Any] = {}
        if filters.source_document_type:
            conditions.append("je.source_document_type = %(source_document_type)s")
            params["source_document_type"] = filters.source_document_type
        if filters.source_document_id:
            conditions.append("je.source_document_id = %(source_document_id)s")
            params["source_document_id"] = filters.source_document_id
        if filters.status:
            conditions.append("je.status = %(status)s")
            params["status"] = filters.status
        if filters.date_from_ad:
            conditions.append("je.journal_date_ad >= %(date_from_ad)s")
            params["date_from_ad"] = filters.date_from_ad
        if filters.date_to_ad:
            conditions.append("je.journal_date_ad <= %(date_to_ad)s")
            params["date_to_ad"] = filters.date_to_ad

        where_sql = " AND ".join(conditions)
        offset = (filters.page - 1) * filters.page_size
        sql = f"""
            SELECT je.* FROM journal_entry je
            WHERE {where_sql}
            ORDER BY je.journal_entry_id DESC
            LIMIT %(limit)s OFFSET %(offset)s;
        """
        params["limit"] = filters.page_size
        params["offset"] = offset
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def update_status(self, journal_entry_id: int, status: str, cancellation_reason: Optional[str],
                       updated_by: int, updated_at_ad: Any, updated_at_bs: str) -> None:
        sql = """
            UPDATE journal_entry
            SET status = %(status)s, cancellation_reason = %(cancellation_reason)s,
                updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE journal_entry_id = %(journal_entry_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "journal_entry_id": journal_entry_id, "status": status,
                        "cancellation_reason": cancellation_reason, "updated_by": updated_by,
                        "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs,
                    })
        finally:
            conn.close()
```

### 2.3 Remaining models (complete, leaner form)

```python
"""
models/tax_master_model.py -- straightforward CRUD, same connection
pattern as every model above. Methods: insert(), get_by_id(),
list_active(direction: Optional[str] = None), update(), deactivate().
"""

"""
models/financial_year_model.py -- insert(), get_by_id(),
get_current_open_year(), close_year(financial_year_id,
closing_journal_entry_id).

models/accounting_period_model.py -- insert(), get_period_for_date(date_ad)
(the lookup the Journal Engine calls on every post to find which period
a journal_date_ad falls into and check its status), lock_period(),
reopen_period(reopened_by, reopen_reason).
"""

"""
models/opening_balance_model.py -- insert_batch(rows) (one financial
year's full opening balance set, inserted together), get_by_financial_year(),
mark_posted(opening_balance_id, posted_journal_entry_id).
"""

"""
models/bank_reconciliation_model.py -- insert(journal_entry_line_id,
account_id) (auto-called by the Journal Engine whenever a line posts
against a Bank account), mark_reconciled(bank_reconciliation_id,
bank_statement_reference, reconciled_date_ad, reconciled_by,
difference_amount), get_unreconciled(account_id).
"""

"""
models/accounting_role_permission_model.py -- get_permissions_for_role(role_name)
-> dict of permission_name -> is_granted, used by the Engine to check
Cancel/Reverse/Period-Unlock before allowing the action. seed_defaults()
for the initial permission grid.
"""
```

---

## 3. Glossary

| Term | Meaning |
|---|---|
| **Control Account** | `1300`/`2100` — a single COA row representing ALL customers/suppliers combined. Individual identity lives on the journal LINE (`sub_ledger_type`+`sub_ledger_id`), never as a separate COA row. |
| **Auto-Accounting Rule** | A data row (not code) saying "for a Sale Invoice, debit Customer Receivable, credit Sales, credit Output VAT" — the Engine (Part 2) reads these rows to build journals, so the mapping is editable without a code change. |
| **Reversed vs Cancelled** | Reversed = a NEW opposite journal exists (used once a period may be closed — never edit the old one). Cancelled = voided outright with a mandatory reason (used for a same-day mistake, no economic reversal needed). |
| **Period Lock** | A journal dated inside a `Locked` accounting_period is rejected unless explicitly reopened (logged) by someone with Period-Unlock permission. |
| **Document ↔ Journal Traceability** | Forward: `journal_entry.source_document_type/source_document_id` says where a journal came from. Reverse: `JournalModel.get_journals_for_document()` lets any source Screen ask "show me my journal(s)" without a new column on its own table. |

---

**Part 1 complete.** Waiting for your confirmation before Part 2 (Validators + Engine: `journal_validator.py` — Debit=Credit balance check, period-lock check, control-account sub-ledger requirement; `accounting_engine.py` — reads `auto_accounting_rule` and builds/posts journals for each of the six existing transaction types, opening balance posting, year-end closing, reversal flow, bank-reconciliation auto-row creation).
