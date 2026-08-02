-- =============================================================================
-- Medical ERP V2 - Manufacturer Master Module
-- File: database/schema_manufacturer.sql
-- Purpose: Full schema for the `manufacturer` table (reusable lookup master
-- consumed by Item Master, Purchase, Sales, Reports, Barcode, Analytics).
--
-- Design notes (read before altering):
--   * BS-FIRST RULE: every audit timestamp stores BOTH the AD instant
--     (timestamptz, authoritative) and the BS display string (varchar,
--     'YYYY-MM-DD'), produced by the centralized Date Engine. No column
--     here computes BS itself.
--   * SOFT DELETE ONLY: there is no DELETE FROM manufacturer anywhere in
--     the application. is_deleted + deleted_* columns model the lifecycle.
--   * Manufacturer Name and Manufacturer Code must be unique only among
--     NON-deleted rows (partial unique indexes), so a deleted manufacturer's
--     name/code can be reused later.
--   * manufacturer_short_name is ALWAYS engine-generated (first word of the
--     name, de-duplicated as Sun / Sun1 / Sun2 ...). It is never entered
--     directly on the form. The partial unique index below is a DB-level
--     integrity backstop for that Engine rule, not a user-facing constraint.
-- =============================================================================

CREATE TABLE IF NOT EXISTS manufacturer (
    manufacturer_id          SERIAL PRIMARY KEY,

    manufacturer_code        VARCHAR(20)     NOT NULL,
    manufacturer_name        VARCHAR(150)    NOT NULL,
    manufacturer_short_name  VARCHAR(50)     NOT NULL,
    country                  VARCHAR(100),

    status                   VARCHAR(10)     NOT NULL DEFAULT 'Active',

    -- Soft delete lifecycle
    is_deleted                BOOLEAN        NOT NULL DEFAULT FALSE,
    deleted_by                INTEGER,
    deleted_at_ad              TIMESTAMPTZ,
    deleted_at_bs               VARCHAR(10),

    -- Audit trail (BS-first: BS display string + AD authoritative instant)
    created_by                INTEGER        NOT NULL,
    created_at_ad              TIMESTAMPTZ    NOT NULL DEFAULT now(),
    created_at_bs               VARCHAR(10)    NOT NULL,

    updated_by                INTEGER,
    updated_at_ad               TIMESTAMPTZ,
    updated_at_bs                VARCHAR(10),

    CONSTRAINT chk_manufacturer_status CHECK (status IN ('Active', 'Inactive'))
);

-- Uniqueness enforced only among non-deleted rows (case-insensitive).
CREATE UNIQUE INDEX IF NOT EXISTS uq_manufacturer_name_active
    ON manufacturer (LOWER(manufacturer_name))
    WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_manufacturer_code_active
    ON manufacturer (LOWER(manufacturer_code))
    WHERE is_deleted = FALSE;

-- Backstop for the Engine's Sun/Sun1/Sun2 de-duplication rule.
CREATE UNIQUE INDEX IF NOT EXISTS uq_manufacturer_short_name_active
    ON manufacturer (LOWER(manufacturer_short_name))
    WHERE is_deleted = FALSE;

-- Search / filter support indexes
CREATE INDEX IF NOT EXISTS idx_manufacturer_status  ON manufacturer (status)  WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_manufacturer_country ON manufacturer (country) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_manufacturer_name     ON manufacturer (manufacturer_name) WHERE is_deleted = FALSE;

COMMENT ON TABLE manufacturer IS 'Manufacturer Master - Medical ERP V2. Soft-delete only, BS-first audit trail. Reusable lookup for Item Master, Purchase, Sales, Reports, Barcode, Analytics.';
COMMENT ON COLUMN manufacturer.manufacturer_short_name IS 'Engine-generated: first word of manufacturer_name, de-duplicated as Name / Name1 / Name2. Never user-entered.';

-- ---------------------------------------------------------
-- SETTINGS SEED: Manufacturer Code Prefix (Settings module
-- already owns the `settings` table - see schema_auth.sql -
-- this module only adds its own key, per the project's
-- "zero hardcoded values" philosophy, same pattern intended
-- for Supplier's supplier.code_prefix).
-- ---------------------------------------------------------
INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order) VALUES
    ('manufacturer.code_prefix', 'MFG-', 'Manufacturer', 'string', 'MFG-', 'Prefix used when auto-generating Manufacturer Codes (e.g. MFG-0001)', 10)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;
