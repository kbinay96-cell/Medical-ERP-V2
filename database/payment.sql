CREATE TABLE IF NOT EXISTS payment (
    payment_id                SERIAL PRIMARY KEY,
    payment_number               VARCHAR(30) NOT NULL UNIQUE,     -- e.g. PYMT-0001
    supplier_id                     INTEGER NOT NULL REFERENCES supplier(supplier_id),
    payment_date_ad                   DATE NOT NULL,
    payment_date_bs                     VARCHAR(10) NOT NULL,
    payment_mode                          VARCHAR(30) NOT NULL,      -- Cash, Bank Transfer, Cheque, Card, Other
    amount                                   NUMERIC(14,2) NOT NULL,    -- total amount paid -- the ONLY manually entered money figure
    allocated_amount                          NUMERIC(14,2) NOT NULL DEFAULT 0,  -- SUM of payment_allocation.allocated_amount -- Engine-maintained
    advance_amount                              NUMERIC(14,2) NOT NULL DEFAULT 0,  -- amount - allocated_amount at creation time
    reference_no                                  VARCHAR(50),                -- cheque number / bank transaction ref, nullable
    bank_name                                       VARCHAR(100),               -- nullable
    status                                             VARCHAR(20) NOT NULL DEFAULT 'Posted',
    cancellation_reason                                   TEXT,        -- mandatory only when status='Cancelled'
    remarks                                                 TEXT,
    is_deleted                                               BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                                 INTEGER NOT NULL,
    created_at_ad                                               TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                                VARCHAR(10) NOT NULL,
    updated_by                                                     INTEGER,
    updated_at_ad                                                   TIMESTAMP,
    updated_at_bs                                                    VARCHAR(10),
    deleted_by                                                         INTEGER,
    deleted_at_ad                                                       TIMESTAMP,
    deleted_at_bs                                                        VARCHAR(10),

    CONSTRAINT chk_payment_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_payment_payment_mode CHECK (payment_mode IN ('Cash', 'Bank Transfer', 'Cheque', 'Card', 'Other')),
    CONSTRAINT chk_payment_amount_positive CHECK (amount > 0),
    CONSTRAINT chk_payment_allocation_not_exceed CHECK (allocated_amount + advance_amount <= amount)
);

CREATE INDEX IF NOT EXISTS idx_payment_supplier ON payment (supplier_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_payment_date ON payment (payment_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_payment_status ON payment (status) WHERE is_deleted = FALSE;

COMMENT ON COLUMN payment.advance_amount IS 'The portion of this payment left unallocated at creation time. Consumed over time as future Purchase Invoices are created -- see payment_advance_usage.';
COMMENT ON COLUMN payment.cancellation_reason IS 'Required whenever status is set to Cancelled. Cancelling reverses this payment''s effect on supplier outstanding via status change alone -- payment_allocation rows are never deleted, only ignored once the parent is Cancelled.';