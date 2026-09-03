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