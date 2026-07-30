-- =========================================================
-- Medical ERP V2
-- Company table cleanup - run this ONCE after the old
-- schema_company.sql accidentally ran instead of the v2 one.
-- Removes columns we don't need, adds the ones we do.
-- =========================================================

-- Drop the old GIN index first - it references `city`, which
-- we're about to remove.
DROP INDEX IF EXISTS ix_company_search;

-- Remove columns that don't belong (not part of the real,
-- agreed Company Master field list):
ALTER TABLE company DROP COLUMN IF EXISTS city;
ALTER TABLE company DROP COLUMN IF EXISTS state;
ALTER TABLE company DROP COLUMN IF EXISTS pincode;
ALTER TABLE company DROP COLUMN IF EXISTS licenseno;
ALTER TABLE company DROP COLUMN IF EXISTS logopath;
ALTER TABLE company DROP COLUMN IF EXISTS isactive;   -- we use the real `status` text column instead
ALTER TABLE company DROP COLUMN IF EXISTS createdat;  -- the real table already has `createddate`

-- Add the columns that were actually missing:
ALTER TABLE company ADD COLUMN IF NOT EXISTS contactperson VARCHAR(100);
ALTER TABLE company ADD COLUMN IF NOT EXISTS mobileno VARCHAR(20);
ALTER TABLE company ADD COLUMN IF NOT EXISTS remarks VARCHAR(500);

-- Recreate the search index against the correct columns
CREATE INDEX IF NOT EXISTS ix_company_search
    ON company USING gin (
        to_tsvector('simple', coalesce(companyname,'') || ' ' ||
                               coalesce(contactperson,'') || ' ' ||
                               coalesce(mobileno,'') || ' ' ||
                               coalesce(email,''))
    );

-- Confirm the final structure
-- (run \d company afterward to verify)
