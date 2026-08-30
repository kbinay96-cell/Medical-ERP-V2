-- =============================================================================
-- Migration: 0009_sale_schema.sql
-- Module   : Sales Invoice (header + lines)
-- Depends  : schema_customer.sql (customers), schema_item.sql (item, item_batch)
--
-- Creates sale_invoice / sale_invoice_item that schema_sale_return.sql FKs.
-- Stock is NOT stored here. Posted sales deduct item_batch.batch_qty and
-- append stock_ledger via ItemEngine.post_stock_movement() (transaction_type
-- = 'SALE', quantity_change negative).
--
-- Idempotent, transaction-wrapped, additive only.
-- =============================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS sale_invoice (
    sale_invoice_id       SERIAL PRIMARY KEY,
    invoice_number        VARCHAR(30) NOT NULL UNIQUE,
    customer_id           INTEGER NOT NULL REFERENCES customers(customer_id),
    invoice_date_ad       DATE NOT NULL,
    invoice_date_bs       VARCHAR(10) NOT NULL,
    payment_mode          VARCHAR(20) NOT NULL DEFAULT 'Cash',
    total_qty             NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_gross_amount    NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cc_amount       NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_tax_amount      NUMERIC(14,2) NOT NULL DEFAULT 0,
    bill_discount_amount  NUMERIC(14,2) NOT NULL DEFAULT 0,
    round_off_amount      NUMERIC(8,2) NOT NULL DEFAULT 0,
    grand_total           NUMERIC(14,2) NOT NULL DEFAULT 0,
    paid_amount           NUMERIC(14,2) NOT NULL DEFAULT 0,
    balance_amount        NUMERIC(14,2) NOT NULL DEFAULT 0,
    status                VARCHAR(20) NOT NULL DEFAULT 'Posted',
    remarks               TEXT,
    is_deleted            BOOLEAN NOT NULL DEFAULT FALSE,
    created_by            INTEGER NOT NULL,
    created_at_ad         TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs         VARCHAR(10) NOT NULL,
    updated_by            INTEGER,
    updated_at_ad         TIMESTAMP,
    updated_at_bs         VARCHAR(10),
    deleted_by            INTEGER,
    deleted_at_ad         TIMESTAMP,
    deleted_at_bs         VARCHAR(10),
    cancellation_reason   TEXT,

    CONSTRAINT chk_sale_invoice_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_sale_invoice_payment_mode CHECK (payment_mode IN ('Cash', 'Credit', 'Partial'))
);

CREATE INDEX IF NOT EXISTS idx_sale_invoice_customer
    ON sale_invoice (customer_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_invoice_date
    ON sale_invoice (invoice_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_invoice_status
    ON sale_invoice (status) WHERE is_deleted = FALSE;

COMMENT ON TABLE sale_invoice IS 'Sales Invoice header — Medical ERP V2. Soft-delete only. Stock deduction lives on item_batch + stock_ledger, not here.';
COMMENT ON COLUMN sale_invoice.balance_amount IS 'grand_total - paid_amount; Receipts module reduces this later.';

CREATE TABLE IF NOT EXISTS sale_invoice_item (
    sale_invoice_item_id  SERIAL PRIMARY KEY,
    sale_invoice_id       INTEGER NOT NULL REFERENCES sale_invoice(sale_invoice_id),
    item_id               INTEGER NOT NULL REFERENCES item(item_id),
    item_batch_id         INTEGER NOT NULL REFERENCES item_batch(item_batch_id),
    batch_no              VARCHAR(50) NOT NULL,
    expiry_month          SMALLINT NOT NULL,
    expiry_year           SMALLINT NOT NULL,
    qty                   NUMERIC(12,2) NOT NULL,
    free_qty              NUMERIC(12,2) NOT NULL DEFAULT 0,
    rate                  NUMERIC(12,2) NOT NULL,
    discount_percent      NUMERIC(5,2) NOT NULL DEFAULT 0,
    discount_amount       NUMERIC(12,2) NOT NULL DEFAULT 0,
    cc_percent            NUMERIC(5,2) NOT NULL DEFAULT 0,
    cc_amount             NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax_percent           NUMERIC(5,2) NOT NULL DEFAULT 0,
    tax_amount            NUMERIC(12,2) NOT NULL DEFAULT 0,
    amount                NUMERIC(12,2) NOT NULL DEFAULT 0,
    remarks               TEXT,

    CONSTRAINT chk_sale_invoice_item_qty CHECK (qty > 0 OR free_qty > 0),
    CONSTRAINT chk_sale_invoice_item_expiry_month CHECK (expiry_month BETWEEN 1 AND 12)
);

CREATE INDEX IF NOT EXISTS idx_sale_invoice_item_invoice
    ON sale_invoice_item (sale_invoice_id);
CREATE INDEX IF NOT EXISTS idx_sale_invoice_item_item
    ON sale_invoice_item (item_id);
CREATE INDEX IF NOT EXISTS idx_sale_invoice_item_batch
    ON sale_invoice_item (item_batch_id);

COMMENT ON COLUMN sale_invoice_item.qty IS 'Paid (billed) units. Stock deducted is qty + free_qty against item_batch_id.';
COMMENT ON COLUMN sale_invoice_item.rate IS 'Sale rate per paid unit at posting time (snapshot).';

INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order)
VALUES
    ('sale.invoice_prefix', 'SINV-', 'Sales', 'string', 'SINV-', 'Prefix for auto-generated Sales Invoice numbers', 10),
    ('sale.return_prefix', 'SRTN-', 'Sales', 'string', 'SRTN-', 'Prefix for auto-generated Sale Return numbers', 20)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;

COMMIT;
