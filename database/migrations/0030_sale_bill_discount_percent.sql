-- Sale Invoice: bill_discount_amount already exists (from 0009), but
-- bill_discount_percent was never added, so percent-based bill discount
-- could not be persisted. Added now to match Purchase Invoice's
-- bill_discount_percent/bill_discount_amount pair (0008_purchase_invoice_enhancements.sql).
ALTER TABLE sale_invoice
    ADD COLUMN IF NOT EXISTS bill_discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0;