-- database/migrations/0031_seed_reports_data.sql
-- Medical ERP V2 -- Reports Module -- Seed Data (Batch 1)
--
-- Seeds report_category (all 22 confirmed categories) and
-- report_definition (Batch 1: only reports buildable from
-- schema-confirmed tables -- sale_invoice(+item), purchase_invoice(+item),
-- sale_return, purchase_return, customers, supplier, item, item_batch,
-- manufacturer, stock_ledger, receipt(+allocation), payment(+allocation)).
--
-- Idempotent: safe to re-run (ON CONFLICT ... DO UPDATE).
--
-- NOT included in this batch (deferred -- see chat for exact reason):
-- Accounting/Financial Statements (no journal_entry/chart_of_accounts
-- tables), Category/Generic/Sub-category/Unit-wise reports (schema
-- unverified), Sale/Purchase Return item-wise detail (sale_return_item/
-- purchase_return_item schema unverified), Purchase-side Tax (no
-- tax_amount column on purchase_invoice_item), Audit & Compliance
-- (schema unverified), Management/Dashboard KPIs
-- (management_dashboard_widget existence unverified), Pharmacy
-- Analytics (depends on generic/category, unverified).

-- ==================================================================
-- 1. report_category -- all 22 confirmed categories
-- ==================================================================
INSERT INTO report_category (category_code, category_name, display_order, is_active) VALUES
    ('DASHBOARD',        'Dashboard',                  1, TRUE),
    ('SALES',            'Sales',                      2, TRUE),
    ('PURCHASE',         'Purchase',                   3, TRUE),
    ('SALES_RETURN',     'Sales Return',               4, TRUE),
    ('PURCHASE_RETURN',  'Purchase Return',             5, TRUE),
    ('STOCK',            'Stock',                       6, TRUE),
    ('STOCK_RECON',      'Stock Reconciliation',        7, TRUE),
    ('RECEIVABLE',       'Customers/Receivables',       8, TRUE),
    ('PAYABLE',          'Suppliers/Payables',          9, TRUE),
    ('CASH_BANK',        'Cash & Bank',                10, TRUE),
    ('ACCOUNTING',       'Accounting',                 11, TRUE),
    ('TAX',              'Tax/VAT',                    12, TRUE),
    ('PROFIT',           'Profit & Margin',            13, TRUE),
    ('PHARMA_ANALYTICS', 'Pharmacy Analytics',         14, TRUE),
    ('EXPIRY_LOSS',      'Expiry & Loss',              15, TRUE),
    ('ITEM_ANALYSIS',    'Item Analysis',              16, TRUE),
    ('MFG_ANALYSIS',     'Manufacturer Analysis',      17, TRUE),
    ('SUPPLIER_ANALYSIS','Supplier Analysis',          18, TRUE),
    ('COUNTRY_ANALYSIS', 'Country Analysis',           19, TRUE),
    ('DISCOUNT_FREE',    'Discount & Free Quantity',   20, TRUE),
    ('AUDIT',            'Audit & Compliance',         21, TRUE),
    ('MANAGEMENT',       'Management Reports',         22, TRUE)
ON CONFLICT (category_code) DO UPDATE SET
    category_name = EXCLUDED.category_name,
    display_order = EXCLUDED.display_order,
    is_active     = EXCLUDED.is_active;

-- ==================================================================
-- 2. report_definition -- Batch 1 (schema-confirmed reports only)
-- ==================================================================

-- ------------------------------------------------------------------
-- SALES
-- ------------------------------------------------------------------
INSERT INTO report_definition
    (report_code, report_name, report_category_id, sql_template, applicable_filters,
     columns_definition, drill_down_report_code, drill_down_source_type,
     required_permission, is_financial_statement, is_active, remarks)
