CREATE TABLE IF NOT EXISTS sale_item_free_scheme (
    sale_item_free_scheme_id   SERIAL PRIMARY KEY,
    item_id                    INTEGER NOT NULL REFERENCES item(item_id),
    scheme_qty                 NUMERIC(12,2) NOT NULL,
    scheme_free                NUMERIC(12,2) NOT NULL,
    is_active                  BOOLEAN NOT NULL DEFAULT TRUE,
    remarks                    TEXT,
    is_deleted                 BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                 INTEGER,
    created_at_ad              TIMESTAMPTZ DEFAULT NOW(),
    created_at_bs              VARCHAR(10),
    updated_by                 INTEGER,
    updated_at_ad              TIMESTAMPTZ DEFAULT NOW(),
    updated_at_bs              VARCHAR(10),
    deleted_by                 INTEGER,
    deleted_at_ad              TIMESTAMPTZ,
    deleted_at_bs              VARCHAR(10),

    CONSTRAINT chk_sale_item_free_scheme_qty   CHECK (scheme_qty > 0),
    CONSTRAINT chk_sale_item_free_scheme_free  CHECK (scheme_free > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sale_item_free_scheme_item_active
    ON sale_item_free_scheme (item_id)
    WHERE is_deleted = FALSE AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_sale_item_free_scheme_item
    ON sale_item_free_scheme (item_id) WHERE is_deleted = FALSE;