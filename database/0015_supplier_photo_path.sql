-- 0015_supplier_photo_path.sql
-- Adds photo_path column to supplier table (feature was already wired in
-- code/UI but the DB column was never migrated, mirroring the same earlier
-- fix on the item table).

ALTER TABLE supplier ADD COLUMN IF NOT EXISTS photo_path TEXT NULL;