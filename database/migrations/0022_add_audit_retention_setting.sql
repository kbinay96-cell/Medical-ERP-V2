-- Migration 0022: Add audit-log retention setting.
-- Governs automatic cleanup of old rows from audit_log,
-- login_history, failed_login_history, and user_audit_log
-- (engines/audit_cleanup_engine.py), run once per app startup.

INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order) VALUES
    ('security.audit_retention_days', '90', 'User & Security', 'integer', '90', 'Automatically delete audit/login history older than this many days (0 = never delete)', 90)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;