-- database/migrations/0008_purchase_invoice_enhancements.sql
-- Purchase Invoice enhancements: header-level bill discount, round-off,
-- and a reusable item+supplier "free scheme" (e.g. 10+1) lookup.
-- Additive only — no existing column/table is altered or dropped.

BEGIN;

-- 1. Header-level (whole-bill) discount — some suppliers discount the
--    whole invoice directly instead of per item. Applied straight on
--    grand_total, never allocated across lines.
ALTER TABLE purchase_invoice
    ADD COLUMN IF NOT EXISTS bill_discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bill_discount_amount  NUMERIC(14,2) NOT NULL DEFAULT 0;

-- 2. Round-off — difference between the raw calculated total and the
--    rounded total actually posted. Stored so it's auditable, not just
--    silently absorbed into grand_total.
ALTER TABLE purchase_invoice
    ADD COLUMN IF NOT EXISTS round_off_amount NUMERIC(8,2) NOT NULL DEFAULT 0;

-- 3. Item + Supplier "free scheme" memory (e.g. "10+1"). One active
--    scheme per (item, supplier) — overwritten whenever the user enters
--    a different ratio on a new invoice, so the next entry auto-suggests
--    the latest known scheme. Reusable by the future Sale module too,
--    since the scheme belongs to the item+supplier pair, not to any one
--    transaction.
CREATE TABLE IF NOT EXISTS item_free_scheme (
    item_free_scheme_id   SERIAL PRIMARY KEY,
    item_id               INTEGER NOT NULL REFERENCES item(item_id),
    supplier_id           INTEGER NOT NULL REFERENCES supplier(supplier_id),
    scheme_qty            NUMERIC(12,2) NOT NULL,
    scheme_free_qty       NUMERIC(12,2) NOT NULL,
    updated_by            INTEGER NOT NULL,
    updated_at_ad         TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at_bs         VARCHAR(10)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_item_free_scheme_item_supplier
    ON item_free_scheme (item_id, supplier_id);

COMMIT;