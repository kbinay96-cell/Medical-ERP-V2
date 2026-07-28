-- =============================================================================
-- Medical ERP V2 - Supplier Master Module
-- File: database/schema_supplier.sql
-- Purpose: Full schema definition for the `supplier` table.
--
-- Design notes (read before altering):
--   * BS-FIRST RULE: every audit timestamp stores BOTH the AD instant
--     (timestamptz, authoritative for sorting/calc) and the BS display
--     string (varchar, 'YYYY-MM-DD' in Bikram Sambat), produced by the
--     centralized Date Engine. No column here computes BS itself.
--   * SOFT DELETE ONLY: there is no DELETE FROM supplier anywhere in the
--     application. is_deleted + deleted_* columns model the lifecycle.
--   * Supplier Name and Supplier Code must be unique only among the
--     NON-deleted rows, so a deleted supplier's name/code can be reused
--     by a brand-new supplier later. This is implemented with PARTIAL
--     UNIQUE INDEXES (WHERE is_deleted = FALSE) rather than plain
--     UNIQUE constraints.
--   * companyid is nullable and unused today -> reserved for the future
--     Company Mapping feature (multi-company suppliers), per project
--     rules ("Future-ready for Company Mapping"). No FK enforcement yet
--     until the Company Mapping module defines the join table; kept as
--     a plain nullable integer column now so the column doesn't need a
--     backfill migration later.
-- =============================================================================

CREATE TABLE IF NOT EXISTS supplier (
    supplier_id         SERIAL PRIMARY KEY,

    supplier_code       VARCHAR(20)     NOT NULL,
    supplier_name       VARCHAR(150)    NOT NULL,

    contact_person      VARCHAR(100),
    mobile_no           VARCHAR(20),
    phone_no            VARCHAR(20),
    email               VARCHAR(150),
    address             VARCHAR(255),
    city                VARCHAR(100),
    pan_vat_no          VARCHAR(30),

    opening_balance     NUMERIC(18, 2)  NOT NULL DEFAULT 0,
    balance_type        VARCHAR(2)      NOT NULL DEFAULT 'Dr',
    credit_limit        NUMERIC(18, 2)  NOT NULL DEFAULT 0,
    credit_days         INTEGER         NOT NULL DEFAULT 0,

    status              VARCHAR(10)     NOT NULL DEFAULT 'Active',
    remarks             TEXT,

    -- Future-ready: Company Mapping (nullable, no FK yet -- see notes above)
    company_id          INTEGER,

    -- Soft delete lifecycle
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_by          INTEGER,
    deleted_at_ad       TIMESTAMPTZ,
    deleted_at_bs       VARCHAR(10),

    -- Audit trail (BS-first: BS display string + AD authoritative instant)
    created_by          INTEGER         NOT NULL,
    created_at_ad       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at_bs       VARCHAR(10)     NOT NULL,

    updated_by          INTEGER,
    updated_at_ad       TIMESTAMPTZ,
    updated_at_bs       VARCHAR(10),

    CONSTRAINT chk_supplier_balance_type CHECK (balance_type IN ('Dr', 'Cr')),
    CONSTRAINT chk_supplier_status       CHECK (status IN ('Active', 'Inactive')),
    CONSTRAINT chk_supplier_credit_days  CHECK (credit_days >= 0),
    CONSTRAINT chk_supplier_credit_limit CHECK (credit_limit >= 0),
    CONSTRAINT chk_supplier_opening_bal  CHECK (opening_balance >= 0)
);

-- Uniqueness enforced only among non-deleted rows (case-insensitive on name).
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_name_active
    ON supplier (LOWER(supplier_name))
    WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_code_active
    ON supplier (LOWER(supplier_code))
    WHERE is_deleted = FALSE;

-- Search / filter support indexes
CREATE INDEX IF NOT EXISTS idx_supplier_mobile      ON supplier (mobile_no) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_supplier_pan_vat      ON supplier (pan_vat_no) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_supplier_status       ON supplier (status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_supplier_name_trgm    ON supplier (supplier_name) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_supplier_company      ON supplier (company_id) WHERE is_deleted = FALSE;

COMMENT ON TABLE supplier IS 'Supplier Master - Medical ERP V2. Soft-delete only, BS-first audit trail.';
COMMENT ON COLUMN supplier.balance_type IS 'Dr = Debit, Cr = Credit. Default Dr.';
COMMENT ON COLUMN supplier.company_id IS 'Reserved for future Company Mapping module. No FK yet.';
