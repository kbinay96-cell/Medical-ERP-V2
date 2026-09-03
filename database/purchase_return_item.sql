CREATE TABLE IF NOT EXISTS purchase_return_item (
    purchase_return_item_id  SERIAL PRIMARY KEY,
    purchase_return_id          INTEGER NOT NULL REFERENCES purchase_return(purchase_return_id),
    purchase_invoice_item_id       INTEGER NOT NULL REFERENCES purchase_invoice_item(purchase_invoice_item_id),  -- the EXACT original line -- source of truth for both cumulative-qty checks
    item_id                            INTEGER NOT NULL REFERENCES item(item_id),
    item_batch_id                        INTEGER NOT NULL REFERENCES item_batch(item_batch_id),   -- copied from purchase_invoice_item -- read-only, same batch stock leaves from
    batch_no                               VARCHAR(50) NOT NULL,     -- snapshot
    expiry_month                             SMALLINT NOT NULL,        -- snapshot
    expiry_year                                SMALLINT NOT NULL,        -- snapshot
    return_qty                                   NUMERIC(12,2) NOT NULL DEFAULT 0,   -- returned PAID quantity -- validated against remaining returnable paid qty
    return_free_qty                                NUMERIC(12,2) NOT NULL DEFAULT 0,   -- returned FREE quantity -- validated separately against remaining returnable free qty
    rate                                              NUMERIC(12,2) NOT NULL,   -- copied read-only from purchase_invoice_item.purchase_rate -- never re-entered
    discount_percent                                    NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only from original line
    discount_amount                                       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty-proportional share of the original line's discount (discount only ever applied to paid qty)
    cc_percent                                              NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only
    cc_amount                                                 NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_free_qty-proportional share of the original line's customs charge (cc was computed on free qty in Purchase Invoice)
    amount                                                       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty * rate - discount_amount (free qty always contributes 0 value, same as on the original invoice line)
    remarks                                                        TEXT,

    CONSTRAINT chk_purchase_return_item_qty CHECK (return_qty >= 0 AND return_free_qty >= 0),
    CONSTRAINT chk_purchase_return_item_qty_nonzero CHECK (return_qty > 0 OR return_free_qty > 0)
);

CREATE INDEX IF NOT EXISTS idx_purchase_return_item_return ON purchase_return_item (purchase_return_id);
CREATE INDEX IF NOT EXISTS idx_purchase_return_item_invoice_item ON purchase_return_item (purchase_invoice_item_id);
CREATE INDEX IF NOT EXISTS idx_purchase_return_item_batch ON purchase_return_item (item_batch_id);

COMMENT ON COLUMN purchase_return_item.purchase_invoice_item_id IS 'The single source of truth for validation: SUM(return_qty) across ALL non-cancelled purchase_return_item rows referencing the same purchase_invoice_item_id must never exceed that line''s original purchase_invoice_item.qty, and SUM(return_free_qty) must never exceed the original free_qty -- two independent cumulative checks. Enforced in purchase_return_validator.py, not the DB, since these are cross-row aggregate rules.';
COMMENT ON COLUMN purchase_return_item.rate IS 'Always copied from the original purchase_invoice_item.purchase_rate at return time and never independently editable.';