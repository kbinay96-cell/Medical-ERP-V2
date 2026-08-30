-- database/migrations/0001_purchase_schema.sql
-- Purchase Module: Phase-1 schema (purchase_order, purchase_invoice, invoice items, return tables)
-- Run this inside Medical-ERP-V2 project's migration process (or psql) after review.

BEGIN;

-- Purchase Order header
CREATE TABLE IF NOT EXISTS purchase_order (
    purchase_order_id   SERIAL PRIMARY KEY,
    po_number           VARCHAR(30) NOT NULL UNIQUE,
    supplier_id         INTEGER NOT NULL REFERENCES supplier(supplier_id),
    order_date_ad       DATE NOT NULL,
    order_date_bs       VARCHAR(10) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'Draft',  -- Draft, Sent, Received, Cancelled
    sent_via            VARCHAR(20),
    sent_at_ad          TIMESTAMP,
    remarks             TEXT,
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    created_by          INTEGER NOT NULL,
    created_at_ad       TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs       VARCHAR(10) NOT NULL,
    updated_by          INTEGER,
    updated_at_ad       TIMESTAMP,
    updated_at_bs       VARCHAR(10),
    deleted_by          INTEGER,
    deleted_at_ad       TIMESTAMP,
    deleted_at_bs       VARCHAR(10)
);

