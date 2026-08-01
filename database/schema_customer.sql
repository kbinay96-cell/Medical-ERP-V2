-- =========================================================
-- Medical ERP V2
-- Customer Master - Schema
-- ---------------------------------------------------------
-- Adds:
--   - areas, routes, price_levels  (future-ready reference
--     masters the Customer Master relates to - relation
--     only, no pricing/route logic yet, per spec)
--   - customers                    (the Customer Master itself)
--   - a `customer.code_prefix` row in the existing `settings`
--     table, so the "prefix configurable later through
--     Settings" requirement is live from day one, using the
--     Settings module already built for this ERP.
--
-- Run this AFTER schema_auth.sql (customers references
-- nothing from schema_auth.sql directly, but the settings
-- INSERT below needs the `settings` table to already exist).
-- =========================================================

-- ---------------------------------------------------------
-- AREA MASTER (future-ready - relation only)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS areas (
    area_id         SERIAL PRIMARY KEY,
    area_name       VARCHAR(100) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_areas_name_unique
    ON areas(LOWER(area_name));

-- ---------------------------------------------------------
-- ROUTE MASTER (future-ready - relation only)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS routes (
    route_id        SERIAL PRIMARY KEY,
    route_name      VARCHAR(100) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_routes_name_unique
    ON routes(LOWER(route_name));

-- ---------------------------------------------------------
-- PRICE LEVEL MASTER (future-ready - relation only, no
-- pricing logic lives here or anywhere yet)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_levels (
    price_level_id      SERIAL PRIMARY KEY,
    price_level_name    VARCHAR(100) NOT NULL,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_price_levels_name_unique
    ON price_levels(LOWER(price_level_name));

INSERT INTO price_levels (price_level_name) VALUES
    ('Retail'), ('Wholesale'), ('Distributor'), ('Hospital'), ('Doctor')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------
-- CUSTOMER MASTER
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    customer_id         SERIAL PRIMARY KEY,
    customer_code       VARCHAR(20)  NOT NULL,
    customer_name       VARCHAR(150) NOT NULL,
    print_name           VARCHAR(150),
    contact_person       VARCHAR(100),
    address               TEXT,
    city                  VARCHAR(100),
    state                 VARCHAR(100),
    country               VARCHAR(100) DEFAULT 'Nepal',
    pincode               VARCHAR(20),
    phone                 VARCHAR(30),
    mobile                VARCHAR(30),
    alternate_mobile      VARCHAR(30),
    email                 VARCHAR(150),
    website               VARCHAR(150),
    pan_vat               VARCHAR(30),
    gst_number            VARCHAR(30),   -- future ready
    drug_license_no       VARCHAR(50),

    credit_limit          NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (credit_limit >= 0),
    credit_days           INTEGER        NOT NULL DEFAULT 0 CHECK (credit_days >= 0),
    opening_balance       NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (opening_balance >= 0),
    balance_type          VARCHAR(2)     NOT NULL DEFAULT 'Dr' CHECK (balance_type IN ('Dr', 'Cr')),

    price_level_id        INTEGER REFERENCES price_levels(price_level_id),
    area_id                INTEGER REFERENCES areas(area_id),
    route_id               INTEGER REFERENCES routes(route_id),

    remarks                TEXT,
    photo_path             VARCHAR(255),  -- relative path only, e.g. resources/images/customers/CUS-0001.jpg - NEVER a BLOB

    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted               BOOLEAN NOT NULL DEFAULT FALSE,  -- soft delete only, no physical delete

    created_by                VARCHAR(50),
    created_at_ad             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at_bs             VARCHAR(12),
    updated_by                VARCHAR(50),
    updated_at_ad              TIMESTAMP,
    updated_at_bs              VARCHAR(12),
    deleted_by                  VARCHAR(50),
    deleted_at_ad                TIMESTAMP,
    deleted_at_bs                VARCHAR(12)
);

-- Uniqueness applies only to non-deleted rows, so a deleted
-- customer's name/code can be reused by a genuinely new customer.
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_name_unique
    ON customers(LOWER(customer_name)) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_code_unique
    ON customers(customer_code) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_customers_mobile ON customers(mobile);
CREATE INDEX IF NOT EXISTS idx_customers_pan_vat ON customers(pan_vat);
CREATE INDEX IF NOT EXISTS idx_customers_area ON customers(area_id);
CREATE INDEX IF NOT EXISTS idx_customers_route ON customers(route_id);
CREATE INDEX IF NOT EXISTS idx_customers_price_level ON customers(price_level_id);
CREATE INDEX IF NOT EXISTS idx_customers_active ON customers(is_active) WHERE is_deleted = FALSE;

-- ---------------------------------------------------------
-- SETTINGS SEED - Customer Code prefix, editable from the
-- Settings screen already built for this ERP.
-- ---------------------------------------------------------
INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order)
VALUES ('customer.code_prefix', 'CUS-', 'Customer', 'string', 'CUS-', 'Prefix used when auto-generating Customer Codes', 10)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;
