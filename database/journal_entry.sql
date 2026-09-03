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