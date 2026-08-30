CREATE TABLE IF NOT EXISTS sale_return_item (
    sale_return_item_id      SERIAL PRIMARY KEY,
    sale_return_id              INTEGER NOT NULL REFERENCES sale_return(sale_return_id),
    sale_invoice_item_id          INTEGER NOT NULL REFERENCES sale_invoice_item(sale_invoice_item_id),  -- the EXACT original line -- source of truth for the cumulative-qty check
    item_id                          INTEGER NOT NULL REFERENCES item(item_id),
    item_batch_id                      INTEGER NOT NULL REFERENCES item_batch(item_batch_id),   -- copied from sale_invoice_item -- read-only, same batch stock re-enters
    batch_no                             VARCHAR(50) NOT NULL,     -- snapshot
    expiry_month                           SMALLINT NOT NULL,        -- snapshot
    expiry_year                              SMALLINT NOT NULL,        -- snapshot
    return_qty                                 NUMERIC(12,2) NOT NULL,   -- the ONLY field the user manually types; validated against remaining returnable qty in the Engine
    rate                                          NUMERIC(12,2) NOT NULL,   -- copied read-only from sale_invoice_item.rate -- never re-entered
    discount_percent                                NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only from original line
    discount_amount                                   NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty-proportional share of the original line's discount
    cc_percent                                          NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only, Wholesale invoices only
    cc_amount                                             NUMERIC(12,2) NOT NULL DEFAULT 0,   -- proportional reversal -- only applies if the returned units include a CC-bearing free-goods link; ordinarily 0 since free_qty itself is never returned
    tax_percent                                             NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only
    tax_amount                                                NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty-proportional share
    amount                                                       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty * rate - discount_amount
    remarks                                                        TEXT,

    CONSTRAINT chk_sale_return_item_qty CHECK (return_qty > 0)
);

CREATE INDEX IF NOT EXISTS idx_sale_return_item_return ON sale_return_item (sale_return_id);
CREATE INDEX IF NOT EXISTS idx_sale_return_item_invoice_item ON sale_return_item (sale_invoice_item_id);
CREATE INDEX IF NOT EXISTS idx_sale_return_item_batch ON sale_return_item (item_batch_id);

COMMENT ON COLUMN sale_return_item.sale_invoice_item_id IS 'The single source of truth for validation: SUM(return_qty) across ALL non-cancelled sale_return_item rows referencing the same sale_invoice_item_id must never exceed that line''s original sale_invoice_item.qty. Enforced in sale_return_validator.py, not the DB, since it is a cross-row aggregate rule.';
COMMENT ON COLUMN sale_return_item.rate IS 'Always copied from the original sale_invoice_item.rate at return time and never independently editable -- guarantees the return value can never diverge from what was actually billed.';
