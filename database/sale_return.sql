CREATE TABLE IF NOT EXISTS sale_return (
    sale_return_id          SERIAL PRIMARY KEY,
    return_number             VARCHAR(30) NOT NULL UNIQUE,     -- e.g. SRTN-0001
    sale_invoice_id             INTEGER NOT NULL REFERENCES sale_invoice(sale_invoice_id),
    customer_id                   INTEGER NOT NULL REFERENCES customers(customer_id),   -- snapshot from invoice (kept even if customer master changes)
    return_date_ad                  DATE NOT NULL,
    return_date_bs                    VARCHAR(10) NOT NULL,
    return_reason                       TEXT NOT NULL,             -- WHY the customer is returning (damaged/expired/wrong item/excess supply, etc.) -- separate from cancellation_reason below
    refund_mode                           VARCHAR(30) NOT NULL DEFAULT 'Adjust Against Invoice',
    total_qty                               NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_gross_amount                        NUMERIC(14,2) NOT NULL DEFAULT 0,   -- sum(return_qty * rate) before discount
    total_discount_amount                       NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cc_amount                               NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_tax_amount                                NUMERIC(14,2) NOT NULL DEFAULT 0,
    round_off                                         NUMERIC(8,2) NOT NULL DEFAULT 0,
    grand_total                                         NUMERIC(14,2) NOT NULL DEFAULT 0,   -- gross - discount + cc + tax + round_off
    status                                                VARCHAR(20) NOT NULL DEFAULT 'Posted',
    cancellation_reason                                    TEXT,        -- mandatory only when status='Cancelled', enforced in Engine/Validator, not DB CHECK (keeps the column simple; Validator owns the rule)
    remarks                                                  TEXT,
    is_deleted                                                BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                                  INTEGER NOT NULL,
    created_at_ad                                                TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                                 VARCHAR(10) NOT NULL,
    updated_by                                                      INTEGER,
    updated_at_ad                                                    TIMESTAMP,
    updated_at_bs                                                     VARCHAR(10),
    deleted_by                                                          INTEGER,
    deleted_at_ad                                                        TIMESTAMP,
    deleted_at_bs                                                         VARCHAR(10),

    CONSTRAINT chk_sale_return_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_sale_return_refund_mode CHECK (refund_mode IN ('Adjust Against Invoice', 'Advance', 'Cash Refund'))
);

CREATE INDEX IF NOT EXISTS idx_sale_return_invoice ON sale_return (sale_invoice_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_return_customer ON sale_return (customer_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_return_date ON sale_return (return_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_return_status ON sale_return (status) WHERE is_deleted = FALSE;

COMMENT ON COLUMN sale_return.refund_mode IS 'How the returned value is settled: Adjust Against Invoice (reduces this invoice''s own outstanding, default), Advance (added to customer credit balance, usable on any future invoice), Cash Refund (physical cash given back now). Drives future Accounts-module journal posting; not journaled yet as Accounts is a separate blueprint.';
COMMENT ON COLUMN sale_return.cancellation_reason IS 'Required by the Validator whenever status is set to Cancelled. Cancelling a Posted return never deletes it or its stock effect -- a reversing stock movement is posted instead (see 1.2 comment), preserving full history.';