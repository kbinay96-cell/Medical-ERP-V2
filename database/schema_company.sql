-- =========================================================
-- Medical ERP V2
-- Company Master Schema (v2 - matches real DB structure)
-- ---------------------------------------------------------
-- The real `company` table (confirmed via \d company) has only:
--   companyid, companyname, country, status, createddate
-- It uses a TEXT `status` column ('Active'/'Inactive'), NOT
-- boolean isactive/isdeleted. `users.companyid` has a FK to
-- this table, so we only ADD columns here - never drop/rename
-- anything that already exists.
-- =========================================================

-- New fields needed by the Company Master form:
ALTER TABLE company ADD COLUMN IF NOT EXISTS address VARCHAR(255);
ALTER TABLE company ADD COLUMN IF NOT EXISTS contactperson VARCHAR(100);
ALTER TABLE company ADD COLUMN IF NOT EXISTS mobileno VARCHAR(20);
ALTER TABLE company ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE company ADD COLUMN IF NOT EXISTS email VARCHAR(100);
ALTER TABLE company ADD COLUMN IF NOT EXISTS panno VARCHAR(50);
ALTER TABLE company ADD COLUMN IF NOT EXISTS registrationno VARCHAR(50);
ALTER TABLE company ADD COLUMN IF NOT EXISTS remarks VARCHAR(500);

-- Soft delete: separate from `status` (Active/Inactive), per
-- Option A decision - deleting a company must not be confused
-- with deactivating one.
ALTER TABLE company ADD COLUMN IF NOT EXISTS isdeleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE company ADD COLUMN IF NOT EXISTS deletedby VARCHAR(50);
ALTER TABLE company ADD COLUMN IF NOT EXISTS deletedat TIMESTAMP;

-- Audit columns
ALTER TABLE company ADD COLUMN IF NOT EXISTS createdby VARCHAR(50);
ALTER TABLE company ADD COLUMN IF NOT EXISTS modifiedby VARCHAR(50);
ALTER TABLE company ADD COLUMN IF NOT EXISTS modifiedat TIMESTAMP;

-- Case-insensitive duplicate protection on non-deleted rows only
CREATE UNIQUE INDEX IF NOT EXISTS ux_company_name_active
    ON company (LOWER(companyname))
    WHERE isdeleted = FALSE;

-- Search performance
CREATE INDEX IF NOT EXISTS ix_company_search
    ON company USING gin (
        to_tsvector('simple', coalesce(companyname,'') || ' ' ||
                               coalesce(contactperson,'') || ' ' ||
                               coalesce(mobileno,'') || ' ' ||
                               coalesce(email,''))
    );
