CREATE TABLE IF NOT EXISTS report_definition (
    report_definition_id   SERIAL PRIMARY KEY,
    report_code                VARCHAR(50) NOT NULL UNIQUE,     -- e.g. 'SALES_ITEM_WISE', 'TRIAL_BALANCE'
    report_name                   VARCHAR(150) NOT NULL,           -- display name, e.g. 'Item-wise Sales'
    report_category_id               INTEGER NOT NULL REFERENCES report_category(report_category_id),
    sql_template                        TEXT NOT NULL,   -- SELECT-only, named %(placeholder)s params for every applicable filter -- see 2.1 security note
    applicable_filters                    TEXT[] NOT NULL DEFAULT '{}',   -- subset of the fixed standard filter list, e.g. ARRAY['financial_year','date_from','date_to','customer_id']
    columns_definition                      JSONB NOT NULL,   -- [{"key": "item_name", "label": "Item", "type": "text"}, {"key": "total_qty", "label": "Qty", "type": "number"}, ...]
    drill_down_report_code                    VARCHAR(50) REFERENCES report_definition(report_code),   -- another report to open on row click, nullable
    drill_down_source_type                      VARCHAR(30),   -- e.g. 'Sale Invoice' -- opens that source document's own detail screen instead, nullable
    required_permission                           VARCHAR(50) NOT NULL,   -- e.g. 'View Sales Reports' -- checked against report_permission
    is_financial_statement                          BOOLEAN NOT NULL DEFAULT FALSE,   -- TRUE for P&L/Balance Sheet/Trial Balance -- gated extra strictly (confirmed: "Profit/financial reports normal user ko automatically nahi dikhenge")
    is_active                                         BOOLEAN NOT NULL DEFAULT TRUE,
    remarks                                             TEXT,

    CONSTRAINT chk_report_drill_down_exclusive CHECK (
        drill_down_report_code IS NULL OR drill_down_source_type IS NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_report_def_category ON report_definition (report_category_id) WHERE is_active = TRUE;

COMMENT ON COLUMN report_definition.sql_template IS 'A SELECT-only query written by the developer at definition time (trusted, not user input) using named %(placeholder)s params matching entries in applicable_filters -- e.g. "...WHERE si.invoice_date_ad BETWEEN %(date_from)s AND %(date_to)s AND (%(customer_id)s IS NULL OR si.customer_id = %(customer_id)s)...". The Engine (Part 2) NEVER string-concatenates a filter VALUE into this template -- values are always bound as query parameters via psycopg2, exactly like every other Model in this project. The template TEXT itself is data-as-config (like auto_accounting_rule), not end-user input, so it carries no injection risk as long as report_definition rows are only ever added/edited by a developer/DBA, never exposed to an end-user input form.';
COMMENT ON COLUMN report_definition.drill_down_report_code IS 'Mutually exclusive with drill_down_source_type (enforced by chk_report_drill_down_exclusive) -- a summary report either opens ANOTHER summary report (e.g. P&L -> Customer-wise Sales) or opens a specific source document type''s own existing detail screen (e.g. Sales by Invoice -> that Sale Invoice''s View screen), never both.';