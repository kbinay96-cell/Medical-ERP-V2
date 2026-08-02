-- =============================================================================
-- Medical ERP V2 - Simple Lookup Masters Foundation
-- File: database/schema_simple_masters.sql
-- Purpose: Shared schema for the five GENERIC lookup masters that Item
--          Master (and other future modules) depend on:
--              Category, Sub Category, Item Group, Unit, Generic
--
-- Design notes (read before altering):
--   * Manufacturer is DELIBERATELY EXCLUDED from this file. Manufacturer has
--     its own business rules (Country, auto short-name generation, Settings-
--     driven code prefix, future VAT/Custom tax integration) and lives in
--     its own dedicated schema/model/engine -- never folded into this
--     generic table shape.
--   * All five tables here share IDENTICAL structure and lifecycle rules on
--     purpose -- this is what lets models/simple_master_model.py and
--     engines/simple_master_engine.py be ONE reusable, table-agnostic
--     Model/Engine pair (config-driven by table name) instead of five
--     near-duplicate files. Do not add a table-specific column to any one
--     of these tables without adding it to all five, or the generic layer
--     breaks its own "same shape" assumption.
--   * BS-FIRST AUDIT RULE (same as supplier/company): every audit event
--     stores BOTH the AD instant (timestamptz, authoritative for
--     sorting/calc) and the BS display string (varchar 'YYYY-MM-DD'),
--     produced by the centralized Date Engine. No column here computes
--     BS itself.
--   * SOFT DELETE ONLY: no DELETE FROM anywhere in the application layer.
--     is_deleted + deleted_* columns model the lifecycle, exactly like
--     supplier/company.
--   * Uniqueness (Code and Name) is enforced only among NON-deleted rows,
--     case-insensitive, via PARTIAL UNIQUE INDEXES -- so a deleted row's
--     code/name can be reused by a brand-new row later, same rule as
--     supplier_code/supplier_name in schema_supplier.sql.
--   * SUB CATEGORY is the one table here that is SCOPED: every sub_category
--     row belongs to exactly one category_id (NOT NULL, FK). Its uniqueness
--     is scoped too -- the same Sub Category name is blocked twice within
--     the SAME Category, but is free to reuse under a DIFFERENT Category.
-- =============================================================================