CREATE INDEX IF NOT EXISTS idx_purchase_order_supplier_id ON purchase_order (supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchase_order_status ON purchase_order (status);

-- Purchase Order items (one row per item in PO)
CREATE TABLE IF NOT EXISTS purchase_order_item (
    po_item_id                    SERIAL PRIMARY KEY,
    purchase_order_id             INTEGER NOT NULL REFERENCES purchase_order(purchase_order_id) ON DELETE CASCADE,
    item_id                       INTEGER NOT NULL REFERENCES item(item_id),
    ordered_qty                   NUMERIC(12,2) NOT NULL,
    rate                          NUMERIC(12,2) NOT NULL DEFAULT 0,
    is_auto_suggested             BOOLEAN NOT NULL DEFAULT FALSE,
    stock_at_order_time           NUMERIC(18,2),
    minimum_stock_at_order_time   NUMERIC(18,2),
    remarks                       TEXT
);

CREATE INDEX IF NOT EXISTS idx_po_item_item_id ON purchase_order_item (item_id);
CREATE INDEX IF NOT EXISTS idx_po_item_po_id ON purchase_order_item (purchase_order_id);

-- Purchase Invoice (GRN + Bill combined for Phase-1)
CREATE TABLE IF NOT EXISTS purchase_invoice (
    purchase_invoice_id   SERIAL PRIMARY KEY,
    invoice_number        VARCHAR(30) NOT NULL,
    internal_ref_number   VARCHAR(30) NOT NULL UNIQUE,
    supplier_id           INTEGER NOT NULL REFERENCES supplier(supplier_id),
    purchase_order_id     INTEGER REFERENCES purchase_order(purchase_order_id),
    invoice_date_ad       DATE NOT NULL,
    invoice_date_bs       VARCHAR(10) NOT NULL,
    total_qty             NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_gross_amount    NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cc_amount       NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_freight_amount  NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_other_charges   NUMERIC(14,2) NOT NULL DEFAULT 0,
    grand_total           NUMERIC(14,2) NOT NULL DEFAULT 0,
    status                VARCHAR(20) NOT NULL DEFAULT 'Posted', -- Draft, Posted, Cancelled
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
    deleted_at_bs         VARCHAR(10)
);

CREATE INDEX IF NOT EXISTS idx_purchase_invoice_supplier_id ON purchase_invoice (supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchase_invoice_po_id ON purchase_invoice (purchase_order_id);

-- Prevent duplicate supplier invoice numbers (for active rows)
CREATE UNIQUE INDEX IF NOT EXISTS ux_purchase_invoice_supplier_billno
    ON purchase_invoice (supplier_id, invoice_number)
    WHERE is_deleted = FALSE;

-- Purchase Invoice line items (line-level batch info)
CREATE TABLE IF NOT EXISTS purchase_invoice_item (
    purchase_invoice_item_id   SERIAL PRIMARY KEY,
    purchase_invoice_id        INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id) ON DELETE CASCADE,
    item_id                    INTEGER NOT NULL REFERENCES item(item_id),
    batch_no                   VARCHAR(50) NOT NULL,
    expiry_month               SMALLINT NOT NULL,
    expiry_year                SMALLINT NOT NULL,
    qty                        NUMERIC(12,2) NOT NULL,
    free_qty                   NUMERIC(12,2) NOT NULL DEFAULT 0,
    purchase_rate              NUMERIC(12,2) NOT NULL,
    discount_percent           NUMERIC(5,2) NOT NULL DEFAULT 0,
    discount_amount            NUMERIC(12,2) NOT NULL DEFAULT 0,
    cc_percent                 NUMERIC(5,2) NOT NULL DEFAULT 0,
    cc_amount                  NUMERIC(12,2) NOT NULL DEFAULT 0,
    freight_amount_allocated   NUMERIC(12,2) NOT NULL DEFAULT 0,
    other_charges_allocated    NUMERIC(12,2) NOT NULL DEFAULT 0,
    landing_cost_per_unit      NUMERIC(12,4) NOT NULL DEFAULT 0,
    mrp                        NUMERIC(12,2) NOT NULL,
    sale_rate                  NUMERIC(12,2) NOT NULL DEFAULT 0,
    item_batch_id              INTEGER REFERENCES item_batch(item_batch_id),
    remarks                    TEXT
);

CREATE INDEX IF NOT EXISTS idx_purchase_invoice_item_invoice_id ON purchase_invoice_item (purchase_invoice_id);
CREATE INDEX IF NOT EXISTS idx_purchase_invoice_item_item_id ON purchase_invoice_item (item_id);

-- Purchase Return (Phase-2)
CREATE TABLE IF NOT EXISTS purchase_return (
    purchase_return_id    SERIAL PRIMARY KEY,
    return_number         VARCHAR(30) NOT NULL UNIQUE,
    purchase_invoice_id   INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),
    supplier_id           INTEGER NOT NULL REFERENCES supplier(supplier_id),
    return_date_ad        DATE NOT NULL,
    return_date_bs        VARCHAR(10) NOT NULL,
    total_amount          NUMERIC(14,2) NOT NULL DEFAULT 0,
    reason                TEXT,
    status                VARCHAR(20) NOT NULL DEFAULT 'Posted',
    is_deleted            BOOLEAN NOT NULL DEFAULT FALSE,
    created_by            INTEGER NOT NULL,
    created_at_ad         TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs         VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_return_item (
    purchase_return_item_id SERIAL PRIMARY KEY,
    purchase_return_id      INTEGER NOT NULL REFERENCES purchase_return(purchase_return_id) ON DELETE CASCADE,
    item_batch_id           INTEGER NOT NULL REFERENCES item_batch(item_batch_id),
    return_qty              NUMERIC(12,2) NOT NULL,
    return_rate             NUMERIC(12,2) NOT NULL,
    remarks                 TEXT
);

CREATE INDEX IF NOT EXISTS idx_purchase_return_invoice_id ON purchase_return (purchase_invoice_id);
CREATE INDEX IF NOT EXISTS idx_purchase_return_item_batch_id ON purchase_return_item (item_batch_id);

-- Helpful views/indexes can be added later as usage patterns emerge.

-- Settings seed (safe to run multiple times: ON CONFLICT DO NOTHING)
INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order)
VALUES
    ('purchase.po_prefix', 'PO-', 'Purchase', 'string', 'PO-', 'Prefix for auto-generated Purchase Order numbers', 10),
    ('purchase.invoice_prefix', 'PINV-', 'Purchase', 'string', 'PINV-', 'Prefix for auto-generated Purchase Invoice internal reference numbers', 20),
    ('purchase.return_prefix', 'PRET-', 'Purchase', 'string', 'PRET-', 'Prefix for auto-generated Purchase Return numbers (Phase-2)', 30),
    ('purchase.reorder_target_multiplier', '2', 'Purchase', 'decimal', '2', 'Suggested reorder qty = (minimum_stock x multiplier) - current_stock', 40),
    ('purchase.whatsapp_message_template', 'Hello {supplier_name}, please arrange the following items:\n{item_list}\n\nRegards, {company_name}', 'Purchase', 'string', 'Hello {supplier_name}, please arrange the following items:\n{item_list}\n\nRegards, {company_name}', 'WhatsApp order message template. Placeholders: {supplier_name} {po_number} {item_list} {company_name}', 50),
    ('purchase.email_subject_template', 'Purchase Order - {po_number}', 'Purchase', 'string', 'Purchase Order - {po_number}', 'Email subject template for Purchase Orders', 60),
    ('purchase.email_body_template', 'Dear {supplier_name},\n\nPlease find our purchase order below:\n{item_list}\n\nRegards,\n{company_name}', 'Purchase', 'string', 'Dear {supplier_name},\n\nPlease find our purchase order below:\n{item_list}\n\nRegards,\n{company_name}', 'Email body template for Purchase Orders', 70),
    ('purchase.email_send_mode', 'mailto', 'Purchase', 'string', 'mailto', 'mailto = opens default email client (manual send, zero setup) | smtp = auto-send (future, needs SMTP credentials)', 80)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;

COMMIT;