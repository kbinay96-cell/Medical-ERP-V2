-- 0024: fix Sale module save-blocking schema gaps
-- (1) entry_mode was never added to sale_invoice_item despite being written by the engine/model
-- (2) payment_type retained NOT NULL from the pre-0015 payment_mode rename, blocking the
--     blueprint's NULL = "fully Credit" option

ALTER TABLE sale_invoice_item
    ADD COLUMN IF NOT EXISTS entry_mode VARCHAR(10) NOT NULL DEFAULT 'free_qty';

ALTER TABLE sale_invoice_item
    ADD CONSTRAINT chk_sale_invoice_item_entry_mode
    CHECK (entry_mode IN ('free_qty', 'net_rate'));

COMMENT ON COLUMN sale_invoice_item.entry_mode IS
    'Per-line pricing entry mode: free_qty (auto-fill free qty) or net_rate (auto-reduced rate). Added in 0024 -- was missing from 0009/0015.';

ALTER TABLE sale_invoice
    ALTER COLUMN payment_type DROP NOT NULL;