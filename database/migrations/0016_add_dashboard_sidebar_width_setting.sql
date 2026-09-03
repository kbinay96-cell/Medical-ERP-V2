-- database/migrations/0016_add_dashboard_sidebar_width_setting.sql
-- Seeds the "dashboard.sidebar_width" setting used to persist the
-- Dashboard sidebar tree's width across sessions. Idempotent -- safe
-- to re-run (settings.setting_key has no unique constraint, so this
-- uses WHERE NOT EXISTS instead of ON CONFLICT).

INSERT INTO settings (
    setting_key, setting_value, setting_group, data_type,
    default_value, description, display_order, updated_by
)
SELECT
    'dashboard.sidebar_width', '260', 'General', 'int',
    '260', 'Width (px) of the Dashboard sidebar tree, remembered across sessions.',
    900, 'system'
WHERE NOT EXISTS (
    SELECT 1 FROM settings WHERE setting_key = 'dashboard.sidebar_width'
);