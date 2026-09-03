CREATE TABLE IF NOT EXISTS receipt_audit_log (
    receipt_audit_log_id      SERIAL PRIMARY KEY,
    receipt_id                   INTEGER NOT NULL REFERENCES receipt(receipt_id),
    changed_field                   VARCHAR(100) NOT NULL,   -- e.g. 'amount', 'payment_mode', 'allocation:sale_invoice_id=42'
    old_value                         TEXT,
    new_value                           TEXT,
    changed_by                           INTEGER NOT NULL,
    changed_at_ad                          TIMESTAMP NOT NULL DEFAULT NOW(),
    changed_at_bs                           VARCHAR(10) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_receipt_audit_log_receipt ON receipt_audit_log (receipt_id);

COMMENT ON TABLE receipt_audit_log IS 'Append-only, one row per changed field per edit -- this table is the confirmed alternative to a full reversal-voucher design: the Receipt itself stays a single editable record, but every change to it (header field or an allocation being re-targeted from one invoice to another) is captured here BEFORE the update is applied, so nothing is ever silently lost. Never edited or deleted itself.';