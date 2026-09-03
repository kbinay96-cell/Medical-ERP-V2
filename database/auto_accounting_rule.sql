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