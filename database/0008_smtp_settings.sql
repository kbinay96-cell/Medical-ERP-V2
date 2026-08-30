-- =========================================================
-- Medical ERP V2
-- Global default SMTP settings (per-company overrides will be
-- saved via engines.settings_engine.save_company_setting_value()
-- from the Company Form's new Email Settings section -- these
-- rows here are just the global fallback/default, same pattern
-- as purchase.email_send_mode in 0007_purchase_schema.sql).
--
-- NOTE: setting_value is stored as plain TEXT like every other
-- setting in this table -- smtp.app_password will therefore be
-- stored in plaintext in the database. Flagging this now; if
-- this needs to be encrypted at rest later, that's a separate
-- follow-up (would need a dedicated encrypted column, not this
-- generic settings table).
-- =========================================================
INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order) VALUES
    ('smtp.host', '', 'Email', 'string', '', 'SMTP server address (e.g. smtp.gmail.com)', 10),
    ('smtp.port', '587', 'Email', 'integer', '587', 'SMTP server port (587 for TLS, 465 for SSL)', 20),
    ('smtp.email', '', 'Email', 'string', '', 'Sender email address used to send invoices', 30),
    ('smtp.app_password', '', 'Email', 'string', '', 'App Password for the sender email account (not the normal account password)', 40)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;