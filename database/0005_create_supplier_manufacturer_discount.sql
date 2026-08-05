-- =============================================================================
-- Migration: 0005_create_supplier_manufacturer_discount.sql
-- Module   : Supplier-Manufacturer Discount
-- Depends  : 0002_create_supplier.sql, 0003_create_manufacturer.sql
--
-- Purpose: Per (Supplier, Manufacturer) discount % mapping. Consumed by
-- engines/supplier_manufacturer_discount_engine.py's get_discount(), which
-- the future Purchase Engine will call to auto-apply a supplier's agreed
-- discount for a given manufacturer's items on a Purchase entry.
--
-- Idempotent (safe to run more than once), wrapped in a transaction so it
-- either fully applies or not at all. Additive only -- no destructive
-- ALTER/DROP, per project rule.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS supplier_manufacturer_discount (
    id                    SERIAL PRIMARY KEY,

    supplier_id            INTEGER        NOT NULL REFERENCES supplier(supplier_id),
    manufacturer_id        INTEGER        NOT NULL REFERENCES manufacturer(manufacturer_id),

    discount_percent        NUMERIC(5, 2) NOT NULL DEFAULT 0,
    remarks                  TEXT,

    is_deleted                BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_by                INTEGER,
    deleted_at_ad               TIMESTAMPTZ,
    deleted_at_bs                VARCHAR(10),

    created_by                  INTEGER   NOT NULL,
    created_at_ad                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at_bs                  VARCHAR(10) NOT NULL,

    updated_by                     INTEGER,
    updated_at_ad                    TIMESTAMPTZ,
    updated_at_bs                     VARCHAR(10),

    CONSTRAINT chk_supmfg_discount_percent CHECK (discount_percent >= 0 AND discount_percent <= 100)
);

-- (supplier_id, manufacturer_id) unique only among non-deleted rows, so a
-- deleted mapping can be recreated later without a permanent collision.
CREATE UNIQUE INDEX IF NOT EXISTS uq_supmfg_discount_pair_active
    ON supplier_manufacturer_discount (supplier_id, manufacturer_id)
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_supmfg_discount_supplier
    ON supplier_manufacturer_discount (supplier_id) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_supmfg_discount_manufacturer
    ON supplier_manufacturer_discount (manufacturer_id) WHERE is_deleted = FALSE;

COMMENT ON TABLE supplier_manufacturer_discount IS 'Supplier-Manufacturer Discount Master - Medical ERP V2. Soft-delete only, BS-first audit trail. One discount_percent per (supplier, manufacturer) pair. Consumed by SupplierManufacturerDiscountEngine.get_discount() -- intended for the future Purchase Engine.';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'migration_history'
    ) THEN
        INSERT INTO migration_history (migration_name, applied_at)
        VALUES ('0005_create_supplier_manufacturer_discount', now())
        ON CONFLICT (migration_name) DO NOTHING;
    END IF;
END $$;

COMMIT;