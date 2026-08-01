-- =========================================================
-- Migration: 0003_user_master_alignment.sql
-- Module: User Master
-- Medical ERP V2
-- ---------------------------------------------------------
-- IMPORTANT: This migration REPLACES the earlier draft
-- (0001_create_user_master.sql / user_master_schema.sql).
-- Those files targeted a `users` table design that never
-- matched the real, live table already created by
-- database/schema_auth.sql (userid, passwordhash,
-- passwordsalt, fullname, roleid, companyid, status, ...),
-- which Login/Session/Audit/Dashboard already depend on.
-- Do NOT run 0001_create_user_master.sql or
-- user_master_schema.sql against this database - they are
-- superseded by this file and kept only for historical
-- reference.
--
-- This migration only ADDS to the real table (never renames
-- or drops anything Login depends on), and adds two new,
-- previously-missing tables. Idempotent - safe to re-run.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- Additive columns needed by the User Master form that the
-- Login/Auth schema never required.
-- ---------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(150);
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);

-- Case-insensitive duplicate protection (mirrors the pattern
-- used for company/supplier). The real table already has a
-- plain UNIQUE(username) constraint; this index additionally
-- speeds up case-insensitive lookups used by exists_username().
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower ON users (LOWER(username));

CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (roleid);
CREATE INDEX IF NOT EXISTS idx_users_company ON users (companyid);

-- ---------------------------------------------------------
-- Password history - prevents password reuse. Column names
-- follow the existing project convention seen in audit_log
-- (no underscores), not the abandoned draft's user_id/created_on_bs
-- style.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_password_history (
    historyid       BIGSERIAL PRIMARY KEY,
    userid          INTEGER NOT NULL REFERENCES users(userid),
    passwordhash    VARCHAR(256) NOT NULL,
    passwordsalt    VARCHAR(64)  NOT NULL,
    createdat       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_pwd_history_user ON user_password_history(userid);

-- ---------------------------------------------------------
-- User Master audit trail - separate from the login-focused
-- audit_log (which already exists in schema_auth.sql) so
-- User Master CRUD actions (Create/Update/Activate/Deactivate/
-- Delete/Restore/PasswordReset) have their own detailed,
-- before/after JSONB trail without overloading audit_log's
-- simpler `details` text column.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_audit_log (
    auditid         BIGSERIAL PRIMARY KEY,
    userid          INTEGER NOT NULL REFERENCES users(userid),
    action          VARCHAR(30)  NOT NULL,
    performedby     VARCHAR(50),
    oldvalue        JSONB,
    newvalue        JSONB,
    remarks         VARCHAR(255),
    actionat        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_audit_user   ON user_audit_log(userid);
CREATE INDEX IF NOT EXISTS idx_user_audit_action ON user_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_user_audit_date   ON user_audit_log(actionat);

COMMIT;
