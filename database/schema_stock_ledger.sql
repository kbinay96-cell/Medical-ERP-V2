-- =============================================================================
-- Medical ERP V2 - Stock Ledger
-- File: database/schema_stock_ledger.sql
-- Purpose: Immutable audit trail of every stock movement against an
--          item_batch. item_batch.batch_qty stays the fast "current
--          balance" column (already built); stock_ledger is the history
--          alongside it -- every movement writes ONE row here, in the
--          SAME database transaction as the item_batch.batch_qty change,
--          so the two can never drift apart.
--
-- Design notes:
--   * NO SOFT DELETE, NO UPDATE -- this table is APPEND-ONLY, like a bank
--     statement. A mistake is corrected with a new 'ADJUSTMENT' row that
--     reverses it, never by editing or deleting a past row.
--   * quantity_change: positive = stock IN (Opening, Purchase, Sale
--     Return), negative = stock OUT (Sale, Purchase Return, a downward
--     Adjustment).
--   * balance_after: the batch's running total AFTER this row was
--     applied -- a point-in-time snapshot, so historical reports never
--     need to re-sum the whole ledger from scratch.
--   * reference_type / reference_id: polymorphic pointer to whichever
--     module posted this (e.g. reference_type='purchase',
--     reference_id=<purchase_id>) -- NULL for OPENING and manual
--     ADJUSTMENT entries, which have no source document.
--   * Only Purchase/Sale-type entries will ever populate reference_type/
--     reference_id -- those modules do not exist in this repo yet; this
--     table is built now so ItemEngine.post_stock_movement() (see
--     engines/item_engine.py) has somewhere to log to the day they land,
--     without an item_batch-shape change at that point.
-- =============================================================================

CREATE TABLE IF NOT EXISTS stock_ledger (
    stock_ledger_id       SERIAL PRIMARY KEY,

    item_id               INTEGER         NOT NULL REFERENCES item(item_id),
    item_batch_id         INTEGER         NOT NULL REFERENCES item_batch(item_batch_id),

    transaction_type      VARCHAR(20)     NOT NULL,
    quantity_change       NUMERIC(18, 3)  NOT NULL,
    balance_after         NUMERIC(18, 3)  NOT NULL,

    reference_type        VARCHAR(30),
    reference_id          INTEGER,

    remarks               TEXT,

    created_by            INTEGER         NOT NULL,
    created_at_ad         TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at_bs         VARCHAR(10)     NOT NULL,

    CONSTRAINT chk_stock_ledger_transaction_type CHECK (
        transaction_type IN ('OPENING', 'PURCHASE', 'SALE', 'SALE_RETURN', 'PURCHASE_RETURN', 'ADJUSTMENT')
    )
);

CREATE INDEX IF NOT EXISTS idx_stock_ledger_item        ON stock_ledger (item_id);
CREATE INDEX IF NOT EXISTS idx_stock_ledger_batch       ON stock_ledger (item_batch_id);
CREATE INDEX IF NOT EXISTS idx_stock_ledger_type        ON stock_ledger (transaction_type);
CREATE INDEX IF NOT EXISTS idx_stock_ledger_reference    ON stock_ledger (reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_stock_ledger_created      ON stock_ledger (created_at_ad);

COMMENT ON TABLE stock_ledger IS 'Append-only stock movement history for Medical ERP V2 -- never updated or deleted. item_batch.batch_qty is the fast current-balance column; this table is the audit trail behind it.';
COMMENT ON COLUMN stock_ledger.quantity_change IS 'Positive = stock IN (Opening/Purchase/Sale Return), negative = stock OUT (Sale/Purchase Return/downward Adjustment).';
COMMENT ON COLUMN stock_ledger.balance_after IS 'The batch''s running total immediately after this entry -- a snapshot, not recalculated at report time.';
