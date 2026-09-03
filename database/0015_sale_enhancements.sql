-- =============================================================================
-- Migration: 0015_sale_enhancements.sql
-- Module   : Sale Module Enhancements (blueprint alignment)
-- Depends  : 0009_sale_schema.sql (sale_invoice, sale_invoice_item)
--
-- Creates  : sale_item_free_scheme (NEW, Sale-specific master)
-- Alters   : sale_invoice (rename + add columns per blueprint)
-- Seeds    : sale.column_show_* + sale.minimum_auto_free_qty settings
--
-- NOTE: Purchase module's item_free_scheme table is UNTOUCHED (Option A).
--       Sale gets its own separate sale_item_free_scheme table.
--
-- Additive only — no existing column/table is dropped.
-- =============================================================================
BEGIN;

-- =============================================================================
-- 1. NEW TABLE: sale_item_free_scheme (Sale-specific, per-item free scheme)
--    Blueprint design: ratio-based (scheme_qty + scheme_free), one active per item.
--    Completely separate from Purchase's item_free_scheme.
-- =============================================================================
CREATE TABLE IF NOT EXISTS sale_item_free_scheme (
    sale_item_free_scheme_id SERIAL PRIMARY KEY,
    item_id                  INTEGER NOT NULL REFERENCES item(item_id),
    scheme_qty               NUMERIC(12,2) NOT NULL,
    scheme_free              NUMERIC(12,2) NOT NULL,
    is_active                BOOLEAN NOT NULL DEFAULT TRUE,
    remarks                  TEXT,
    is_deleted               BOOLEAN NOT NULL DEFAULT FALSE,
    created_by               INTEGER NOT NULL,
    created_at_ad            TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs            VARCHAR(10) NOT NULL,
    updated_by               INTEGER,
    updated_at_ad            TIMESTAMP,
    updated_at_bs            VARCHAR(10),
    deleted_by               INTEGER,
    deleted_at_ad            TIMESTAMP,
    deleted_at_bs            VARCHAR(10),

    CONSTRAINT chk_sale_item_free_scheme_qty CHECK (scheme_qty > 0 AND scheme_free > 0)
);

