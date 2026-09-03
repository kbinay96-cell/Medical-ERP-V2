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