-- =============================================================================
-- Migration: 0006_create_stock_transaction.sql
-- Module   : Stock Ledger (append-only movement history)
-- Depends  : schema_item.sql (item, item_batch tables)
--
-- Purpose: Immutable audit trail of every stock movement (Opening Stock,
-- Purchase, Sale, Adjustment, Return). item_batch holds only the CURRENT
-- balance per batch; this table holds the HISTORY of how that balance was
-- reached. Never UPDATE or DELETE a row here -- corrections are made via a
-- new reversing entry, per project rule (mirrors audit_log's insert-only
-- design).
--
-- Idempotent, transaction-wrapped, additive only.
-- =============================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS stock_transaction (
    stock_transaction_id   SERIAL PRIMARY KEY,
    item_id                 INTEGER        NOT NULL REFERENCES item(item_id),
    item_batch_id           INTEGER        NOT NULL REFERENCES item_batch(item_batch_id),
    transaction_type         VARCHAR(20)   NOT NULL,
    quantity_in               NUMERIC(18,3) NOT NULL DEFAULT 0,
    quantity_out               NUMERIC(18,3) NOT NULL DEFAULT 0,
    reference_table              VARCHAR(50),
    reference_id                  INTEGER,
    remarks                        TEXT,
    created_by                      INTEGER NOT NULL,
    created_at_ad                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at_bs                     VARCHAR(10) NOT NULL,
    CONSTRAINT chk_stock_txn_type CHECK (transaction_type IN ('Opening', 'Purchase', 'Sale', 'Adjustment', 'Return')),
    CONSTRAINT chk_stock_txn_qty_in CHECK (quantity_in >= 0),
    CONSTRAINT chk_stock_txn_qty_out CHECK (quantity_out >= 0)
);

CREATE INDEX IF NOT EXISTS idx_stock_txn_item ON stock_transaction (item_id);
CREATE INDEX IF NOT EXISTS idx_stock_txn_batch ON stock_transaction (item_batch_id);
CREATE INDEX IF NOT EXISTS idx_stock_txn_type ON stock_transaction (transaction_type);
CREATE INDEX IF NOT EXISTS idx_stock_txn_reference ON stock_transaction (reference_table, reference_id);

COMMENT ON TABLE stock_transaction IS 'Append-only stock movement ledger - Medical ERP V2. Never UPDATE/DELETE; corrections via a new reversing row. item_batch = current balance, this table = how it got there.';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'migration_history'
    ) THEN
        INSERT INTO migration_history (migration_name, applied_at)
        VALUES ('0006_create_stock_transaction', now())
        ON CONFLICT (migration_name) DO NOTHING;
    END IF;
END $$;

COMMIT;