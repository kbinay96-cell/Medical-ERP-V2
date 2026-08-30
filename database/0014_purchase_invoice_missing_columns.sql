-- =============================================================================
-- Migration: 0014_purchase_invoice_missing_columns.sql
-- Module   : Purchase Invoice - adds columns the Engine already expects
-- =============================================================================
BEGIN;

ALTER TABLE purchase_invoice ADD COLUMN IF NOT EXISTS bill_discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0;
ALTER TABLE purchase_invoice ADD COLUMN IF NOT EXISTS round_off_amount NUMERIC(14,2) NOT NULL DEFAULT 0;

COMMIT;