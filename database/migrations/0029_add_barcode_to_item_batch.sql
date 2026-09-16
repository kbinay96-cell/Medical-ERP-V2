ALTER TABLE item_batch ADD COLUMN IF NOT EXISTS barcode VARCHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS uq_item_batch_barcode
    ON item_batch (barcode) WHERE barcode IS NOT NULL;