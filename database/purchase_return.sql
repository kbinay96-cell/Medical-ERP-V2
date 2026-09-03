CREATE TABLE IF NOT EXISTS purchase_return (
    purchase_return_id      SERIAL PRIMARY KEY,
    return_number              VARCHAR(30) NOT NULL UNIQUE,     -- e.g. PRTN-0001
    purchase_invoice_id           INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),
    supplier_id                     INTEGER NOT NULL REFERENCES supplier(supplier_id),   -- snapshot from invoice
    return_date_ad                   DATE NOT NULL,
    return_date_bs                     VARCHAR(10) NOT NULL,
    return_reason                        TEXT NOT NULL,             -- WHY goods are going back (damaged/expired/wrong item/quality issue)
    settlement_mode                        VARCHAR(30) NOT NULL DEFAULT 'Adjust Against Payable',
    total_qty                                NUMERIC(12,2) NOT NULL DEFAULT 0,   -- sum of returned PAID qty across lines
    total_free_qty                             NUMERIC(12,2) NOT NULL DEFAULT 0,   -- sum of returned FREE qty across lines
    total_gross_amount                           NUMERIC(14,2) NOT NULL DEFAULT 0,   -- sum(return_qty * rate) before discount, free qty contributes 0 value
    total_discount_amount                          NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cc_amount                                  NUMERIC(14,2) NOT NULL DEFAULT 0,   -- reversed customs charge on returned free qty
    grand_total                                        NUMERIC(14,2) NOT NULL DEFAULT 0,   -- gross - discount + cc
    status                                                VARCHAR(20) NOT NULL DEFAULT 'Posted',
    cancellation_reason                                    TEXT,        -- mandatory only when status='Cancelled'; enforced in Validator, not a DB CHECK
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

    CONSTRAINT chk_purchase_return_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_purchase_return_settlement_mode CHECK (settlement_mode IN ('Adjust Against Payable', 'Supplier Advance', 'Cash Refund'))
);

CREATE INDEX IF NOT EXISTS idx_purchase_return_invoice ON purchase_return (purchase_invoice_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_purchase_return_supplier ON purchase_return (supplier_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_purchase_return_date ON purchase_return (return_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_purchase_return_status ON purchase_return (status) WHERE is_deleted = FALSE;

COMMENT ON COLUMN purchase_return.settlement_mode IS 'How the returned value is settled with the supplier: Adjust Against Payable (reduces what we owe this supplier, default), Supplier Advance (added to our credit balance with this supplier, usable on a future purchase), Cash Refund (supplier hands cash back now). Drives future Accounts-module journal posting; not journaled yet as Accounts is a separate blueprint.';
COMMENT ON COLUMN purchase_return.cancellation_reason IS 'Required by the Validator whenever status is set to Cancelled. Cancelling a Posted return never deletes it or its stock effect -- a reversing stock movement is posted instead, preserving full history.';