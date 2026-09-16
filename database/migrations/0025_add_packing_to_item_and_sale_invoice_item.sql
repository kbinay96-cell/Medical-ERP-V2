-- 0025: add packing column to item (Item Master) and sale_invoice_item
-- (Sale line-level snapshot). Free-text field, e.g. "Strip of 10", "100ml Bottle".

ALTER TABLE item
    ADD COLUMN IF NOT EXISTS packing VARCHAR(50);

ALTER TABLE sale_invoice_item
    ADD COLUMN IF NOT EXISTS packing VARCHAR(50);