VALUES
(
    'SALES_REGISTER', 'Sales Register',
    (SELECT report_category_id FROM report_category WHERE category_code = 'SALES'),
    $$
        SELECT si.sale_invoice_id, si.invoice_number, si.invoice_date_ad,
               c.customer_name, si.payment_type, si.total_qty,
               si.total_discount_amount, si.total_tax_amount, si.grand_total,
               si.balance_amount, si.status
          FROM sale_invoice si
          JOIN customers c ON c.customer_id = si.customer_id
         WHERE si.is_deleted = FALSE
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
           AND (%(customer_id)s IS NULL OR si.customer_id = %(customer_id)s)
           AND (%(status)s IS NULL OR si.status = %(status)s)
         ORDER BY si.invoice_date_ad DESC, si.invoice_number DESC;
    $$,
    ARRAY['date_from','date_to','customer_id','status'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"payment_type","label":"Payment Mode","type":"text"},
        {"key":"total_qty","label":"Qty","type":"number"},
        {"key":"total_discount_amount","label":"Discount","type":"currency"},
        {"key":"total_tax_amount","label":"Tax","type":"currency"},
        {"key":"grand_total","label":"Grand Total","type":"currency"},
        {"key":"balance_amount","label":"Balance","type":"currency"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Sales Reports', FALSE, TRUE,
    'Header-level sales register.'
),
(
    'SALES_ITEM_WISE', 'Item-wise Sales',
    (SELECT report_category_id FROM report_category WHERE category_code = 'SALES'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, i.item_code, i.item_name,
               sii.batch_no, c.customer_name, sii.qty, sii.free_qty, sii.rate,
               sii.discount_amount, sii.tax_amount, sii.amount, si.sale_invoice_id
          FROM sale_invoice_item sii
          JOIN sale_invoice si ON si.sale_invoice_id = sii.sale_invoice_id
          JOIN item i ON i.item_id = sii.item_id
          JOIN customers c ON c.customer_id = si.customer_id
         WHERE si.is_deleted = FALSE
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
           AND (%(item_id)s IS NULL OR sii.item_id = %(item_id)s)
           AND (%(customer_id)s IS NULL OR si.customer_id = %(customer_id)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['date_from','date_to','item_id','customer_id'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"qty","label":"Qty","type":"number"},
        {"key":"free_qty","label":"Free Qty","type":"number"},
        {"key":"rate","label":"Rate","type":"currency"},
        {"key":"discount_amount","label":"Discount","type":"currency"},
        {"key":"tax_amount","label":"Tax","type":"currency"},
        {"key":"amount","label":"Amount","type":"currency"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Sales Reports', FALSE, TRUE,
    'Line-item level sales, drills into the source Sale Invoice.'
),
(
    'SALES_CUSTOMER_WISE', 'Customer-wise Sales',
    (SELECT report_category_id FROM report_category WHERE category_code = 'SALES'),
    $$
        SELECT c.customer_id, c.customer_name, COUNT(si.sale_invoice_id) AS invoice_count,
               SUM(si.total_qty) AS total_qty, SUM(si.total_discount_amount) AS total_discount,
               SUM(si.grand_total) AS total_sales
          FROM sale_invoice si
          JOIN customers c ON c.customer_id = si.customer_id
         WHERE si.is_deleted = FALSE AND si.status = 'Posted'
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
           AND (%(customer_id)s IS NULL OR si.customer_id = %(customer_id)s)
         GROUP BY c.customer_id, c.customer_name
         ORDER BY total_sales DESC;
    $$,
    ARRAY['date_from','date_to','customer_id'],
    $$[
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"invoice_count","label":"Invoices","type":"number"},
        {"key":"total_qty","label":"Qty","type":"number"},
        {"key":"total_discount","label":"Discount","type":"currency"},
        {"key":"total_sales","label":"Total Sales","type":"currency"}
    ]$$::jsonb,
    'SALES_REGISTER', NULL, 'View Sales Reports', FALSE, TRUE,
    'Drills into Sales Register pre-filtered by that customer.'
),
(
    'CASH_SALES', 'Cash Sales',
    (SELECT report_category_id FROM report_category WHERE category_code = 'SALES'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, c.customer_name, si.grand_total
          FROM sale_invoice si JOIN customers c ON c.customer_id = si.customer_id
         WHERE si.is_deleted = FALSE AND si.status = 'Posted' AND si.payment_type = 'Cash'
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['date_from','date_to'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"grand_total","label":"Amount","type":"currency"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Sales Reports', FALSE, TRUE, NULL
),
(
    'CREDIT_SALES', 'Credit Sales (Outstanding Balance)',
    (SELECT report_category_id FROM report_category WHERE category_code = 'SALES'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, c.customer_name,
               si.grand_total, si.balance_amount
          FROM sale_invoice si JOIN customers c ON c.customer_id = si.customer_id
         WHERE si.is_deleted = FALSE AND si.status = 'Posted' AND si.balance_amount > 0
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
           AND (%(customer_id)s IS NULL OR si.customer_id = %(customer_id)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['date_from','date_to','customer_id'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"grand_total","label":"Invoice Total","type":"currency"},
        {"key":"balance_amount","label":"Outstanding","type":"currency"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Sales Reports', FALSE, TRUE, NULL
),
(
    'CANCELLED_SALES', 'Cancelled Sales',
    (SELECT report_category_id FROM report_category WHERE category_code = 'SALES'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, c.customer_name,
               si.grand_total, si.cancellation_reason
          FROM sale_invoice si JOIN customers c ON c.customer_id = si.customer_id
         WHERE si.is_deleted = FALSE AND si.status = 'Cancelled'
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['date_from','date_to'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"grand_total","label":"Amount","type":"currency"},
        {"key":"cancellation_reason","label":"Reason","type":"text"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Sales Reports', FALSE, TRUE, NULL
)
ON CONFLICT (report_code) DO UPDATE SET
    report_name = EXCLUDED.report_name, sql_template = EXCLUDED.sql_template,
    applicable_filters = EXCLUDED.applicable_filters, columns_definition = EXCLUDED.columns_definition,
    drill_down_report_code = EXCLUDED.drill_down_report_code, drill_down_source_type = EXCLUDED.drill_down_source_type,
    required_permission = EXCLUDED.required_permission, is_financial_statement = EXCLUDED.is_financial_statement,
    is_active = EXCLUDED.is_active, remarks = EXCLUDED.remarks;

-- ------------------------------------------------------------------
-- PURCHASE
-- ------------------------------------------------------------------
INSERT INTO report_definition
    (report_code, report_name, report_category_id, sql_template, applicable_filters,
     columns_definition, drill_down_report_code, drill_down_source_type,
     required_permission, is_financial_statement, is_active, remarks)
VALUES
(
    'PURCHASE_REGISTER', 'Purchase Register',
    (SELECT report_category_id FROM report_category WHERE category_code = 'PURCHASE'),
    $$
        SELECT pi.purchase_invoice_id, pi.invoice_number, pi.invoice_date_ad,
               s.supplier_name, pi.total_qty, pi.total_discount_amount,
               pi.grand_total, pi.status
          FROM purchase_invoice pi
          JOIN supplier s ON s.supplier_id = pi.supplier_id
         WHERE pi.is_deleted = FALSE
           AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
           AND (%(supplier_id)s IS NULL OR pi.supplier_id = %(supplier_id)s)
           AND (%(status)s IS NULL OR pi.status = %(status)s)
         ORDER BY pi.invoice_date_ad DESC;
    $$,
    ARRAY['date_from','date_to','supplier_id','status'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"total_qty","label":"Qty","type":"number"},
        {"key":"total_discount_amount","label":"Discount","type":"currency"},
        {"key":"grand_total","label":"Grand Total","type":"currency"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, 'Purchase Invoice', 'View Purchase Reports', FALSE, TRUE, NULL
),
(
    'PURCHASE_ITEM_WISE', 'Item-wise Purchase',
    (SELECT report_category_id FROM report_category WHERE category_code = 'PURCHASE'),
    $$
        SELECT pi.invoice_date_ad, pi.invoice_number, i.item_code, i.item_name,
               pii.batch_no, s.supplier_name, pii.qty, pii.free_qty,
               pii.purchase_rate, pii.discount_amount, pii.landing_cost_per_unit,
               pi.purchase_invoice_id
          FROM purchase_invoice_item pii
          JOIN purchase_invoice pi ON pi.purchase_invoice_id = pii.purchase_invoice_id
          JOIN item i ON i.item_id = pii.item_id
          JOIN supplier s ON s.supplier_id = pi.supplier_id
         WHERE pi.is_deleted = FALSE
           AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
           AND (%(item_id)s IS NULL OR pii.item_id = %(item_id)s)
           AND (%(supplier_id)s IS NULL OR pi.supplier_id = %(supplier_id)s)
         ORDER BY pi.invoice_date_ad DESC;
    $$,
    ARRAY['date_from','date_to','item_id','supplier_id'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"qty","label":"Qty","type":"number"},
        {"key":"free_qty","label":"Free Qty","type":"number"},
        {"key":"purchase_rate","label":"Rate","type":"currency"},
        {"key":"discount_amount","label":"Discount","type":"currency"},
        {"key":"landing_cost_per_unit","label":"Landing Cost/Unit","type":"currency"}
    ]$$::jsonb,
    NULL, 'Purchase Invoice', 'View Purchase Reports', FALSE, TRUE, NULL
),
(
    'PURCHASE_SUPPLIER_WISE', 'Supplier-wise Purchase',
    (SELECT report_category_id FROM report_category WHERE category_code = 'PURCHASE'),
    $$
        SELECT s.supplier_id, s.supplier_name, COUNT(pi.purchase_invoice_id) AS invoice_count,
               SUM(pi.total_qty) AS total_qty, SUM(pi.grand_total) AS total_purchase
          FROM purchase_invoice pi JOIN supplier s ON s.supplier_id = pi.supplier_id
         WHERE pi.is_deleted = FALSE AND pi.status = 'Posted'
           AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
           AND (%(supplier_id)s IS NULL OR pi.supplier_id = %(supplier_id)s)
         GROUP BY s.supplier_id, s.supplier_name
         ORDER BY total_purchase DESC;
    $$,
    ARRAY['date_from','date_to','supplier_id'],
    $$[
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"invoice_count","label":"Invoices","type":"number"},
        {"key":"total_qty","label":"Qty","type":"number"},
        {"key":"total_purchase","label":"Total Purchase","type":"currency"}
    ]$$::jsonb,
    'PURCHASE_REGISTER', NULL, 'View Purchase Reports', FALSE, TRUE, NULL
)
ON CONFLICT (report_code) DO UPDATE SET
    report_name = EXCLUDED.report_name, sql_template = EXCLUDED.sql_template,
    applicable_filters = EXCLUDED.applicable_filters, columns_definition = EXCLUDED.columns_definition,
    drill_down_report_code = EXCLUDED.drill_down_report_code, drill_down_source_type = EXCLUDED.drill_down_source_type,
    required_permission = EXCLUDED.required_permission, is_financial_statement = EXCLUDED.is_financial_statement,
    is_active = EXCLUDED.is_active, remarks = EXCLUDED.remarks;

-- ------------------------------------------------------------------
-- SALES RETURN / PURCHASE RETURN (header-level only -- see gap note)
-- ------------------------------------------------------------------
INSERT INTO report_definition
    (report_code, report_name, report_category_id, sql_template, applicable_filters,
     columns_definition, drill_down_report_code, drill_down_source_type,
     required_permission, is_financial_statement, is_active, remarks)
VALUES
(
    'SALES_RETURN_REGISTER', 'Sales Return Register',
    (SELECT report_category_id FROM report_category WHERE category_code = 'SALES_RETURN'),
    $$
        SELECT sr.return_date_ad, sr.return_number, c.customer_name,
               si.invoice_number AS original_invoice, sr.total_qty,
               sr.grand_total, sr.refund_mode, sr.status, sr.return_reason
          FROM sale_return sr
          JOIN customers c ON c.customer_id = sr.customer_id
          JOIN sale_invoice si ON si.sale_invoice_id = sr.sale_invoice_id
         WHERE sr.is_deleted = FALSE
           AND (%(date_from)s IS NULL OR sr.return_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR sr.return_date_ad <= %(date_to)s)
           AND (%(customer_id)s IS NULL OR sr.customer_id = %(customer_id)s)
         ORDER BY sr.return_date_ad DESC;
    $$,
    ARRAY['date_from','date_to','customer_id'],
    $$[
        {"key":"return_date_ad","label":"Date","type":"date"},
        {"key":"return_number","label":"Return No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"original_invoice","label":"Original Invoice","type":"text"},
        {"key":"total_qty","label":"Qty","type":"number"},
        {"key":"grand_total","label":"Amount","type":"currency"},
        {"key":"refund_mode","label":"Refund Mode","type":"text"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, 'Sale Return', 'View Sales Reports', FALSE, TRUE,
    'Header-level only -- sale_return_item column schema not yet verified for line-item detail.'
),
(
    'PURCHASE_RETURN_REGISTER', 'Purchase Return Register',
    (SELECT report_category_id FROM report_category WHERE category_code = 'PURCHASE_RETURN'),
    $$
        SELECT pr.return_date_ad, pr.return_number, s.supplier_name,
               pi.invoice_number AS original_invoice, pr.total_qty,
               pr.grand_total, pr.settlement_mode, pr.status, pr.return_reason
          FROM purchase_return pr
          JOIN supplier s ON s.supplier_id = pr.supplier_id
          JOIN purchase_invoice pi ON pi.purchase_invoice_id = pr.purchase_invoice_id
         WHERE pr.is_deleted = FALSE
           AND (%(date_from)s IS NULL OR pr.return_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pr.return_date_ad <= %(date_to)s)
           AND (%(supplier_id)s IS NULL OR pr.supplier_id = %(supplier_id)s)
         ORDER BY pr.return_date_ad DESC;
    $$,
    ARRAY['date_from','date_to','supplier_id'],
    $$[
        {"key":"return_date_ad","label":"Date","type":"date"},
        {"key":"return_number","label":"Return No","type":"text"},
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"original_invoice","label":"Original Invoice","type":"text"},
        {"key":"total_qty","label":"Qty","type":"number"},
        {"key":"grand_total","label":"Amount","type":"currency"},
        {"key":"settlement_mode","label":"Settlement Mode","type":"text"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, 'Purchase Return', 'View Purchase Reports', FALSE, TRUE,
    'Header-level only -- purchase_return_item column schema not yet verified for line-item detail.'
)
ON CONFLICT (report_code) DO UPDATE SET
    report_name = EXCLUDED.report_name, sql_template = EXCLUDED.sql_template,
    applicable_filters = EXCLUDED.applicable_filters, columns_definition = EXCLUDED.columns_definition,
    drill_down_report_code = EXCLUDED.drill_down_report_code, drill_down_source_type = EXCLUDED.drill_down_source_type,
    required_permission = EXCLUDED.required_permission, is_financial_statement = EXCLUDED.is_financial_statement,
    is_active = EXCLUDED.is_active, remarks = EXCLUDED.remarks;

-- ------------------------------------------------------------------
-- STOCK / EXPIRY & LOSS / STOCK RECONCILIATION-adjacent
-- ------------------------------------------------------------------
INSERT INTO report_definition
    (report_code, report_name, report_category_id, sql_template, applicable_filters,
     columns_definition, drill_down_report_code, drill_down_source_type,
     required_permission, is_financial_statement, is_active, remarks)
VALUES
(
    'CURRENT_STOCK', 'Current Stock',
    (SELECT report_category_id FROM report_category WHERE category_code = 'STOCK'),
    $$
        SELECT i.item_code, i.item_name, m.manufacturer_name, ib.batch_no,
               ib.expiry_display, ib.batch_qty, ib.batch_purchase_rate,
               (ib.batch_qty * ib.batch_purchase_rate) AS stock_value, ib.item_batch_id
          FROM item_batch ib
          JOIN item i ON i.item_id = ib.item_id
          LEFT JOIN manufacturer m ON m.manufacturer_id = i.manufacturer_id
         WHERE ib.batch_qty > 0
           AND (%(item_id)s IS NULL OR ib.item_id = %(item_id)s)
           AND (%(manufacturer_id)s IS NULL OR i.manufacturer_id = %(manufacturer_id)s)
         ORDER BY i.item_name, ib.expiry_year, ib.expiry_month;
    $$,
    ARRAY['item_id','manufacturer_id'],
    $$[
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"manufacturer_name","label":"Manufacturer","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"expiry_display","label":"Expiry","type":"text"},
        {"key":"batch_qty","label":"Qty","type":"number"},
        {"key":"batch_purchase_rate","label":"Purchase Rate","type":"currency"},
        {"key":"stock_value","label":"Stock Value","type":"currency"}
    ]$$::jsonb,
    NULL, NULL, 'View Stock Reports', FALSE, TRUE, NULL
),
(
    'ZERO_STOCK', 'Zero Stock Batches',
    (SELECT report_category_id FROM report_category WHERE category_code = 'STOCK'),
    $$
        SELECT i.item_code, i.item_name, ib.batch_no, ib.expiry_display, ib.batch_qty
          FROM item_batch ib JOIN item i ON i.item_id = ib.item_id
         WHERE ib.batch_qty = 0
           AND (%(item_id)s IS NULL OR ib.item_id = %(item_id)s)
         ORDER BY i.item_name;
    $$,
    ARRAY['item_id'],
    $$[
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"expiry_display","label":"Expiry","type":"text"},
        {"key":"batch_qty","label":"Qty","type":"number"}
    ]$$::jsonb,
    NULL, NULL, 'View Stock Reports', FALSE, TRUE, NULL
),
(
    'LOW_STOCK', 'Low Stock (Below Minimum)',
    (SELECT report_category_id FROM report_category WHERE category_code = 'STOCK'),
    $$
        SELECT i.item_code, i.item_name, i.minimum_stock,
               COALESCE(SUM(ib.batch_qty), 0) AS current_stock
          FROM item i
          LEFT JOIN item_batch ib ON ib.item_id = i.item_id
         WHERE i.is_deleted = FALSE AND i.status = 'Active'
           AND (%(item_id)s IS NULL OR i.item_id = %(item_id)s)
         GROUP BY i.item_id, i.item_code, i.item_name, i.minimum_stock
        HAVING COALESCE(SUM(ib.batch_qty), 0) <= i.minimum_stock
         ORDER BY i.item_name;
    $$,
    ARRAY['item_id'],
    $$[
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"minimum_stock","label":"Min Stock","type":"number"},
        {"key":"current_stock","label":"Current Stock","type":"number"}
    ]$$::jsonb,
    NULL, NULL, 'View Stock Reports', FALSE, TRUE, NULL
),
(
    'STOCK_LEDGER', 'Stock Ledger',
    (SELECT report_category_id FROM report_category WHERE category_code = 'STOCK'),
    $$
        SELECT sl.created_at_ad, i.item_code, i.item_name, ib.batch_no,
               sl.transaction_type, sl.quantity_change, sl.balance_after,
               sl.reference_type, sl.reference_id
          FROM stock_ledger sl
          JOIN item i ON i.item_id = sl.item_id
          JOIN item_batch ib ON ib.item_batch_id = sl.item_batch_id
         WHERE (%(date_from)s IS NULL OR sl.created_at_ad::date >= %(date_from)s)
           AND (%(date_to)s IS NULL OR sl.created_at_ad::date <= %(date_to)s)
           AND (%(item_id)s IS NULL OR sl.item_id = %(item_id)s)
         ORDER BY sl.created_at_ad DESC;
    $$,
    ARRAY['date_from','date_to','item_id'],
    $$[
        {"key":"created_at_ad","label":"Date/Time","type":"text"},
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"transaction_type","label":"Type","type":"text"},
        {"key":"quantity_change","label":"Qty Change","type":"number"},
        {"key":"balance_after","label":"Balance","type":"number"},
        {"key":"reference_type","label":"Ref Type","type":"text"}
    ]$$::jsonb,
    NULL, NULL, 'View Stock Reports', FALSE, TRUE,
    'transaction_type currently uses only PURCHASE/ADJUSTMENT/SALE in live data; 6 values allowed by CHECK constraint (also SALE_RETURN/PURCHASE_RETURN/OPENING).'
),
(
    'STOCK_ADJUSTMENT_REPORT', 'Stock Adjustments',
    (SELECT report_category_id FROM report_category WHERE category_code = 'STOCK'),
    $$
        SELECT sl.created_at_ad, i.item_code, i.item_name, ib.batch_no,
               sl.quantity_change, sl.balance_after, sl.remarks
          FROM stock_ledger sl
          JOIN item i ON i.item_id = sl.item_id
          JOIN item_batch ib ON ib.item_batch_id = sl.item_batch_id
         WHERE sl.transaction_type = 'ADJUSTMENT'
           AND (%(date_from)s IS NULL OR sl.created_at_ad::date >= %(date_from)s)
           AND (%(date_to)s IS NULL OR sl.created_at_ad::date <= %(date_to)s)
           AND (%(item_id)s IS NULL OR sl.item_id = %(item_id)s)
         ORDER BY sl.created_at_ad DESC;
    $$,
    ARRAY['date_from','date_to','item_id'],
    $$[
        {"key":"created_at_ad","label":"Date/Time","type":"text"},
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"quantity_change","label":"Qty Change","type":"number"},
        {"key":"balance_after","label":"Balance","type":"number"},
        {"key":"remarks","label":"Remarks","type":"text"}
    ]$$::jsonb,
    'STOCK_LEDGER', NULL, 'View Stock Reports', FALSE, TRUE, NULL
),
(
    'EXPIRED_ITEMS', 'Expired Items',
    (SELECT report_category_id FROM report_category WHERE category_code = 'EXPIRY_LOSS'),
    $$
        SELECT i.item_code, i.item_name, ib.batch_no, ib.expiry_display,
               ib.batch_qty, ib.batch_purchase_rate,
               (ib.batch_qty * ib.batch_purchase_rate) AS loss_value
          FROM item_batch ib JOIN item i ON i.item_id = ib.item_id
         WHERE ib.batch_qty > 0
           AND make_date(ib.expiry_year, ib.expiry_month, 1) + INTERVAL '1 month' <= CURRENT_DATE
           AND (%(item_id)s IS NULL OR ib.item_id = %(item_id)s)
         ORDER BY ib.expiry_year, ib.expiry_month;
    $$,
    ARRAY['item_id'],
    $$[
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"expiry_display","label":"Expiry","type":"text"},
        {"key":"batch_qty","label":"Qty","type":"number"},
        {"key":"batch_purchase_rate","label":"Purchase Rate","type":"currency"},
        {"key":"loss_value","label":"Loss Value","type":"currency"}
    ]$$::jsonb,
    NULL, NULL, 'View Stock Reports', FALSE, TRUE, NULL
),
(
    'NEAR_EXPIRY', 'Near Expiry (Next 90 Days)',
    (SELECT report_category_id FROM report_category WHERE category_code = 'EXPIRY_LOSS'),
    $$
        SELECT i.item_code, i.item_name, ib.batch_no, ib.expiry_display, ib.batch_qty
          FROM item_batch ib JOIN item i ON i.item_id = ib.item_id
         WHERE ib.batch_qty > 0
           AND make_date(ib.expiry_year, ib.expiry_month, 1) + INTERVAL '1 month'
               BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days'
           AND (%(item_id)s IS NULL OR ib.item_id = %(item_id)s)
         ORDER BY ib.expiry_year, ib.expiry_month;
    $$,
    ARRAY['item_id'],
    $$[
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"expiry_display","label":"Expiry","type":"text"},
        {"key":"batch_qty","label":"Qty","type":"number"}
    ]$$::jsonb,
    NULL, NULL, 'View Stock Reports', FALSE, TRUE, NULL
)
ON CONFLICT (report_code) DO UPDATE SET
    report_name = EXCLUDED.report_name, sql_template = EXCLUDED.sql_template,
    applicable_filters = EXCLUDED.applicable_filters, columns_definition = EXCLUDED.columns_definition,
    drill_down_report_code = EXCLUDED.drill_down_report_code, drill_down_source_type = EXCLUDED.drill_down_source_type,
    required_permission = EXCLUDED.required_permission, is_financial_statement = EXCLUDED.is_financial_statement,
    is_active = EXCLUDED.is_active, remarks = EXCLUDED.remarks;

-- ------------------------------------------------------------------
-- ITEM ANALYSIS -- including the requested Item Transaction History
-- ------------------------------------------------------------------
INSERT INTO report_definition
    (report_code, report_name, report_category_id, sql_template, applicable_filters,
     columns_definition, drill_down_report_code, drill_down_source_type,
     required_permission, is_financial_statement, is_active, remarks)
VALUES
(
    'ITEM_MASTER_REPORT', 'Item Master',
    (SELECT report_category_id FROM report_category WHERE category_code = 'ITEM_ANALYSIS'),
    $$
        SELECT i.item_code, i.item_name, m.manufacturer_name, i.purchase_rate,
               i.sale_rate, i.mrp, i.minimum_stock, i.status
          FROM item i
          LEFT JOIN manufacturer m ON m.manufacturer_id = i.manufacturer_id
         WHERE i.is_deleted = FALSE
           AND (%(item_id)s IS NULL OR i.item_id = %(item_id)s)
           AND (%(manufacturer_id)s IS NULL OR i.manufacturer_id = %(manufacturer_id)s)
         ORDER BY i.item_name;
    $$,
    ARRAY['item_id','manufacturer_id'],
    $$[
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"manufacturer_name","label":"Manufacturer","type":"text"},
        {"key":"purchase_rate","label":"Purchase Rate","type":"currency"},
        {"key":"sale_rate","label":"Sale Rate","type":"currency"},
        {"key":"mrp","label":"MRP","type":"currency"},
        {"key":"minimum_stock","label":"Min Stock","type":"number"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, NULL, 'View Stock Reports', FALSE, TRUE,
    'Category/Generic/Unit names omitted -- those lookup tables'' schema not yet verified.'
),
(
    -- Must-answer: "Which supplier supplied this item? On which dates? How much qty? At what rate? Which batch?"
    'ITEM_SUPPLIER_PURCHASE_HISTORY', 'Item Purchase History by Supplier',
    (SELECT report_category_id FROM report_category WHERE category_code = 'ITEM_ANALYSIS'),
    $$
        SELECT pi.invoice_date_ad, pi.invoice_number, s.supplier_name,
               i.item_code, i.item_name, m.manufacturer_name, pii.batch_no,
               pii.qty, pii.free_qty, pii.purchase_rate, pii.discount_amount,
               pi.purchase_invoice_id
          FROM purchase_invoice_item pii
          JOIN purchase_invoice pi ON pi.purchase_invoice_id = pii.purchase_invoice_id
          JOIN supplier s ON s.supplier_id = pi.supplier_id
          JOIN item i ON i.item_id = pii.item_id
          LEFT JOIN manufacturer m ON m.manufacturer_id = i.manufacturer_id
         WHERE pi.is_deleted = FALSE
           AND (%(item_id)s IS NULL OR pii.item_id = %(item_id)s)
           AND (%(supplier_id)s IS NULL OR pi.supplier_id = %(supplier_id)s)
           AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
         ORDER BY pi.invoice_date_ad DESC;
    $$,
    ARRAY['item_id','supplier_id','date_from','date_to'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"manufacturer_name","label":"Manufacturer","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"qty","label":"Qty","type":"number"},
        {"key":"free_qty","label":"Free Qty","type":"number"},
        {"key":"purchase_rate","label":"Rate","type":"currency"},
        {"key":"discount_amount","label":"Discount","type":"currency"}
    ]$$::jsonb,
    NULL, 'Purchase Invoice', 'View Purchase Reports', FALSE, TRUE,
    'Answers: which supplier/date/qty/rate/batch this item arrived on.'
),
(
    -- Must-answer: "How much manufacturer-wise stock was received? Which supplier supplied stock from each manufacturer?"
    'ITEM_MANUFACTURER_SUPPLIER_TRACE', 'Manufacturer-Supplier Traceability',
    (SELECT report_category_id FROM report_category WHERE category_code = 'ITEM_ANALYSIS'),
    $$
        SELECT m.manufacturer_name, s.supplier_name, i.item_name,
               SUM(pii.qty) AS received_qty, SUM(pii.free_qty) AS free_qty,
               SUM(pii.qty * pii.purchase_rate) AS purchase_value
          FROM purchase_invoice_item pii
          JOIN purchase_invoice pi ON pi.purchase_invoice_id = pii.purchase_invoice_id
          JOIN supplier s ON s.supplier_id = pi.supplier_id
          JOIN item i ON i.item_id = pii.item_id
          LEFT JOIN manufacturer m ON m.manufacturer_id = i.manufacturer_id
         WHERE pi.is_deleted = FALSE
           AND (%(manufacturer_id)s IS NULL OR i.manufacturer_id = %(manufacturer_id)s)
           AND (%(supplier_id)s IS NULL OR pi.supplier_id = %(supplier_id)s)
           AND (%(item_id)s IS NULL OR pii.item_id = %(item_id)s)
           AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
         GROUP BY m.manufacturer_name, s.supplier_name, i.item_name
         ORDER BY m.manufacturer_name, s.supplier_name;
    $$,
    ARRAY['manufacturer_id','supplier_id','item_id','date_from','date_to'],
    $$[
        {"key":"manufacturer_name","label":"Manufacturer","type":"text"},
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"received_qty","label":"Received Qty","type":"number"},
        {"key":"free_qty","label":"Free Qty","type":"number"},
        {"key":"purchase_value","label":"Purchase Value","type":"currency"}
    ]$$::jsonb,
    'ITEM_SUPPLIER_PURCHASE_HISTORY', NULL, 'View Purchase Reports', FALSE, TRUE,
    'Answers JSON blueprint''s manufacturer_supplier_traceability example: how much of Manufacturer X came from Supplier Y.'
),
(
    -- Must-answer: "Which batch did it arrive in? What is remaining stock from each batch?"
    'ITEM_BATCH_PURCHASE_HISTORY', 'Item Batch Purchase & Remaining Stock',
    (SELECT report_category_id FROM report_category WHERE category_code = 'ITEM_ANALYSIS'),
    $$
        SELECT i.item_code, i.item_name, ib.batch_no, ib.expiry_display,
               pi.invoice_date_ad, pi.invoice_number, s.supplier_name,
               pii.qty AS received_qty, pii.purchase_rate, ib.batch_qty AS remaining_qty
          FROM item_batch ib
          JOIN item i ON i.item_id = ib.item_id
          LEFT JOIN purchase_invoice_item pii ON pii.item_batch_id = ib.item_batch_id
          LEFT JOIN purchase_invoice pi ON pi.purchase_invoice_id = pii.purchase_invoice_id
          LEFT JOIN supplier s ON s.supplier_id = pi.supplier_id
         WHERE (%(item_id)s IS NULL OR ib.item_id = %(item_id)s)
           AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
         ORDER BY i.item_name, ib.expiry_year, ib.expiry_month;
    $$,
    ARRAY['item_id','date_from','date_to'],
    $$[
        {"key":"item_code","label":"Item Code","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"expiry_display","label":"Expiry","type":"text"},
        {"key":"invoice_date_ad","label":"Purchase Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"received_qty","label":"Received Qty","type":"number"},
        {"key":"purchase_rate","label":"Purchase Rate","type":"currency"},
        {"key":"remaining_qty","label":"Remaining Qty","type":"number"}
    ]$$::jsonb,
    NULL, 'Purchase Invoice', 'View Stock Reports', FALSE, TRUE, NULL
),
(
    -- Must-answer: "Which customers purchased? On which dates? How much qty? Which invoice? Which batch?"
    'ITEM_CUSTOMER_SALES_HISTORY', 'Item Sales History by Customer',
    (SELECT report_category_id FROM report_category WHERE category_code = 'ITEM_ANALYSIS'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, c.customer_name,
               i.item_code, i.item_name, sii.batch_no, sii.qty, sii.free_qty,
               sii.rate, si.sale_invoice_id
          FROM sale_invoice_item sii
          JOIN sale_invoice si ON si.sale_invoice_id = sii.sale_invoice_id
          JOIN customers c ON c.customer_id = si.customer_id
          JOIN item i ON i.item_id = sii.item_id
         WHERE si.is_deleted = FALSE
           AND (%(item_id)s IS NULL OR sii.item_id = %(item_id)s)
           AND (%(customer_id)s IS NULL OR si.customer_id = %(customer_id)s)
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['item_id','customer_id','date_from','date_to'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"qty","label":"Qty","type":"number"},
        {"key":"free_qty","label":"Free Qty","type":"number"},
        {"key":"rate","label":"Rate","type":"currency"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Sales Reports', FALSE, TRUE, NULL
)
ON CONFLICT (report_code) DO UPDATE SET
    report_name = EXCLUDED.report_name, sql_template = EXCLUDED.sql_template,
    applicable_filters = EXCLUDED.applicable_filters, columns_definition = EXCLUDED.columns_definition,
    drill_down_report_code = EXCLUDED.drill_down_report_code, drill_down_source_type = EXCLUDED.drill_down_source_type,
    required_permission = EXCLUDED.required_permission, is_financial_statement = EXCLUDED.is_financial_statement,
    is_active = EXCLUDED.is_active, remarks = EXCLUDED.remarks;

-- ------------------------------------------------------------------
-- MANUFACTURER ANALYSIS / COUNTRY ANALYSIS
-- ------------------------------------------------------------------
INSERT INTO report_definition
    (report_code, report_name, report_category_id, sql_template, applicable_filters,
     columns_definition, drill_down_report_code, drill_down_source_type,
     required_permission, is_financial_statement, is_active, remarks)
VALUES
(
    'MFG_WISE_PURCHASE', 'Manufacturer-wise Purchase',
    (SELECT report_category_id FROM report_category WHERE category_code = 'MFG_ANALYSIS'),
    $$
        SELECT m.manufacturer_name, m.country, SUM(pii.qty) AS total_qty,
               SUM(pii.qty * pii.purchase_rate) AS total_value
          FROM purchase_invoice_item pii
          JOIN purchase_invoice pi ON pi.purchase_invoice_id = pii.purchase_invoice_id
          JOIN item i ON i.item_id = pii.item_id
          LEFT JOIN manufacturer m ON m.manufacturer_id = i.manufacturer_id
         WHERE pi.is_deleted = FALSE
           AND (%(manufacturer_id)s IS NULL OR i.manufacturer_id = %(manufacturer_id)s)
           AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
         GROUP BY m.manufacturer_name, m.country
         ORDER BY total_value DESC;
    $$,
    ARRAY['manufacturer_id','date_from','date_to'],
    $$[
        {"key":"manufacturer_name","label":"Manufacturer","type":"text"},
        {"key":"country","label":"Country","type":"text"},
        {"key":"total_qty","label":"Qty","type":"number"},
        {"key":"total_value","label":"Purchase Value","type":"currency"}
    ]$$::jsonb,
    'ITEM_SUPPLIER_PURCHASE_HISTORY', NULL, 'View Purchase Reports', FALSE, TRUE, NULL
),
(
    'COUNTRY_WISE_PURCHASE', 'Country-wise Purchase (by Manufacturer Origin)',
    (SELECT report_category_id FROM report_category WHERE category_code = 'COUNTRY_ANALYSIS'),
    $$
        SELECT m.country, SUM(pii.qty) AS total_qty,
               SUM(pii.qty * pii.purchase_rate) AS total_value
          FROM purchase_invoice_item pii
          JOIN purchase_invoice pi ON pi.purchase_invoice_id = pii.purchase_invoice_id
          JOIN item i ON i.item_id = pii.item_id
          LEFT JOIN manufacturer m ON m.manufacturer_id = i.manufacturer_id
         WHERE pi.is_deleted = FALSE AND m.country IS NOT NULL
           AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
         GROUP BY m.country
         ORDER BY total_value DESC;
    $$,
    ARRAY['date_from','date_to'],
    $$[
        {"key":"country","label":"Country","type":"text"},
        {"key":"total_qty","label":"Qty","type":"number"},
        {"key":"total_value","label":"Purchase Value","type":"currency"}
    ]$$::jsonb,
    'MFG_WISE_PURCHASE', NULL, 'View Purchase Reports', FALSE, TRUE, NULL
)
ON CONFLICT (report_code) DO UPDATE SET
    report_name = EXCLUDED.report_name, sql_template = EXCLUDED.sql_template,
    applicable_filters = EXCLUDED.applicable_filters, columns_definition = EXCLUDED.columns_definition,
    drill_down_report_code = EXCLUDED.drill_down_report_code, drill_down_source_type = EXCLUDED.drill_down_source_type,
    required_permission = EXCLUDED.required_permission, is_financial_statement = EXCLUDED.is_financial_statement,
    is_active = EXCLUDED.is_active, remarks = EXCLUDED.remarks;

-- ------------------------------------------------------------------
-- RECEIVABLE / PAYABLE / CASH & BANK
-- ------------------------------------------------------------------
INSERT INTO report_definition
    (report_code, report_name, report_category_id, sql_template, applicable_filters,
     columns_definition, drill_down_report_code, drill_down_source_type,
     required_permission, is_financial_statement, is_active, remarks)
VALUES
(
    'CUSTOMER_OUTSTANDING', 'Customer Outstanding',
    (SELECT report_category_id FROM report_category WHERE category_code = 'RECEIVABLE'),
    $$
        SELECT c.customer_id, c.customer_name, c.credit_limit, c.credit_days,
               COALESCE(SUM(si.balance_amount), 0) AS outstanding_amount
          FROM customers c
          LEFT JOIN sale_invoice si ON si.customer_id = c.customer_id
               AND si.is_deleted = FALSE AND si.status = 'Posted' AND si.balance_amount > 0
         WHERE c.is_deleted = FALSE
           AND (%(customer_id)s IS NULL OR c.customer_id = %(customer_id)s)
         GROUP BY c.customer_id, c.customer_name, c.credit_limit, c.credit_days
        HAVING COALESCE(SUM(si.balance_amount), 0) > 0
         ORDER BY outstanding_amount DESC;
    $$,
    ARRAY['customer_id'],
    $$[
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"credit_limit","label":"Credit Limit","type":"currency"},
        {"key":"credit_days","label":"Credit Days","type":"number"},
        {"key":"outstanding_amount","label":"Outstanding","type":"currency"}
    ]$$::jsonb,
    'CREDIT_SALES', NULL, 'View Accounts Reports', FALSE, TRUE, NULL
),
(
    'CUSTOMER_RECEIPT_HISTORY', 'Customer Receipt History',
    (SELECT report_category_id FROM report_category WHERE category_code = 'RECEIVABLE'),
    $$
        SELECT r.receipt_date_ad, r.receipt_number, c.customer_name,
               r.payment_mode, r.amount, r.allocated_amount, r.advance_amount, r.status
          FROM receipt r JOIN customers c ON c.customer_id = r.customer_id
         WHERE r.is_deleted = FALSE
           AND (%(customer_id)s IS NULL OR r.customer_id = %(customer_id)s)
           AND (%(date_from)s IS NULL OR r.receipt_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR r.receipt_date_ad <= %(date_to)s)
         ORDER BY r.receipt_date_ad DESC;
    $$,
    ARRAY['customer_id','date_from','date_to'],
    $$[
        {"key":"receipt_date_ad","label":"Date","type":"date"},
        {"key":"receipt_number","label":"Receipt No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"payment_mode","label":"Mode","type":"text"},
        {"key":"amount","label":"Amount","type":"currency"},
        {"key":"allocated_amount","label":"Allocated","type":"currency"},
        {"key":"advance_amount","label":"Advance","type":"currency"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, 'Receipt', 'View Accounts Reports', FALSE, TRUE, NULL
),
(
    'SUPPLIER_OUTSTANDING', 'Supplier Outstanding',
    (SELECT report_category_id FROM report_category WHERE category_code = 'PAYABLE'),
    $$
        SELECT s.supplier_id, s.supplier_name, s.credit_limit, s.credit_days,
               COALESCE(SUM(pi.grand_total), 0) - COALESCE(pa_sum.total_allocated, 0) AS outstanding_amount
          FROM supplier s
          LEFT JOIN purchase_invoice pi ON pi.supplier_id = s.supplier_id
               AND pi.is_deleted = FALSE AND pi.status = 'Posted'
          LEFT JOIN (
              SELECT pi2.supplier_id, SUM(pa.allocated_amount) AS total_allocated
                FROM payment_allocation pa
                JOIN purchase_invoice pi2 ON pi2.purchase_invoice_id = pa.purchase_invoice_id
                JOIN payment p ON p.payment_id = pa.payment_id
               WHERE p.status != 'Cancelled'
               GROUP BY pi2.supplier_id
          ) pa_sum ON pa_sum.supplier_id = s.supplier_id
         WHERE s.is_deleted = FALSE
           AND (%(supplier_id)s IS NULL OR s.supplier_id = %(supplier_id)s)
         GROUP BY s.supplier_id, s.supplier_name, s.credit_limit, s.credit_days, pa_sum.total_allocated
        HAVING COALESCE(SUM(pi.grand_total), 0) - COALESCE(pa_sum.total_allocated, 0) > 0
         ORDER BY outstanding_amount DESC;
    $$,
    ARRAY['supplier_id'],
    $$[
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"credit_limit","label":"Credit Limit","type":"currency"},
        {"key":"credit_days","label":"Credit Days","type":"number"},
        {"key":"outstanding_amount","label":"Outstanding","type":"currency"}
    ]$$::jsonb,
    'PURCHASE_REGISTER', NULL, 'View Accounts Reports', FALSE, TRUE,
    'Simplified vs the full reconciliation check in ReportEngine.check_payable_exception (no return-adjustment offset here); this is a display report, that is the audit check.'
),
(
    'SUPPLIER_PAYMENT_HISTORY', 'Supplier Payment History',
    (SELECT report_category_id FROM report_category WHERE category_code = 'PAYABLE'),
    $$
        SELECT p.payment_date_ad, p.payment_number, s.supplier_name,
               p.payment_mode, p.amount, p.allocated_amount, p.advance_amount, p.status
          FROM payment p JOIN supplier s ON s.supplier_id = p.supplier_id
         WHERE p.is_deleted = FALSE
           AND (%(supplier_id)s IS NULL OR p.supplier_id = %(supplier_id)s)
           AND (%(date_from)s IS NULL OR p.payment_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR p.payment_date_ad <= %(date_to)s)
         ORDER BY p.payment_date_ad DESC;
    $$,
    ARRAY['supplier_id','date_from','date_to'],
    $$[
        {"key":"payment_date_ad","label":"Date","type":"date"},
        {"key":"payment_number","label":"Payment No","type":"text"},
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"payment_mode","label":"Mode","type":"text"},
        {"key":"amount","label":"Amount","type":"currency"},
        {"key":"allocated_amount","label":"Allocated","type":"currency"},
        {"key":"advance_amount","label":"Advance","type":"currency"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, 'Payment', 'View Accounts Reports', FALSE, TRUE, NULL
),
(
    'CASH_BANK_RECEIPT_REGISTER', 'Receipt Register (Cash & Bank)',
    (SELECT report_category_id FROM report_category WHERE category_code = 'CASH_BANK'),
    $$
        SELECT r.receipt_date_ad, r.receipt_number, c.customer_name,
               r.payment_mode, r.amount, r.status
          FROM receipt r JOIN customers c ON c.customer_id = r.customer_id
         WHERE r.is_deleted = FALSE
           AND (%(payment_mode)s IS NULL OR r.payment_mode = %(payment_mode)s)
           AND (%(date_from)s IS NULL OR r.receipt_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR r.receipt_date_ad <= %(date_to)s)
         ORDER BY r.receipt_date_ad DESC;
    $$,
    ARRAY['payment_mode','date_from','date_to'],
    $$[
        {"key":"receipt_date_ad","label":"Date","type":"date"},
        {"key":"receipt_number","label":"Receipt No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"payment_mode","label":"Mode","type":"text"},
        {"key":"amount","label":"Amount","type":"currency"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, 'Receipt', 'View Accounts Reports', FALSE, TRUE, NULL
),
(
    'CASH_BANK_PAYMENT_REGISTER', 'Payment Register (Cash & Bank)',
    (SELECT report_category_id FROM report_category WHERE category_code = 'CASH_BANK'),
    $$
        SELECT p.payment_date_ad, p.payment_number, s.supplier_name,
               p.payment_mode, p.amount, p.status
          FROM payment p JOIN supplier s ON s.supplier_id = p.supplier_id
         WHERE p.is_deleted = FALSE
           AND (%(payment_mode)s IS NULL OR p.payment_mode = %(payment_mode)s)
           AND (%(date_from)s IS NULL OR p.payment_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR p.payment_date_ad <= %(date_to)s)
         ORDER BY p.payment_date_ad DESC;
    $$,
    ARRAY['payment_mode','date_from','date_to'],
    $$[
        {"key":"payment_date_ad","label":"Date","type":"date"},
        {"key":"payment_number","label":"Payment No","type":"text"},
        {"key":"supplier_name","label":"Supplier","type":"text"},
        {"key":"payment_mode","label":"Mode","type":"text"},
        {"key":"amount","label":"Amount","type":"currency"},
        {"key":"status","label":"Status","type":"text"}
    ]$$::jsonb,
    NULL, 'Payment', 'View Accounts Reports', FALSE, TRUE, NULL
)
ON CONFLICT (report_code) DO UPDATE SET
    report_name = EXCLUDED.report_name, sql_template = EXCLUDED.sql_template,
    applicable_filters = EXCLUDED.applicable_filters, columns_definition = EXCLUDED.columns_definition,
    drill_down_report_code = EXCLUDED.drill_down_report_code, drill_down_source_type = EXCLUDED.drill_down_source_type,
    required_permission = EXCLUDED.required_permission, is_financial_statement = EXCLUDED.is_financial_statement,
    is_active = EXCLUDED.is_active, remarks = EXCLUDED.remarks;

-- ------------------------------------------------------------------
-- TAX/VAT (sales-side only -- see gap note) / DISCOUNT & FREE QTY /
-- PROFIT & MARGIN (batch-matched, gated as financial statement)
-- ------------------------------------------------------------------
INSERT INTO report_definition
    (report_code, report_name, report_category_id, sql_template, applicable_filters,
     columns_definition, drill_down_report_code, drill_down_source_type,
     required_permission, is_financial_statement, is_active, remarks)
VALUES
(
    'SALES_TAX_SUMMARY', 'Sales Tax Summary',
    (SELECT report_category_id FROM report_category WHERE category_code = 'TAX'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, c.customer_name,
               si.total_gross_amount, si.total_tax_amount, si.grand_total
          FROM sale_invoice si JOIN customers c ON c.customer_id = si.customer_id
         WHERE si.is_deleted = FALSE AND si.status = 'Posted' AND si.total_tax_amount > 0
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['date_from','date_to'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"total_gross_amount","label":"Gross Amount","type":"currency"},
        {"key":"total_tax_amount","label":"Tax Amount","type":"currency"},
        {"key":"grand_total","label":"Grand Total","type":"currency"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Tax Reports', FALSE, TRUE,
    'Sales-side only -- purchase_invoice_item has no tax_amount/tax_percent column in this schema.'
),
(
    'SALES_DISCOUNT_REPORT', 'Sales Discount Report',
    (SELECT report_category_id FROM report_category WHERE category_code = 'DISCOUNT_FREE'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, c.customer_name,
               si.total_discount_amount, si.bill_discount_amount, si.bill_discount_percent
          FROM sale_invoice si JOIN customers c ON c.customer_id = si.customer_id
         WHERE si.is_deleted = FALSE AND si.status = 'Posted'
           AND (si.total_discount_amount > 0 OR si.bill_discount_amount > 0)
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['date_from','date_to'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"customer_name","label":"Customer","type":"text"},
        {"key":"total_discount_amount","label":"Line Discount","type":"currency"},
        {"key":"bill_discount_amount","label":"Bill Discount","type":"currency"},
        {"key":"bill_discount_percent","label":"Bill Discount %","type":"number"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Sales Reports', FALSE, TRUE, NULL
),
(
    'FREE_QUANTITY_REPORT', 'Free Quantity Given (Sales)',
    (SELECT report_category_id FROM report_category WHERE category_code = 'DISCOUNT_FREE'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, i.item_name, sii.batch_no,
               sii.qty, sii.free_qty, c.customer_name
          FROM sale_invoice_item sii
          JOIN sale_invoice si ON si.sale_invoice_id = sii.sale_invoice_id
          JOIN customers c ON c.customer_id = si.customer_id
          JOIN item i ON i.item_id = sii.item_id
         WHERE si.is_deleted = FALSE AND sii.free_qty > 0
           AND (%(item_id)s IS NULL OR sii.item_id = %(item_id)s)
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['item_id','date_from','date_to'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"qty","label":"Paid Qty","type":"number"},
        {"key":"free_qty","label":"Free Qty","type":"number"},
        {"key":"customer_name","label":"Customer","type":"text"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Sales Reports', FALSE, TRUE, NULL
),
(
    -- Profit computed by matching each sold batch back to its purchase rate --
    -- gated as financial statement per project rule ("normal user ko automatically nahi dikhna").
    'SALES_PROFIT_BY_BATCH', 'Sales Profit (Batch-matched)',
    (SELECT report_category_id FROM report_category WHERE category_code = 'PROFIT'),
    $$
        SELECT si.invoice_date_ad, si.invoice_number, i.item_name, sii.batch_no,
               sii.qty, sii.rate AS sale_rate, pur.avg_purchase_rate,
               (sii.rate - COALESCE(pur.avg_purchase_rate, 0)) * sii.qty AS profit_amount
          FROM sale_invoice_item sii
          JOIN sale_invoice si ON si.sale_invoice_id = sii.sale_invoice_id
          JOIN item i ON i.item_id = sii.item_id
          LEFT JOIN (
              SELECT item_batch_id, AVG(purchase_rate) AS avg_purchase_rate
                FROM purchase_invoice_item GROUP BY item_batch_id
          ) pur ON pur.item_batch_id = sii.item_batch_id
         WHERE si.is_deleted = FALSE AND si.status = 'Posted'
           AND (%(item_id)s IS NULL OR sii.item_id = %(item_id)s)
           AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
           AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
         ORDER BY si.invoice_date_ad DESC;
    $$,
    ARRAY['item_id','date_from','date_to'],
    $$[
        {"key":"invoice_date_ad","label":"Date","type":"date"},
        {"key":"invoice_number","label":"Invoice No","type":"text"},
        {"key":"item_name","label":"Item","type":"text"},
        {"key":"batch_no","label":"Batch","type":"text"},
        {"key":"qty","label":"Qty","type":"number"},
        {"key":"sale_rate","label":"Sale Rate","type":"currency"},
        {"key":"avg_purchase_rate","label":"Avg Purchase Rate","type":"currency"},
        {"key":"profit_amount","label":"Profit","type":"currency"}
    ]$$::jsonb,
    NULL, 'Sale Invoice', 'View Profit Reports', TRUE, TRUE,
    'Approximation: averages purchase_rate across all purchase_invoice_item rows for that item_batch_id, since a batch could theoretically be replenished at different rates. is_financial_statement=TRUE per confirmed rule that profit reports are gated.'
)
ON CONFLICT (report_code) DO UPDATE SET
    report_name = EXCLUDED.report_name, sql_template = EXCLUDED.sql_template,
    applicable_filters = EXCLUDED.applicable_filters, columns_definition = EXCLUDED.columns_definition,
    drill_down_report_code = EXCLUDED.drill_down_report_code, drill_down_source_type = EXCLUDED.drill_down_source_type,
    required_permission = EXCLUDED.required_permission, is_financial_statement = EXCLUDED.is_financial_statement,
    is_active = EXCLUDED.is_active, remarks = EXCLUDED.remarks;