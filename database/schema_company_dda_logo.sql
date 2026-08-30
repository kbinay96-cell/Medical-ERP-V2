-- =========================================================
-- Medical ERP V2
-- Adds DDA/Drug License No. and Logo path back to company,
-- per explicit request (previously removed in
-- cleanup_company_columns.sql as "not part of the agreed
-- field list" -- now needed for the Purchase Invoice bill
-- letterhead).
-- =========================================================
ALTER TABLE company ADD COLUMN IF NOT EXISTS ddano VARCHAR(50);
ALTER TABLE company ADD COLUMN IF NOT EXISTS logopath VARCHAR(255);