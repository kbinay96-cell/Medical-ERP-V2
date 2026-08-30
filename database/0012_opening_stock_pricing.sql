-- =============================================================================
-- Migration: 0012_opening_stock_pricing.sql
-- Module   : Item Master - Super Discount & Business Type Setting
-- =============================================================================
BEGIN;

ALTER TABLE item ADD COLUMN IF NOT EXISTS super_discount_percent NUMERIC(5,2);

INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order)
VALUES
    ('general.business_type', 'Retailer', 'General', 'string', 'Retailer', 'Business type of the enterprise (Retailer or Wholesaler)', 30)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;

COMMIT;
