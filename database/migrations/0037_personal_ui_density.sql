BEGIN;

INSERT INTO settings (
    setting_key, setting_value, setting_group, data_type,
    default_value, description, display_order, updated_by
)
SELECT
    'ui.control_height', '28', 'General', 'integer',
    '28', 'Personal control height in pixels, shared by buttons, input fields and table rows.',
    910, 'system'
WHERE NOT EXISTS (
    SELECT 1 FROM settings
    WHERE setting_key = 'ui.control_height'
      AND companyid IS NULL
      AND userid IS NULL
);

UPDATE settings
SET setting_value = '28',
    default_value = '28',
    description = 'Personal control height in pixels, shared by buttons, input fields and table rows.',
    updated_at = CURRENT_TIMESTAMP,
    updated_by = 'system'
WHERE setting_key = 'ui.control_height'
  AND companyid IS NULL
  AND userid IS NULL;

UPDATE settings
SET setting_value = '260',
    default_value = '260',
    description = 'Fixed dashboard sidebar width in pixels.',
    is_editable = FALSE,
    updated_at = CURRENT_TIMESTAMP,
    updated_by = 'system'
WHERE setting_key = 'dashboard.sidebar_width'
  AND companyid IS NULL
  AND userid IS NULL;

COMMIT;
