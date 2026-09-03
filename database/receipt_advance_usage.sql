CREATE TABLE IF NOT EXISTS receipt_advance_usage (
    receipt_advance_usage_id  SERIAL PRIMARY KEY,
    receipt_id                   INTEGER NOT NULL REFERENCES receipt(receipt_id),   -- the receipt whose advance_amount is being drawn down
    sale_invoice_id                 INTEGER NOT NULL REFERENCES sale_invoice(sale_invoice_id),  -- the NEW invoice this advance was applied to
    used_amount                       NUMERIC(14,2) NOT NULL,
    used_by                             INTEGER NOT NULL,
    used_at_ad                           TIMESTAMP NOT NULL DEFAULT NOW(),
    used_at_bs                            VARCHAR(10) NOT NULL,

    CONSTRAINT chk_receipt_advance_usage_positive CHECK (used_amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_receipt_advance_usage_receipt ON receipt_advance_usage (receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_advance_usage_invoice ON receipt_advance_usage (sale_invoice_id);

COMMENT ON TABLE receipt_advance_usage IS 'A receipt''s remaining usable advance = receipt.advance_amount - SUM(used_amount) across its non-cancelled usage rows. Kept as its own append-only ledger (never edited/deleted, only added to) since it represents money already applied to a specific later invoice -- reversing it belongs to that invoice''s own cancellation/return flow, not this table.';