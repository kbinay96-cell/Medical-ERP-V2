BEGIN;

CREATE TABLE IF NOT EXISTS chart_of_accounts (
    account_id SERIAL PRIMARY KEY,
    account_code VARCHAR(10) NOT NULL UNIQUE,
    account_name VARCHAR(150) NOT NULL,
    account_group VARCHAR(20) NOT NULL CHECK (
        account_group IN ('Assets', 'Liabilities', 'Equity', 'Revenue', 'Cost of Goods', 'Operating Expenses')
    ),
    parent_account_id INTEGER REFERENCES chart_of_accounts(account_id),
    is_control_account BOOLEAN NOT NULL DEFAULT FALSE,
    normal_balance VARCHAR(10) NOT NULL CHECK (normal_balance IN ('Debit', 'Credit')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    remarks TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_by INTEGER NOT NULL DEFAULT 1,
    created_at_ad TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs VARCHAR(10) NOT NULL DEFAULT '',
    updated_by INTEGER,
    updated_at_ad TIMESTAMP,
    updated_at_bs VARCHAR(10)
);
CREATE INDEX IF NOT EXISTS idx_coa_parent ON chart_of_accounts (parent_account_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_coa_group ON chart_of_accounts (account_group) WHERE is_deleted = FALSE;

CREATE TABLE IF NOT EXISTS financial_year (
    financial_year_id SERIAL PRIMARY KEY,
    fy_label VARCHAR(20) NOT NULL UNIQUE,
    start_date_ad DATE NOT NULL,
    end_date_ad DATE NOT NULL,
    start_date_bs VARCHAR(10) NOT NULL,
    end_date_bs VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Closed')),
    closing_journal_entry_id INTEGER
);

CREATE TABLE IF NOT EXISTS accounting_period (
    accounting_period_id SERIAL PRIMARY KEY,
    financial_year_id INTEGER NOT NULL REFERENCES financial_year(financial_year_id),
    period_label VARCHAR(20) NOT NULL,
    start_date_ad DATE NOT NULL,
    end_date_ad DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Locked')),
    locked_by INTEGER,
    locked_at_ad TIMESTAMP,
    reopened_by INTEGER,
    reopened_at_ad TIMESTAMP,
    reopen_reason TEXT,
    CHECK (start_date_ad <= end_date_ad),
    UNIQUE (financial_year_id, start_date_ad)
);
CREATE INDEX IF NOT EXISTS idx_period_fy ON accounting_period (financial_year_id);
CREATE INDEX IF NOT EXISTS idx_period_dates ON accounting_period (start_date_ad, end_date_ad);
CREATE UNIQUE INDEX IF NOT EXISTS uq_accounting_period_fy_start
    ON accounting_period (financial_year_id, start_date_ad);

CREATE TABLE IF NOT EXISTS journal_entry (
    journal_entry_id SERIAL PRIMARY KEY,
    journal_number VARCHAR(30) NOT NULL UNIQUE,
    journal_date_ad DATE NOT NULL,
    journal_date_bs VARCHAR(10) NOT NULL,
    financial_year_id INTEGER NOT NULL REFERENCES financial_year(financial_year_id),
    accounting_period_id INTEGER NOT NULL REFERENCES accounting_period(accounting_period_id),
    source_document_type VARCHAR(30) NOT NULL CHECK (source_document_type IN (
        'Sale Invoice', 'Purchase Invoice', 'Sale Return', 'Purchase Return', 'Receipt',
        'Payment', 'Opening Balance', 'Manual', 'Year End Closing'
    )),
    source_document_id INTEGER,
    narration TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Posted' CHECK (status IN ('Draft', 'Posted', 'Reversed', 'Cancelled')),
    reversal_of_journal_entry_id INTEGER REFERENCES journal_entry(journal_entry_id),
    cancellation_reason TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_by INTEGER NOT NULL,
    created_at_ad TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs VARCHAR(10) NOT NULL,
    updated_by INTEGER,
    updated_at_ad TIMESTAMP,
    updated_at_bs VARCHAR(10),
    CHECK (source_document_type = 'Manual' OR source_document_id IS NOT NULL),
    CHECK (status <> 'Cancelled' OR NULLIF(BTRIM(cancellation_reason), '') IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_journal_source ON journal_entry (source_document_type, source_document_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entry (journal_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_journal_status ON journal_entry (status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_journal_period ON journal_entry (accounting_period_id) WHERE is_deleted = FALSE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_financial_year_closing_journal'
    ) THEN
        ALTER TABLE financial_year ADD CONSTRAINT fk_financial_year_closing_journal
            FOREIGN KEY (closing_journal_entry_id) REFERENCES journal_entry(journal_entry_id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS journal_entry_line (
    journal_entry_line_id SERIAL PRIMARY KEY,
    journal_entry_id INTEGER NOT NULL REFERENCES journal_entry(journal_entry_id),
    account_id INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),
    debit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    sub_ledger_type VARCHAR(20) CHECK (sub_ledger_type IS NULL OR sub_ledger_type IN ('Customer', 'Supplier')),
    sub_ledger_id INTEGER,
    branch_id INTEGER,
    department_id INTEGER,
    cost_center_id INTEGER,
    line_narration TEXT,
    line_order SMALLINT NOT NULL DEFAULT 1,
    CHECK ((debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0))
);
CREATE INDEX IF NOT EXISTS idx_jel_journal ON journal_entry_line (journal_entry_id);
CREATE INDEX IF NOT EXISTS idx_jel_account ON journal_entry_line (account_id);
CREATE INDEX IF NOT EXISTS idx_jel_subledger ON journal_entry_line (sub_ledger_type, sub_ledger_id);

CREATE TABLE IF NOT EXISTS auto_accounting_rule (
    auto_accounting_rule_id SERIAL PRIMARY KEY,
    transaction_type VARCHAR(30) NOT NULL CHECK (transaction_type IN (
        'Sale Invoice', 'Purchase Invoice', 'Sale Return', 'Purchase Return', 'Receipt', 'Payment'
    )),
    line_role VARCHAR(30) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('Debit', 'Credit')),
    account_id INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),
    is_sub_ledger_line BOOLEAN NOT NULL DEFAULT FALSE,
    display_order SMALLINT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (transaction_type, line_role)
);
CREATE INDEX IF NOT EXISTS idx_aar_txn_type ON auto_accounting_rule (transaction_type) WHERE is_active = TRUE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_auto_accounting_rule_type_role
    ON auto_accounting_rule (transaction_type, line_role);

CREATE TABLE IF NOT EXISTS tax_master (
    tax_master_id SERIAL PRIMARY KEY,
    tax_name VARCHAR(50) NOT NULL,
    tax_rate_percent NUMERIC(5,2) NOT NULL CHECK (tax_rate_percent >= 0),
    tax_direction VARCHAR(10) NOT NULL CHECK (tax_direction IN ('Input', 'Output')),
    account_id INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS opening_balance (
    opening_balance_id SERIAL PRIMARY KEY,
    financial_year_id INTEGER NOT NULL REFERENCES financial_year(financial_year_id),
    account_id INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),
    sub_ledger_type VARCHAR(20) CHECK (sub_ledger_type IS NULL OR sub_ledger_type IN ('Customer', 'Supplier')),
    sub_ledger_id INTEGER,
    debit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    credit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    posted_journal_entry_id INTEGER REFERENCES journal_entry(journal_entry_id),
    created_by INTEGER NOT NULL,
    created_at_ad TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs VARCHAR(10) NOT NULL,
    CHECK ((debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0))
);

CREATE TABLE IF NOT EXISTS bank_reconciliation (
    bank_reconciliation_id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),
    journal_entry_line_id INTEGER NOT NULL UNIQUE REFERENCES journal_entry_line(journal_entry_line_id),
    bank_statement_reference VARCHAR(100),
    reconciliation_status VARCHAR(20) NOT NULL DEFAULT 'Unreconciled'
        CHECK (reconciliation_status IN ('Unreconciled', 'Reconciled')),
    reconciled_date_ad DATE,
    reconciled_by INTEGER,
    difference_amount NUMERIC(14,2) NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_bank_recon_account
    ON bank_reconciliation (account_id, reconciliation_status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bank_reconciliation_journal_line
    ON bank_reconciliation (journal_entry_line_id);

INSERT INTO financial_year (fy_label, start_date_ad, end_date_ad, start_date_bs, end_date_bs, status)
SELECT financialyear, startaddate, endaddate, startbsdate, endbsdate,
       CASE WHEN isclosed THEN 'Closed' ELSE 'Open' END
FROM financialyear
WHERE startaddate IS NOT NULL AND endaddate IS NOT NULL
  AND endaddate >= startaddate
ON CONFLICT (fy_label) DO NOTHING;

INSERT INTO accounting_period
    (financial_year_id, period_label, start_date_ad, end_date_ad, status)
SELECT fy.financial_year_id,
       TO_CHAR(period_start, 'Mon YYYY'),
       period_start::date,
       LEAST((period_start + INTERVAL '1 month' - INTERVAL '1 day')::date, fy.end_date_ad),
       CASE WHEN fy.status = 'Closed' THEN 'Locked' ELSE 'Open' END
FROM financial_year fy
CROSS JOIN LATERAL GENERATE_SERIES(
    fy.start_date_ad::timestamp,
    fy.end_date_ad::timestamp,
    INTERVAL '1 month'
) AS period_start
ON CONFLICT (financial_year_id, start_date_ad) DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting_role_permission (
    accounting_role_permission_id SERIAL PRIMARY KEY,
    role_name VARCHAR(30) NOT NULL CHECK (
        role_name IN ('Accountant', 'Senior Accountant', 'Manager', 'Admin', 'Auditor')
    ),
    permission_name VARCHAR(30) NOT NULL CHECK (
        permission_name IN ('Create', 'Edit', 'Post', 'Cancel', 'Reverse', 'Approve', 'View', 'Export', 'Period Unlock')
    ),
    is_granted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (role_name, permission_name)
);

DO $$
DECLARE
    account_row RECORD;
    parent_id INTEGER;
BEGIN
    FOR account_row IN
        SELECT * FROM (VALUES
            ('1000','Assets','Assets',NULL,FALSE,'Debit',0),
            ('2000','Liabilities','Liabilities',NULL,FALSE,'Credit',0),
            ('3000','Equity','Equity',NULL,FALSE,'Credit',0),
            ('4000','Revenue','Revenue',NULL,FALSE,'Credit',0),
            ('5000','Cost of Goods / Direct Cost','Cost of Goods',NULL,FALSE,'Debit',0),
            ('6000','Operating Expenses','Operating Expenses',NULL,FALSE,'Debit',0),
            ('1100','Cash & Cash Equivalents','Assets','1000',FALSE,'Debit',1),
            ('1200','Bank Accounts','Assets','1000',FALSE,'Debit',1),
            ('1300','Customer Receivables','Assets','1000',TRUE,'Debit',1),
            ('1400','Inventory / Stock','Assets','1000',FALSE,'Debit',1),
            ('1500','Tax Receivable','Assets','1000',FALSE,'Debit',1),
            ('1600','Other Current Assets','Assets','1000',FALSE,'Debit',1),
            ('2100','Supplier Payables','Liabilities','2000',TRUE,'Credit',1),
            ('2200','Tax / VAT Payable','Liabilities','2000',FALSE,'Credit',1),
            ('2300','Customer Advances','Liabilities','2000',FALSE,'Credit',1),
            ('2400','Supplier Advances','Liabilities','2000',FALSE,'Debit',1),
            ('2500','Other Current Liabilities','Liabilities','2000',FALSE,'Credit',1),
            ('3100','Owner Capital','Equity','3000',FALSE,'Credit',1),
            ('3200','Drawings','Equity','3000',FALSE,'Debit',1),
            ('3300','Retained Earnings','Equity','3000',FALSE,'Credit',1),
            ('3400','Current Year Profit/Loss','Equity','3000',FALSE,'Credit',1),
            ('4100','Sales','Revenue','4000',FALSE,'Credit',1),
            ('4200','Sales Return','Revenue','4000',FALSE,'Debit',1),
            ('4300','Other Operating Income','Revenue','4000',FALSE,'Credit',1),
            ('4400','Discount Received','Revenue','4000',FALSE,'Credit',1),
            ('5100','COGS','Cost of Goods','5000',FALSE,'Debit',1),
            ('5200','Purchase','Cost of Goods','5000',FALSE,'Debit',1),
            ('5300','Purchase Return','Cost of Goods','5000',FALSE,'Credit',1),
            ('5400','Freight Inward','Cost of Goods','5000',FALSE,'Debit',1),
            ('5900','Other Direct Cost','Cost of Goods','5000',FALSE,'Debit',1),
            ('6100','Salary','Operating Expenses','6000',FALSE,'Debit',1),
            ('6200','Rent','Operating Expenses','6000',FALSE,'Debit',1),
            ('6300','Electricity','Operating Expenses','6000',FALSE,'Debit',1),
            ('6400','Internet/Telephone','Operating Expenses','6000',FALSE,'Debit',1),
            ('6500','Transport','Operating Expenses','6000',FALSE,'Debit',1),
            ('6600','Bank Charges','Operating Expenses','6000',FALSE,'Debit',1),
            ('6700','Discount Allowed','Operating Expenses','6000',FALSE,'Debit',1),
            ('6800','Depreciation','Operating Expenses','6000',FALSE,'Debit',1),
            ('6900','Other Expenses','Operating Expenses','6000',FALSE,'Debit',1),
            ('1110','Cash','Assets','1100',FALSE,'Debit',2),
            ('1120','Petty Cash','Assets','1100',FALSE,'Debit',2),
            ('1210','Primary Bank','Assets','1200',FALSE,'Debit',2)
        ) AS accounts(account_code, account_name, account_group, parent_code, is_control, normal_balance, depth)
        ORDER BY depth, account_code
    LOOP
        parent_id := NULL;
        IF account_row.parent_code IS NOT NULL THEN
            SELECT account_id INTO parent_id
            FROM chart_of_accounts WHERE account_code = account_row.parent_code;
        END IF;
        INSERT INTO chart_of_accounts
            (account_code, account_name, account_group, parent_account_id,
             is_control_account, normal_balance, created_by, created_at_bs)
        VALUES
            (account_row.account_code, account_row.account_name, account_row.account_group,
             parent_id, account_row.is_control, account_row.normal_balance, 1, '2083-01-01')
        ON CONFLICT (account_code) DO NOTHING;
    END LOOP;
END $$;

INSERT INTO auto_accounting_rule
    (transaction_type, line_role, side, account_id, is_sub_ledger_line, display_order)
SELECT seed.transaction_type, seed.line_role, seed.side, coa.account_id, seed.is_sub_ledger_line, seed.display_order
FROM (VALUES
    ('Sale Invoice','Customer Receivable','Debit','1300',TRUE,1),
    ('Sale Invoice','Sales','Credit','4100',FALSE,2),
    ('Sale Invoice','Output VAT','Credit','2200',FALSE,3),
    ('Purchase Invoice','Purchase','Debit','5200',FALSE,1),
    ('Purchase Invoice','Input VAT','Debit','1500',FALSE,2),
    ('Purchase Invoice','Supplier Payable','Credit','2100',TRUE,3),
    ('Sale Return','Sales Return','Debit','4200',FALSE,1),
    ('Sale Return','Output VAT Reversal','Debit','2200',FALSE,2),
    ('Sale Return','Customer Receivable Reversal','Credit','1300',TRUE,3),
    ('Purchase Return','Purchase Return','Credit','5300',FALSE,1),
    ('Purchase Return','Input VAT Reversal','Credit','1500',FALSE,2),
    ('Purchase Return','Supplier Payable Reversal','Debit','2100',TRUE,3),
    ('Receipt','Cash/Bank','Debit','1110',FALSE,1),
    ('Receipt','Customer Receivable','Credit','1300',TRUE,2),
    ('Receipt','Customer Advance','Credit','2300',FALSE,3),
    ('Payment','Supplier Payable','Debit','2100',TRUE,1),
    ('Payment','Supplier Advance','Debit','2400',FALSE,2),
    ('Payment','Cash/Bank','Credit','1110',FALSE,3)
) AS seed(transaction_type, line_role, side, account_code, is_sub_ledger_line, display_order)
JOIN chart_of_accounts coa ON coa.account_code = seed.account_code
ON CONFLICT (transaction_type, line_role) DO NOTHING;

INSERT INTO accounting_role_permission (role_name, permission_name, is_granted)
SELECT roles.role_name, permissions.permission_name,
       CASE
           WHEN roles.role_name IN ('Manager', 'Admin') THEN TRUE
           WHEN roles.role_name = 'Accountant' AND permissions.permission_name IN ('Create','Edit','Post','View') THEN TRUE
           WHEN roles.role_name = 'Senior Accountant'
                AND permissions.permission_name IN ('Create','Edit','Post','Cancel','Reverse','View','Export') THEN TRUE
           WHEN roles.role_name = 'Auditor' AND permissions.permission_name IN ('View','Export') THEN TRUE
           ELSE FALSE
       END
FROM (VALUES ('Accountant'),('Senior Accountant'),('Manager'),('Admin'),('Auditor')) roles(role_name)
CROSS JOIN (VALUES
    ('Create'),('Edit'),('Post'),('Cancel'),('Reverse'),('Approve'),('View'),('Export'),('Period Unlock')
) permissions(permission_name)
ON CONFLICT (role_name, permission_name) DO NOTHING;

INSERT INTO role_permissions
    (roleid, screenname, can_view, can_add, can_edit, can_delete, can_restore,
     can_print, can_export, can_import, can_approve, can_cancel, can_lock, can_unlock)
SELECT roleid, target.screenname, source.can_view, source.can_add, source.can_edit,
       source.can_delete, source.can_restore, source.can_print, source.can_export,
       source.can_import, source.can_approve, source.can_cancel, source.can_lock, source.can_unlock
FROM role_permissions source
CROSS JOIN (VALUES
    ('Chart of Accounts'),
    ('Journal Voucher'),
    ('Account Ledger'),
    ('Period Lock'),
    ('Bank Reconciliation')
) AS target(screenname)
WHERE source.screenname = 'Payment'
ON CONFLICT (roleid, screenname) DO NOTHING;

COMMIT;
