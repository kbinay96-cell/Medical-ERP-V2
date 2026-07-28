-- =============================================================================
-- Migration: 0002_create_supplier.sql
-- Module   : Supplier Master
-- Depends  : 0001_* (auth/calendar migrations already applied)
--
-- This migration is idempotent (safe to run more than once) and wrapped in a
-- transaction so it either fully applies or not at all.
-- =============================================================================

BEGIN;

\i ../schema_supplier.sql

-- Record migration in the migration history table if one exists.
-- (Matches the pattern used by 0001_* migrations in this project; if the
--  migration_history table does not exist yet in a given environment this
--  block is skipped rather than failing the whole migration.)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'migration_history'
    ) THEN
        INSERT INTO migration_history (migration_name, applied_at)
        VALUES ('0002_create_supplier', now())
        ON CONFLICT (migration_name) DO NOTHING;
    END IF;
END $$;

COMMIT;
