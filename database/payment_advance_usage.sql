CREATE TABLE IF NOT EXISTS payment_advance_usage (
    payment_advance_usage_id  SERIAL PRIMARY KEY,
    payment_id                   INTEGER NOT NULL REFERENCES payment(payment_id),
    purchase_invoice_id             INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),   -- the NEW invoice this advance was applied to
    used_amount                       NUMERIC(14,2) NOT NULL,
    used_by                             INTEGER NOT NULL,
    used_at_ad                           TIMESTAMP NOT NULL DEFAULT NOW(),
    used_at_bs                            VARCHAR(10) NOT NULL,

    CONSTRAINT chk_payment_advance_usage_positive CHECK (used_amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_payment_advance_usage_payment ON payment_advance_usage (payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_advance_usage_invoice ON payment_advance_usage (purchase_invoice_id);

COMMENT ON TABLE payment_advance_usage IS 'A payment''s remaining usable advance = payment.advance_amount - SUM(used_amount) across its usage rows. Append-only, same reasoning as receipt_advance_usage.';