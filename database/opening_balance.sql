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