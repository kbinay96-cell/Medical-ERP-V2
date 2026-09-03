CREATE TABLE IF NOT EXISTS management_dashboard_widget (
    management_dashboard_widget_id  SERIAL PRIMARY KEY,
    widget_code                        VARCHAR(50) NOT NULL UNIQUE,   -- e.g. 'GROSS_PROFIT', 'TOP_SELLING_ITEMS'
    widget_name                           VARCHAR(100) NOT NULL,
    widget_type                              VARCHAR(20) NOT NULL,   -- 'KPI' | 'List' | 'Trend'
    sql_template                                TEXT NOT NULL,   -- same trusted-template rule as report_definition.sql_template
    display_order                                 SMALLINT NOT NULL DEFAULT 1,
    is_active                                        BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT chk_widget_type CHECK (widget_type IN ('KPI', 'List', 'Trend'))
);

COMMENT ON TABLE management_dashboard_widget IS 'The Reports-section landing page (distinct from Module 01''s main app Dashboard). Seeded ONLY with what is NOT already on the main Dashboard (confirmed exclusion list: Total Sales, Total Purchase, Stock Value, Low Stock, Near Expiry are already there): Gross Profit, Net Profit, Receivable, Payable, Cash, Bank, Expired Stock (KPI type); Top Selling Items, Top Profitable Items, Top Customers, Top Suppliers, Top Manufacturers, Outstanding Customers, Outstanding Suppliers (List type); Sales Trend, Purchase Trend, Profit Trend (Trend type).';