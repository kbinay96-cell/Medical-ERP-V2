CREATE TABLE IF NOT EXISTS payment_audit_log (
    payment_audit_log_id      SERIAL PRIMARY KEY,
    payment_id                   INTEGER NOT NULL REFERENCES payment(payment_id),
    changed_field                   VARCHAR(100) NOT NULL,   -- e.g. 'amount', 'allocation:purchase_invoice_id=42'
    old_value                         TEXT,
    new_value                           TEXT,
    changed_by                           INTEGER NOT NULL,
    changed_at_ad                          TIMESTAMP NOT NULL DEFAULT NOW(),
    changed_at_bs                           VARCHAR(10) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payment_audit_log_payment ON payment_audit_log (payment_id);

COMMENT ON TABLE payment_audit_log IS 'Append-only, one row per changed field per edit -- identical design to receipt_audit_log, mirrored for the supplier side.';