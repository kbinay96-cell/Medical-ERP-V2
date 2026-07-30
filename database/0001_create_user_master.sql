-- =========================================================
-- Migration: 0001_create_user_master.sql
-- Module: User Master
-- Medical ERP V2
-- Idempotent forward migration — safe to re-run.
-- =========================================================

BEGIN;

-- Placeholder stubs — remove if roles/companies already exist from
-- Role Master / Settings Module in your database.
CREATE TABLE IF NOT EXISTS roles (
    role_id     SERIAL PRIMARY KEY,
    role_name   VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS companies (
    company_id   SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id             BIGSERIAL PRIMARY KEY,
    username            VARCHAR(50)  NOT NULL,
    display_name        VARCHAR(150) NOT NULL,
    email               VARCHAR(150),
    phone               VARCHAR(20),

    password_hash       VARCHAR(255) NOT NULL,
    password_algo       VARCHAR(20)  NOT NULL DEFAULT 'ARGON2ID',
    password_updated_at TIMESTAMP    NOT NULL DEFAULT now(),
    must_change_password BOOLEAN     NOT NULL DEFAULT TRUE,

    role_id             INTEGER      REFERENCES roles(role_id),
    company_id          INTEGER      REFERENCES companies(company_id),

    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted           BOOLEAN     NOT NULL DEFAULT FALSE,

    created_on_bs       VARCHAR(10)  NOT NULL,
    created_on_ad       TIMESTAMP    NOT NULL DEFAULT now(),
    created_by          BIGINT       REFERENCES users(user_id),

    updated_on_bs       VARCHAR(10),
    updated_on_ad       TIMESTAMP,
    updated_by          BIGINT       REFERENCES users(user_id),

    deleted_on_bs       VARCHAR(10),
    deleted_on_ad       TIMESTAMP,
    deleted_by          BIGINT       REFERENCES users(user_id),

    CONSTRAINT uq_users_username UNIQUE (username)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower ON users (LOWER(username));
CREATE INDEX IF NOT EXISTS idx_users_active   ON users (is_active) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_users_deleted  ON users (is_deleted);
CREATE INDEX IF NOT EXISTS idx_users_role     ON users (role_id);
CREATE INDEX IF NOT EXISTS idx_users_company  ON users (company_id);

CREATE TABLE IF NOT EXISTS user_password_history (
    history_id      BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(user_id),
    password_hash   VARCHAR(255) NOT NULL,
    password_algo   VARCHAR(20) NOT NULL,
    created_on_bs   VARCHAR(10) NOT NULL,
    created_on_ad   TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pwd_history_user ON user_password_history(user_id);

CREATE TABLE IF NOT EXISTS user_audit_log (
    audit_id        BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(user_id),
    action          VARCHAR(30)  NOT NULL,
    performed_by    BIGINT REFERENCES users(user_id),
    old_value       JSONB,
    new_value       JSONB,
    remarks         VARCHAR(255),
    action_on_bs    VARCHAR(10) NOT NULL,
    action_on_ad    TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_user   ON user_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON user_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_date   ON user_audit_log(action_on_ad);

COMMIT;
