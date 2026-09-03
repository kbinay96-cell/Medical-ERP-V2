CREATE TABLE IF NOT EXISTS receipt (
    receipt_id               SERIAL PRIMARY KEY,
    receipt_number             VARCHAR(30) NOT NULL UNIQUE,     -- e.g. RCPT-0001
    customer_id                  INTEGER NOT NULL REFERENCES customer(customer_id),
    receipt_date_ad                DATE NOT NULL,
    receipt_date_bs                  VARCHAR(10) NOT NULL,
    payment_mode                       VARCHAR(30) NOT NULL,      -- Cash, Bank Transfer, Cheque, Card, Other
    amount                                NUMERIC(14,2) NOT NULL,    -- total amount received -- the ONLY manually entered money figure
    allocated_amount                       NUMERIC(14,2) NOT NULL DEFAULT 0,  -- SUM of receipt_allocation.allocated_amount for this receipt -- maintained by the Engine, not user-entered
    advance_amount                           NUMERIC(14,2) NOT NULL DEFAULT 0,  -- amount - allocated_amount at creation time (see receipt_advance_usage for how much of it is later consumed)
    reference_no                               VARCHAR(50),                -- cheque number / bank transaction ref, nullable
    bank_name                                    VARCHAR(100),               -- nullable, relevant only for Bank Transfer/Cheque/Card
    status                                          VARCHAR(20) NOT NULL DEFAULT 'Posted',
    cancellation_reason                                TEXT,        -- mandatory only when status='Cancelled'
    remarks                                              TEXT,
    is_deleted                                            BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                              INTEGER NOT NULL,
    created_at_ad                                            TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                             VARCHAR(10) NOT NULL,
    updated_by                                                  INTEGER,
    updated_at_ad                                                TIMESTAMP,
    updated_at_bs                                                 VARCHAR(10),
    deleted_by                                                      INTEGER,
    deleted_at_ad                                                    TIMESTAMP,
    deleted_at_bs                                                     VARCHAR(10),

    CONSTRAINT chk_receipt_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_receipt_payment_mode CHECK (payment_mode IN ('Cash', 'Bank Transfer', 'Cheque', 'Card', 'Other')),
    CONSTRAINT chk_receipt_amount_positive CHECK (amount > 0),
    CONSTRAINT chk_receipt_allocation_not_exceed CHECK (allocated_amount + advance_amount <= amount)
);

CREATE INDEX IF NOT EXISTS idx_receipt_customer ON receipt (customer_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_receipt_date ON receipt (receipt_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_receipt_status ON receipt (status) WHERE is_deleted = FALSE;

COMMENT ON COLUMN receipt.advance_amount IS 'The portion of this receipt left unallocated at creation time (amount - allocated_amount). Consumed over time as future invoices are created -- see receipt_advance_usage for how much of THIS receipt''s advance has been used and how much remains.';
COMMENT ON COLUMN receipt.cancellation_reason IS 'Required by the Validator whenever status is set to Cancelled. Cancelling reverses this receipt''s effect on customer outstanding (its allocations stop counting) via status change alone -- receipt_allocation rows are never deleted, only ignored by every query once the parent is Cancelled.';