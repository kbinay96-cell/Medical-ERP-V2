-- database/migrations/0017_add_ui_appearance_settings.sql
-- Seeds adjustable UI appearance settings: control height (buttons/
-- sidebar rows), font size, font family. Idempotent.

INSERT INTO settings (
    setting_key, setting_value, setting_group, data_type,
    default_value, description, display_order, updated_by
)
SELECT 'ui.control_height', '34', 'General', 'integer',
       '34', 'Height (px) of buttons and sidebar menu rows across the app.',
       910, 'system'
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE setting_key = 'ui.control_height');

INSERT INTO settings (
    setting_key, setting_value, setting_group, data_type,
    default_value, description, display_order, updated_by
)
SELECT 'ui.font_size', '10.5', 'General', 'decimal',
       '10.5', 'Base font size (pt) used across the whole application.',
       911, 'system'
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE setting_key = 'ui.font_size');

INSERT INTO settings (
    setting_key, setting_value, setting_group, data_type,
    default_value, description, display_order, updated_by
)
SELECT 'ui.font_family', 'Segoe UI', 'General', 'string',
       'Segoe UI', 'Font family used across the whole application.',
       912, 'system'
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE setting_key = 'ui.font_family');