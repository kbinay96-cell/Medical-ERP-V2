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