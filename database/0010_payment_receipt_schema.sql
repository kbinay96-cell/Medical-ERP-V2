-- =============================================================================
-- Migration: 0010_payment_receipt_schema.sql
-- Module   : Accounts — supplier Payments and customer Receipts
-- Depends  : 0007_purchase_schema.sql, 0009_sale_schema.sql
--
-- Additive only. Screens/engines for these tables come after Sales.
-- =============================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS supplier_payment (
    supplier_payment_id   SERIAL PRIMARY KEY,
    payment_number        VARCHAR(30) NOT NULL UNIQUE,
    supplier_id           INTEGER NOT NULL REFERENCES supplier(supplier_id),
    purchase_invoice_id   INTEGER REFERENCES purchase_invoice(purchase_invoice_id),
    payment_date_ad       DATE NOT NULL,
    payment_date_bs       VARCHAR(10) NOT NULL,
    amount                NUMERIC(14,2) NOT NULL,
    payment_mode          VARCHAR(20) NOT NULL DEFAULT 'Cash',
    remarks               TEXT,
    is_deleted            BOOLEAN NOT NULL DEFAULT FALSE,
    created_by            INTEGER NOT NULL,
    created_at_ad         TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs         VARCHAR(10) NOT NULL,
    CONSTRAINT chk_supplier_payment_mode CHECK (payment_mode IN ('Cash', 'Bank', 'Cheque', 'Adjust')),
    CONSTRAINT chk_supplier_payment_amount CHECK (amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_supplier_payment_supplier
    ON supplier_payment (supplier_id) WHERE is_deleted = FALSE;

CREATE TABLE IF NOT EXISTS customer_receipt (
    customer_receipt_id   SERIAL PRIMARY KEY,
    receipt_number        VARCHAR(30) NOT NULL UNIQUE,
    customer_id           INTEGER NOT NULL REFERENCES customers(customer_id),
    sale_invoice_id       INTEGER REFERENCES sale_invoice(sale_invoice_id),
    receipt_date_ad       DATE NOT NULL,
    receipt_date_bs       VARCHAR(10) NOT NULL,
    amount                NUMERIC(14,2) NOT NULL,
    receipt_mode          VARCHAR(20) NOT NULL DEFAULT 'Cash',
    remarks               TEXT,
    is_deleted            BOOLEAN NOT NULL DEFAULT FALSE,
    created_by            INTEGER NOT NULL,
    created_at_ad         TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs         VARCHAR(10) NOT NULL,
    CONSTRAINT chk_customer_receipt_mode CHECK (receipt_mode IN ('Cash', 'Bank', 'Cheque', 'Adjust')),
    CONSTRAINT chk_customer_receipt_amount CHECK (amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_customer_receipt_customer
    ON customer_receipt (customer_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_customer_receipt_invoice
    ON customer_receipt (sale_invoice_id) WHERE is_deleted = FALSE;

INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order)
VALUES
    ('accounts.payment_prefix', 'PAY-', 'Accounts', 'string', 'PAY-', 'Prefix for supplier payment numbers', 10),
    ('accounts.receipt_prefix', 'RCT-', 'Accounts', 'string', 'RCT-', 'Prefix for customer receipt numbers', 20)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;

COMMIT;