CREATE INDEX IF NOT EXISTS idx_sale_item_free_scheme_item
    ON sale_item_free_scheme (item_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_item_free_scheme_active
    ON sale_item_free_scheme (item_id, is_active) WHERE is_deleted = FALSE AND is_active = TRUE;

COMMENT ON TABLE sale_item_free_scheme IS 'Sale-specific free-qty scheme master (e.g. 5+1). One active scheme per item. Separate from Purchase module''s item_free_scheme.';
COMMENT ON COLUMN sale_item_free_scheme.scheme_qty IS 'Paid units that must be bought to qualify for free units (the "X" in X+Y).';
COMMENT ON COLUMN sale_item_free_scheme.scheme_free IS 'Free units awarded when scheme_qty paid units are bought (the "Y" in X+Y).';

-- =============================================================================
-- 2. RENAME existing sale_invoice columns (blueprint naming)
-- =============================================================================
-- payment_mode (Cash/Credit/Partial) -> payment_type (Cash/Bank/eSewa/Khalti/IPS)
ALTER TABLE sale_invoice RENAME COLUMN payment_mode TO payment_type;

-- round_off_amount -> round_off
ALTER TABLE sale_invoice RENAME COLUMN round_off_amount TO round_off;

-- paid_amount -> amount_paid_now (snapshot of what was settled at invoice time)
ALTER TABLE sale_invoice RENAME COLUMN paid_amount TO amount_paid_now;

-- =============================================================================
-- 3. DROP old CHECK constraints on renamed columns, ADD new ones
-- =============================================================================
-- Drop old payment_type constraint (was chk_sale_invoice_payment_mode on payment_mode)
ALTER TABLE sale_invoice DROP CONSTRAINT IF EXISTS chk_sale_invoice_payment_mode;

-- Add new constraint for payment_type (Cash/Bank/eSewa/Khalti/IPS)
ALTER TABLE sale_invoice
    ADD CONSTRAINT chk_sale_invoice_payment_type
    CHECK (payment_type IN ('Cash', 'Bank', 'eSewa', 'Khalti', 'IPS'));

-- =============================================================================
-- 4. ADD new columns to sale_invoice (blueprint)
-- =============================================================================
ALTER TABLE sale_invoice
    ADD COLUMN IF NOT EXISTS area_id        INTEGER REFERENCES areas(area_id),
    ADD COLUMN IF NOT EXISTS price_level_id INTEGER,
    ADD COLUMN IF NOT EXISTS sale_mode      VARCHAR(10) NOT NULL DEFAULT 'Retail',
    ADD COLUMN IF NOT EXISTS total_free_qty NUMERIC(12,2) NOT NULL DEFAULT 0;

-- Constraint for sale_mode
ALTER TABLE sale_invoice
    ADD CONSTRAINT chk_sale_invoice_sale_mode
    CHECK (sale_mode IN ('Retail', 'Wholesale'));

-- Index for area filtering
CREATE INDEX IF NOT EXISTS idx_sale_invoice_area
    ON sale_invoice (area_id) WHERE is_deleted = FALSE;

COMMENT ON COLUMN sale_invoice.area_id IS 'Customer area at invoice time — backs Area→Customer two-combo search.';
COMMENT ON COLUMN sale_invoice.price_level_id IS 'Customer price level snapshot at invoice time.';
COMMENT ON COLUMN sale_invoice.sale_mode IS 'Retail (free scheme OFF) vs Wholesale (free scheme + CC ON). Snapshotted per-invoice.';
COMMENT ON COLUMN sale_invoice.total_free_qty IS 'Sum of free_qty across all lines. Stock deducted = qty + free_qty.';
COMMENT ON COLUMN sale_invoice.amount_paid_now IS 'Amount settled at invoice time. Remaining balance tracked via Accounts module.';
COMMENT ON COLUMN sale_invoice.payment_type IS 'Payment method: Cash, Bank, eSewa, Khalti, IPS.';
COMMENT ON COLUMN sale_invoice.round_off IS 'Difference between raw total and rounded grand_total.';

-- =============================================================================
-- 5. SEED Sale settings (column visibility + free-scheme behaviour)
--    Idempotent — ON CONFLICT DO NOTHING.
-- =============================================================================
INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order)
VALUES
    -- Column visibility (compulsory columns — Item, Qty, Rate, Amount — are NOT here; they are always shown)
    ('sale.column_show_batch',            'true',  'Sale', 'boolean', 'true',  'Show Batch No. column on the Sale Invoice grid and print', 10),
    ('sale.column_show_expiry',           'true',  'Sale', 'boolean', 'true',  'Show Expiry column on the Sale Invoice grid and print', 20),
    ('sale.column_show_free',             'false', 'Sale', 'boolean', 'false', 'Show Free Qty column — ON = Wholesale mode (free scheme + CC apply), OFF = Retail mode (free scheme never applies)', 30),
    ('sale.column_show_mrp',              'true',  'Sale', 'boolean', 'true',  'Show MRP column on the Sale Invoice grid and print', 40),
    ('sale.column_show_discount_percent', 'true',  'Sale', 'boolean', 'true',  'Show Discount % column on the Sale Invoice grid and print', 50),
    ('sale.column_show_packing',          'true',  'Sale', 'boolean', 'true',  'Show Packing/Unit column on the Sale Invoice grid and print', 60),
    ('sale.column_show_tax',              'false', 'Sale', 'boolean', 'false', 'Show Tax % / Tax Amount columns on the Sale Invoice grid and print', 70),

    -- Free-scheme behaviour
    ('sale.allow_half_free',              'false', 'Sale', 'boolean', 'false', 'Allow proportional (fractional) free qty when the entered qty is not an exact multiple of the item''s free scheme, e.g. 2.5 of a 5+1 scheme -> 0.5 free', 80),
    ('sale.minimum_auto_free_qty',        '1',     'Sale', 'decimal', '1',     'Minimum computed free qty required before it is auto-filled on a line; below this the Free field is left at 0 for the user to set manually', 90)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;

COMMIT;


