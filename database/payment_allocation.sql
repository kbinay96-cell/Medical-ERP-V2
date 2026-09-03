CREATE TABLE IF NOT EXISTS payment_allocation (
    payment_allocation_id    SERIAL PRIMARY KEY,
    payment_id                  INTEGER NOT NULL REFERENCES payment(payment_id),
    purchase_invoice_id            INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),
    allocated_amount                  NUMERIC(14,2) NOT NULL,
    is_auto_allocated                   BOOLEAN NOT NULL DEFAULT TRUE,   -- TRUE = FIFO engine matched it, FALSE = user manually re-targeted
    remarks                               TEXT,

    CONSTRAINT chk_payment_allocation_positive CHECK (allocated_amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_payment_allocation_payment ON payment_allocation (payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_allocation_invoice ON payment_allocation (purchase_invoice_id);

COMMENT ON COLUMN payment_allocation.purchase_invoice_id IS 'SUM(allocated_amount) across every payment_allocation row for a given purchase_invoice_id, restricted to payments with status != Cancelled, is the total amount ever paid toward that invoice. purchase_invoice.grand_total minus that sum (further reduced by any Purchase Return with settlement_mode=''Adjust Against Payable'') is that invoice''s live outstanding balance.';