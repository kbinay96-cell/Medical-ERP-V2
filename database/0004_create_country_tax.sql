-- =============================================================================
-- Migration: 0004_create_country_tax.sql
-- Module   : Country Tax Settings
-- Depends  : 0001_* (auth/calendar), schema_auth.sql (settings table pattern)
--
-- Purpose: Country -> (VAT %, Custom %) lookup table. Consumed today by
-- engines/country_tax_engine.py's get_tax_for_country(), which
-- engines/item_lookup_registry.py's country_tax_lookup() will eventually
-- wire in to replace its current "(0, 0) placeholder" TODO. Also consumed
-- directly by the future Purchase Engine.
--
-- Idempotent (safe to run more than once), wrapped in a transaction so it
-- either fully applies or not at all. Additive only -- no destructive
-- ALTER/DROP, per project rule.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS country_tax (
    country_tax_id      SERIAL PRIMARY KEY,

    country              VARCHAR(100)    NOT NULL,
    vat_percent           NUMERIC(5, 2)  NOT NULL DEFAULT 0,
    custom_percent        NUMERIC(5, 2)  NOT NULL DEFAULT 0,
    remarks               TEXT,

    status                VARCHAR(10)    NOT NULL DEFAULT 'Active',

    is_deleted             BOOLEAN       NOT NULL DEFAULT FALSE,
    deleted_by             INTEGER,
    deleted_at_ad           TIMESTAMPTZ,
    deleted_at_bs            VARCHAR(10),

    created_by              INTEGER      NOT NULL,
    created_at_ad            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at_bs             VARCHAR(10) NOT NULL,

    updated_by                INTEGER,
    updated_at_ad               TIMESTAMPTZ,
    updated_at_bs                VARCHAR(10),

    CONSTRAINT chk_country_tax_status CHECK (status IN ('Active', 'Inactive')),
    CONSTRAINT chk_country_tax_vat_percent CHECK (vat_percent >= 0),
    CONSTRAINT chk_country_tax_custom_percent CHECK (custom_percent >= 0)
);

-- Uniqueness enforced only among non-deleted rows (case-insensitive on
-- country name), same "reusable after soft-delete" rule as every other
-- master table in this project.
CREATE UNIQUE INDEX IF NOT EXISTS uq_country_tax_country_active
    ON country_tax (LOWER(country))
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_country_tax_status ON country_tax (status) WHERE is_deleted = FALSE;

COMMENT ON TABLE country_tax IS 'Country Tax Settings - Medical ERP V2. Soft-delete only, BS-first audit trail. Consumed by CountryTaxEngine.get_tax_for_country() for Item Master''s country_default tax mode and by the future Purchase Engine.';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'migration_history'
    ) THEN
        INSERT INTO migration_history (migration_name, applied_at)
        VALUES ('0004_create_country_tax', now())
        ON CONFLICT (migration_name) DO NOTHING;
    END IF;
END $$;

COMMIT;