-- =============================================================================
-- CATEGORY
-- =============================================================================
CREATE TABLE IF NOT EXISTS category (
    category_id         SERIAL PRIMARY KEY,

    code                 VARCHAR(20)     NOT NULL,
    name                 VARCHAR(100)    NOT NULL,
    status               VARCHAR(10)     NOT NULL DEFAULT 'Active',
    remarks              TEXT,

    is_deleted           BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_by           INTEGER,
    deleted_at_ad        TIMESTAMPTZ,
    deleted_at_bs        VARCHAR(10),

    created_by           INTEGER         NOT NULL,
    created_at_ad        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at_bs        VARCHAR(10)     NOT NULL,

    updated_by           INTEGER,
    updated_at_ad        TIMESTAMPTZ,
    updated_at_bs        VARCHAR(10),

    CONSTRAINT chk_category_status CHECK (status IN ('Active', 'Inactive'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_category_name_active
    ON category (LOWER(name)) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_category_code_active
    ON category (LOWER(code)) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_category_status ON category (status) WHERE is_deleted = FALSE;

COMMENT ON TABLE category IS 'Item Category lookup master - Medical ERP V2. Soft-delete only, BS-first audit trail.';


-- =============================================================================
-- SUB CATEGORY (scoped by category_id)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sub_category (
    sub_category_id      SERIAL PRIMARY KEY,

    category_id          INTEGER         NOT NULL REFERENCES category(category_id),

    code                 VARCHAR(20)     NOT NULL,
    name                 VARCHAR(100)    NOT NULL,
    status               VARCHAR(10)     NOT NULL DEFAULT 'Active',
    remarks              TEXT,

    is_deleted           BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_by           INTEGER,
    deleted_at_ad        TIMESTAMPTZ,
    deleted_at_bs        VARCHAR(10),

    created_by           INTEGER         NOT NULL,
    created_at_ad        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at_bs        VARCHAR(10)     NOT NULL,

    updated_by           INTEGER,
    updated_at_ad        TIMESTAMPTZ,
    updated_at_bs        VARCHAR(10),

    CONSTRAINT chk_sub_category_status CHECK (status IN ('Active', 'Inactive'))
);

-- Uniqueness is SCOPED to category_id -- same name allowed under a
-- different parent Category, per the design notes above.
CREATE UNIQUE INDEX IF NOT EXISTS uq_sub_category_name_active
    ON sub_category (category_id, LOWER(name)) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_sub_category_code_active
    ON sub_category (category_id, LOWER(code)) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_sub_category_parent
    ON sub_category (category_id) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_sub_category_status ON sub_category (status) WHERE is_deleted = FALSE;

COMMENT ON TABLE sub_category IS 'Item Sub-Category lookup master, scoped by category_id - Medical ERP V2. Soft-delete only, BS-first audit trail.';


-- =============================================================================
-- ITEM GROUP  (a.k.a. Item Type - Medicine, Surgical, Equipment, Consumable,
-- Cosmetic, Veterinary, Service, Allopathic, ...)
-- =============================================================================
CREATE TABLE IF NOT EXISTS item_group (
    item_group_id        SERIAL PRIMARY KEY,

    code                 VARCHAR(20)     NOT NULL,
    name                 VARCHAR(100)    NOT NULL,
    status               VARCHAR(10)     NOT NULL DEFAULT 'Active',
    remarks              TEXT,

    is_deleted           BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_by           INTEGER,
    deleted_at_ad        TIMESTAMPTZ,
    deleted_at_bs        VARCHAR(10),

    created_by           INTEGER         NOT NULL,
    created_at_ad        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at_bs        VARCHAR(10)     NOT NULL,

    updated_by           INTEGER,
    updated_at_ad        TIMESTAMPTZ,
    updated_at_bs        VARCHAR(10),

    CONSTRAINT chk_item_group_status CHECK (status IN ('Active', 'Inactive'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_item_group_name_active
    ON item_group (LOWER(name)) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_item_group_code_active
    ON item_group (LOWER(code)) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_item_group_status ON item_group (status) WHERE is_deleted = FALSE;

COMMENT ON TABLE item_group IS 'Item Group / Item Type lookup master - Medical ERP V2. Soft-delete only, BS-first audit trail.';


-- =============================================================================
-- UNIT  (Tablet, Strip, Box, Bottle, Vial, Piece, ...)
-- =============================================================================
CREATE TABLE IF NOT EXISTS unit (
    unit_id              SERIAL PRIMARY KEY,

    code                 VARCHAR(20)     NOT NULL,
    name                 VARCHAR(100)    NOT NULL,
    status               VARCHAR(10)     NOT NULL DEFAULT 'Active',
    remarks              TEXT,

    is_deleted           BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_by           INTEGER,
    deleted_at_ad        TIMESTAMPTZ,
    deleted_at_bs        VARCHAR(10),

    created_by           INTEGER         NOT NULL,
    created_at_ad        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at_bs        VARCHAR(10)     NOT NULL,

    updated_by           INTEGER,
    updated_at_ad        TIMESTAMPTZ,
    updated_at_bs        VARCHAR(10),

    CONSTRAINT chk_unit_status CHECK (status IN ('Active', 'Inactive'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_unit_name_active
    ON unit (LOWER(name)) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_unit_code_active
    ON unit (LOWER(code)) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_unit_status ON unit (status) WHERE is_deleted = FALSE;

COMMENT ON TABLE unit IS 'Unit of Measure lookup master - Medical ERP V2. Soft-delete only, BS-first audit trail. Used for both Unit and Purchase Unit selectors on Item Master.';


-- =============================================================================
-- GENERIC  (the generic/chemical name of a medicine, e.g. Paracetamol)
-- =============================================================================
CREATE TABLE IF NOT EXISTS generic (
    generic_id           SERIAL PRIMARY KEY,

    code                 VARCHAR(20)     NOT NULL,
    name                 VARCHAR(150)    NOT NULL,
    status               VARCHAR(10)     NOT NULL DEFAULT 'Active',
    remarks              TEXT,

    is_deleted           BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_by           INTEGER,
    deleted_at_ad        TIMESTAMPTZ,
    deleted_at_bs        VARCHAR(10),

    created_by           INTEGER         NOT NULL,
    created_at_ad        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at_bs        VARCHAR(10)     NOT NULL,

    updated_by           INTEGER,
    updated_at_ad        TIMESTAMPTZ,
    updated_at_bs        VARCHAR(10),

    CONSTRAINT chk_generic_status CHECK (status IN ('Active', 'Inactive'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_generic_name_active
    ON generic (LOWER(name)) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_generic_code_active
    ON generic (LOWER(code)) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_generic_status ON generic (status) WHERE is_deleted = FALSE;

COMMENT ON TABLE generic IS 'Generic/Chemical Name lookup master - Medical ERP V2. Soft-delete only, BS-first audit trail.';
