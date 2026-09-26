CREATE TABLE IF NOT EXISTS payment_opening_balance_allocation (
    payment_opening_balance_allocation_id  SERIAL PRIMARY KEY,
    payment_id                                INTEGER NOT NULL REFERENCES payment(payment_id),
    supplier_id                                  INTEGER NOT NULL REFERENCES supplier(supplier_id),
    allocated_amount                                NUMERIC(14,2) NOT NULL,
    created_by                                        INTEGER NOT NULL,
    created_at_ad                                       TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                         VARCHAR(10) NOT NULL,

    CONSTRAINT chk_payment_ob_allocation_positive CHECK (allocated_amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_payment_ob_allocation_payment ON payment_opening_balance_allocation (payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_ob_allocation_supplier ON payment_opening_balance_allocation (supplier_id);

COMMENT ON TABLE payment_opening_balance_allocation IS 'A supplier''s remaining unpaid Cr-type opening balance = supplier.opening_balance - SUM(allocated_amount) across its allocation rows (restricted to non-Cancelled, non-deleted payments). Append-only, same reasoning as payment_advance_usage.';

COMMENT ON COLUMN payment.advance_amount IS 'The portion of this payment left unallocated at creation time, after first settling the supplier''s Cr-type opening balance (see payment_opening_balance_allocation) and then Purchase Invoices (see payment_allocation). Consumed over time as future Purchase Invoices are created -- see payment_advance_usage.';