-- =============================================================================
-- Medical ERP V2 - Item Master Module
-- File: database/schema_item.sql
-- Purpose: Full schema for `item` (the master record) and `item_batch`
--          (batch-wise stock/expiry), plus the Tax redesign columns.
--
-- Design notes (read before altering):
--   * BS-FIRST RULE: every audit timestamp stores BOTH the AD instant
--     (timestamptz) and the BS display string (varchar 'YYYY-MM-DD'),
--     produced by the centralized Date Engine. Same convention as
--     schema_supplier.sql / schema_simple_masters.sql.
--   * SOFT DELETE ONLY on `item` -- no DELETE FROM anywhere in the app.
--     `item_batch` rows are NOT soft-deleted individually; a batch that
--     reaches zero qty simply stops contributing to stock (it stays as a
--     historical record for audit/traceability -- exactly why Purchase
--     will insert new rows here rather than mutating old ones).
--   * STOCK IS BATCH-LEVEL, NOT ITEM-LEVEL (confirmed decision): `item`
--     itself has NO stock/qty column. Total stock for an item is always
--     SUM(item_batch.batch_qty) over its non-zero batches. This is what
--     lets each batch carry its own expiry and purchase rate -- required
--     for a Medical ERP where FIFO/expiry-wise stock movement matters.
--   * ZERO-QTY ITEM CREATION IS VALID (confirmed decision): an item can be
--     created with NO batches at all (0 total stock) -- e.g. a brand-new
--     item added to the Master before its first Purchase entry arrives.
--     There is no CHECK constraint here forcing at least one batch to
--     exist; the Engine simply never blocks a zero-batch item.
--   * EXPIRY DATE IS ALWAYS AD, MONTH/YEAR ONLY (confirmed decision) --
--     medicine packaging itself prints AD month/year (e.g. "10/2027"),
--     never a day, never BS. Modeled as expiry_year + expiry_month
--     (both INTEGER) rather than a DATE column, since there is no real
--     "day" to store and a fabricated day-of-month would be misleading
--     on reports. A generated `expiry_display` computed column gives the
--     "MM/YYYY" string directly from SQL for convenience.
--   * TAX REDESIGN (per MASTER_BLUEPRINT_ItemMaster_TaxAndDropdowns.md):
--     the old flat `tax_id` -> tax_master FK is NOT used by Item anymore.
--     tax_mode decides whether the item's effective VAT/Custom% come from
--     its Manufacturer's Country (via a future country_tax_settings table)
--     or from these four explicit columns. See engines/item_engine.py's
--     resolve_item_tax() for how tax_mode is applied -- this schema only
--     stores the raw inputs, it does not compute anything.
--   * Manufacturer, Category, Sub Category, Item Group, Unit, Generic are
--     all referenced by ID only -- their own tables/engines are entirely
--     separate modules (schema_simple_masters.sql for the first five,
--     Manufacturer's own dedicated schema for the sixth). This file does
--     NOT define or alter any of those tables.
-- =============================================================================


-- =============================================================================
-- ITEM  (the master record)
-- =============================================================================
CREATE TABLE IF NOT EXISTS item (
    item_id              SERIAL PRIMARY KEY,

    item_code            VARCHAR(20)     NOT NULL,
    item_name            VARCHAR(200)    NOT NULL,

    -- Classification (all FK to their own dedicated lookup master tables)
    category_id          INTEGER         REFERENCES category(category_id),
    sub_category_id      INTEGER         REFERENCES sub_category(sub_category_id),
    item_group_id        INTEGER         REFERENCES item_group(item_group_id),
    manufacturer_id      INTEGER,        -- FK added once Manufacturer's own table is migrated in
    generic_id           INTEGER         REFERENCES generic(generic_id),

    -- Units
    unit_id              INTEGER         NOT NULL REFERENCES unit(unit_id),
    purchase_unit_id      INTEGER        REFERENCES unit(unit_id),
    -- purchase_unit_id nullable: many items purchase and sell in the same
    -- unit, in which case the Screen defaults it to unit_id and this stays
    -- explicit rather than magically inferred at read time.

    -- Rates (per Unit, not per Purchase Unit -- conversion, if any, is a
    -- Purchase Engine concern, not an Item Master concern)
    purchase_rate        NUMERIC(18, 2)  NOT NULL DEFAULT 0,
    sale_rate             NUMERIC(18, 2) NOT NULL DEFAULT 0,
    mrp                   NUMERIC(18, 2) NOT NULL DEFAULT 0,

    -- Reorder control -- freely editable at any time (not locked after creation)
    minimum_stock        NUMERIC(18, 2)  NOT NULL DEFAULT 0,

    -- ---------------- TAX REDESIGN ----------------
    tax_mode              VARCHAR(20)    NOT NULL DEFAULT 'country_default',
    item_vat_checked      BOOLEAN        NOT NULL DEFAULT FALSE,
    item_vat_percent      NUMERIC(5, 2),
    item_custom_checked   BOOLEAN        NOT NULL DEFAULT FALSE,
    item_custom_percent   NUMERIC(5, 2),
    -- tax_id / tax_master retired for Item -- intentionally NOT a column here.

    status                VARCHAR(10)    NOT NULL DEFAULT 'Active',
    remarks                TEXT,

    is_deleted            BOOLEAN        NOT NULL DEFAULT FALSE,
    deleted_by             INTEGER,
    deleted_at_ad          TIMESTAMPTZ,
    deleted_at_bs          VARCHAR(10),

    created_by             INTEGER       NOT NULL,
    created_at_ad          TIMESTAMPTZ   NOT NULL DEFAULT now(),
    created_at_bs          VARCHAR(10)   NOT NULL,

    updated_by              INTEGER,
    updated_at_ad           TIMESTAMPTZ,
    updated_at_bs            VARCHAR(10),

    CONSTRAINT chk_item_tax_mode CHECK (tax_mode IN ('country_default', 'individual')),
    CONSTRAINT chk_item_status CHECK (status IN ('Active', 'Inactive')),
    CONSTRAINT chk_item_purchase_rate CHECK (purchase_rate >= 0),
    CONSTRAINT chk_item_sale_rate CHECK (sale_rate >= 0),
    CONSTRAINT chk_item_mrp CHECK (mrp >= 0),
    CONSTRAINT chk_item_minimum_stock CHECK (minimum_stock >= 0),
    CONSTRAINT chk_item_vat_percent CHECK (item_vat_percent IS NULL OR item_vat_percent >= 0),
    CONSTRAINT chk_item_custom_percent CHECK (item_custom_percent IS NULL OR item_custom_percent >= 0)
);

-- Uniqueness enforced only among non-deleted rows (case-insensitive on name).
CREATE UNIQUE INDEX IF NOT EXISTS uq_item_name_active
    ON item (LOWER(item_name)) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_item_code_active
    ON item (LOWER(item_code)) WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_item_category      ON item (category_id)      WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_item_sub_category  ON item (sub_category_id)  WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_item_group         ON item (item_group_id)    WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_item_manufacturer  ON item (manufacturer_id)  WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_item_generic       ON item (generic_id)       WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_item_status        ON item (status)           WHERE is_deleted = FALSE;

COMMENT ON TABLE item IS 'Item Master - Medical ERP V2. No stock column here -- stock is batch-level, see item_batch. Soft-delete only, BS-first audit trail.';
COMMENT ON COLUMN item.tax_mode IS 'country_default = resolve VAT/Custom via Manufacturer.country; individual = use item_vat_percent/item_custom_percent directly.';


-- =============================================================================
-- ITEM BATCH  (batch-wise stock + expiry -- the ONLY place quantity lives)
-- =============================================================================
CREATE TABLE IF NOT EXISTS item_batch (
    item_batch_id         SERIAL PRIMARY KEY,

    item_id               INTEGER         NOT NULL REFERENCES item(item_id),

    batch_no              VARCHAR(50)     NOT NULL,

    -- Expiry is ALWAYS AD, month/year only (confirmed) -- no day component.
    expiry_year           INTEGER         NOT NULL,
    expiry_month          INTEGER         NOT NULL,
    expiry_display        VARCHAR(7) GENERATED ALWAYS AS (
                              LPAD(expiry_month::text, 2, '0') || '/' || expiry_year::text
                          ) STORED,

    batch_qty             NUMERIC(18, 3)  NOT NULL DEFAULT 0,
    batch_purchase_rate   NUMERIC(18, 2)  NOT NULL DEFAULT 0,

    remarks               TEXT,

    -- No is_deleted here on purpose (see design notes) -- a batch's audit
    -- trail (who added it, when) is what's preserved, not a delete flag.
    created_by            INTEGER         NOT NULL,
    created_at_ad         TIMESTAMPTZ     NOT NULL DEFAULT now(),
    created_at_bs         VARCHAR(10)     NOT NULL,

    updated_by            INTEGER,
    updated_at_ad         TIMESTAMPTZ,
    updated_at_bs         VARCHAR(10),

    CONSTRAINT chk_item_batch_qty CHECK (batch_qty >= 0),
    CONSTRAINT chk_item_batch_rate CHECK (batch_purchase_rate >= 0),
    CONSTRAINT chk_item_batch_month CHECK (expiry_month BETWEEN 1 AND 12),
    CONSTRAINT chk_item_batch_year CHECK (expiry_year BETWEEN 2000 AND 2100)
);

-- A given batch_no is unique PER ITEM (the same batch number can recur
-- across different items from different manufacturers).
CREATE UNIQUE INDEX IF NOT EXISTS uq_item_batch_no_per_item
    ON item_batch (item_id, LOWER(batch_no));

CREATE INDEX IF NOT EXISTS idx_item_batch_item   ON item_batch (item_id);
CREATE INDEX IF NOT EXISTS idx_item_batch_expiry ON item_batch (expiry_year, expiry_month);

COMMENT ON TABLE item_batch IS 'Batch-wise stock + expiry for Item Master - Medical ERP V2. Total item stock = SUM(batch_qty) over an item''s rows. Populated today via Opening Stock entry on the Item Form; Purchase module will insert new rows here once built.';
COMMENT ON COLUMN item_batch.expiry_display IS 'Convenience "MM/YYYY" display string, generated from expiry_month/expiry_year -- never write to this column directly.';
