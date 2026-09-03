-- =========================================================
-- Medical ERP V2
-- Global default for where WhatsApp-flow PDFs get saved.
-- Per-company override saved the same way as smtp.* settings,
-- via engines.settings_engine.save_company_setting_value().
-- =========================================================
INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order) VALUES
    ('whatsapp.pdf_save_path', '', 'WhatsApp', 'path', '', 'Folder where invoice PDFs are saved before attaching to WhatsApp', 10)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;