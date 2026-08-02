-- =============================================================================
-- Migration: 0003_create_manufacturer.sql
-- Module   : Manufacturer Master
-- Depends  : 0001_* (auth/calendar), schema_auth.sql (settings table)
--
-- Idempotent (safe to run more than once), wrapped in a transaction so it
-- either fully applies or not at all.
-- =============================================================================

BEGIN;

\i ../schema_manufacturer.sql

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'migration_history'
    ) THEN
        INSERT INTO migration_history (migration_name, applied_at)
        VALUES ('0003_create_manufacturer', now())
        ON CONFLICT (migration_name) DO NOTHING;
    END IF;
END $$;

COMMIT;
