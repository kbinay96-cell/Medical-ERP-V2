-- =============================================================================
-- Migration: 0013_item_free_scheme.sql
-- Module   : Purchase Invoice - Item Free-Qty Scheme (per item+supplier pair)
-- =============================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS item_free_scheme (
    item_free_scheme_id   SERIAL PRIMARY KEY,
    item_id               INTEGER NOT NULL REFERENCES item(item_id),
    supplier_id           INTEGER NOT NULL REFERENCES supplier(supplier_id),
    scheme_qty            NUMERIC(12,2) NOT NULL,
    scheme_free_qty       NUMERIC(12,2) NOT NULL,
    updated_by            INTEGER,
    updated_at_ad         TIMESTAMPTZ DEFAULT NOW(),
    updated_at_bs         VARCHAR(10),

    CONSTRAINT uq_item_free_scheme_item_supplier UNIQUE (item_id, supplier_id)
);

COMMENT ON TABLE item_free_scheme IS 'Lightweight, always-current free-qty scheme suggestion per (item_id, supplier_id) pair -- upserted on every Purchase Invoice save, not an audited record.';

COMMIT;