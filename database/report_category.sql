CREATE TABLE IF NOT EXISTS report_category (
    report_category_id    SERIAL PRIMARY KEY,
    category_code             VARCHAR(30) NOT NULL UNIQUE,   -- e.g. 'SALES', 'PURCHASE', 'STOCK_RECON'
    category_name               VARCHAR(100) NOT NULL,          -- e.g. 'Sales', 'Stock Reconciliation'
    display_order                  SMALLINT NOT NULL DEFAULT 1,
    is_active                         BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE report_category IS 'The 22 confirmed final categories (Dashboard, Sales, Purchase, Sales Return, Purchase Return, Stock, Stock Reconciliation, Customers/Receivables, Suppliers/Payables, Cash & Bank, Accounting, Tax/VAT, Profit & Margin, Pharmacy Analytics, Expiry & Loss, Item Analysis, Manufacturer Analysis, Supplier Analysis, Country Analysis, Discount & Free Quantity, Audit & Compliance, Management Reports) -- seeded once, rarely changed.';
