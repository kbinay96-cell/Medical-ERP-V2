-- database/migrations/0033_seed_management_dashboard_widgets.sql
-- Medical ERP V2 -- Management Dashboard widgets (Batch 1)
--
-- Only widgets computable from ALREADY-LIVE schema. Gross Profit, Net
-- Profit, Cash, Bank KPIs are DEFERRED -- they need chart_of_accounts/
-- journal_entry (Accounts module, not started).
--
-- Receivable/Payable use two helper views that mirror the app's own
-- current-balance logic (PaymentModel.get_current_balance_map() for
-- suppliers; the Receipt-side equivalent for customers).
--
-- Idempotent: safe to re-run (CREATE OR REPLACE VIEW, ON CONFLICT ... DO UPDATE).

CREATE OR REPLACE VIEW v_dashboard_supplier_balance AS
WITH ob AS (
    SELECT s.supplier_id,
           CASE WHEN s.balance_type = 'Cr'
                THEN s.opening_balance - COALESCE(oba_sum.total_allocated, 0)
                ELSE 0
           END AS ob_outstanding
    FROM supplier s
    LEFT JOIN (
        SELECT oba.supplier_id, SUM(oba.allocated_amount) AS total_allocated
        FROM payment_opening_balance_allocation oba
        JOIN payment p ON p.payment_id = oba.payment_id
        WHERE p.status != 'Cancelled' AND p.is_deleted = FALSE
        GROUP BY oba.supplier_id
    ) oba_sum ON oba_sum.supplier_id = s.supplier_id
),
inv AS (
    SELECT sub.supplier_id, SUM(sub.outstanding_amount) AS inv_outstanding
    FROM (
        SELECT pi.supplier_id,
               pi.grand_total
                   - COALESCE(pa_sum.total_allocated, 0)
                   - COALESCE(pr_sum.total_adjusted, 0) AS outstanding_amount
        FROM purchase_invoice pi
        LEFT JOIN (
            SELECT pa.purchase_invoice_id, SUM(pa.allocated_amount) AS total_allocated
            FROM payment_allocation pa
            JOIN payment p ON p.payment_id = pa.payment_id
            WHERE p.status != 'Cancelled' AND p.is_deleted = FALSE
            GROUP BY pa.purchase_invoice_id
        ) pa_sum ON pa_sum.purchase_invoice_id = pi.purchase_invoice_id
        LEFT JOIN (
            SELECT pr.purchase_invoice_id, SUM(pr.grand_total) AS total_adjusted
            FROM purchase_return pr
            WHERE pr.settlement_mode = 'Adjust Against Payable'
              AND pr.status != 'Cancelled' AND pr.is_deleted = FALSE
            GROUP BY pr.purchase_invoice_id
        ) pr_sum ON pr_sum.purchase_invoice_id = pi.purchase_invoice_id
        WHERE pi.status = 'Posted' AND pi.is_deleted = FALSE
    ) sub
    WHERE sub.outstanding_amount > 0
    GROUP BY sub.supplier_id
),
adv AS (
    SELECT sub.supplier_id, SUM(sub.remaining_advance) AS advance_available
    FROM (
        SELECT p.supplier_id,
               p.advance_amount - COALESCE(au_sum.total_used, 0) AS remaining_advance
        FROM payment p
        LEFT JOIN (
            SELECT payment_id, SUM(used_amount) AS total_used
            FROM payment_advance_usage
            GROUP BY payment_id
        ) au_sum ON au_sum.payment_id = p.payment_id
        WHERE p.status != 'Cancelled' AND p.is_deleted = FALSE
          AND p.advance_amount > 0
    ) sub
    WHERE sub.remaining_advance > 0
    GROUP BY sub.supplier_id
)
SELECT s.supplier_id, s.supplier_name,
       COALESCE(ob.ob_outstanding, 0)
           + COALESCE(inv.inv_outstanding, 0)
           - COALESCE(adv.advance_available, 0) AS current_balance
FROM supplier s
LEFT JOIN ob ON ob.supplier_id = s.supplier_id
LEFT JOIN inv ON inv.supplier_id = s.supplier_id
LEFT JOIN adv ON adv.supplier_id = s.supplier_id
WHERE s.is_deleted = FALSE;


CREATE OR REPLACE VIEW v_dashboard_customer_balance AS
WITH ob AS (
    SELECT c.customer_id,
           CASE WHEN c.balance_type = 'Dr' THEN c.opening_balance ELSE 0 END AS ob_outstanding
    FROM customers c
),
inv AS (
    SELECT sub.customer_id, SUM(sub.outstanding_amount) AS inv_outstanding
    FROM (
        SELECT si.customer_id,
               si.balance_amount
                   - COALESCE(ra_sum.total_allocated, 0)
                   - COALESCE(sr_sum.total_adjusted, 0) AS outstanding_amount
        FROM sale_invoice si
        LEFT JOIN (
            SELECT ra.sale_invoice_id, SUM(ra.allocated_amount) AS total_allocated
            FROM receipt_allocation ra
            JOIN receipt r ON r.receipt_id = ra.receipt_id
            WHERE r.status != 'Cancelled' AND r.is_deleted = FALSE
            GROUP BY ra.sale_invoice_id
        ) ra_sum ON ra_sum.sale_invoice_id = si.sale_invoice_id
        LEFT JOIN (
            SELECT sr.sale_invoice_id, SUM(sr.grand_total) AS total_adjusted
            FROM sale_return sr
            WHERE sr.refund_mode = 'Adjust Against Invoice'
              AND sr.status != 'Cancelled' AND sr.is_deleted = FALSE
            GROUP BY sr.sale_invoice_id
        ) sr_sum ON sr_sum.sale_invoice_id = si.sale_invoice_id
        WHERE si.status = 'Posted' AND si.is_deleted = FALSE
    ) sub
    WHERE sub.outstanding_amount > 0
    GROUP BY sub.customer_id
),
adv AS (
    SELECT sub.customer_id, SUM(sub.remaining_advance) AS advance_available
    FROM (
        SELECT r.customer_id,
               r.advance_amount - COALESCE(au_sum.total_used, 0) AS remaining_advance
        FROM receipt r
        LEFT JOIN (
            SELECT receipt_id, SUM(used_amount) AS total_used
            FROM receipt_advance_usage
            GROUP BY receipt_id
        ) au_sum ON au_sum.receipt_id = r.receipt_id
        WHERE r.status != 'Cancelled' AND r.is_deleted = FALSE
          AND r.advance_amount > 0
    ) sub
    WHERE sub.remaining_advance > 0
    GROUP BY sub.customer_id
)
SELECT c.customer_id, c.customer_name,
       COALESCE(ob.ob_outstanding, 0)
           + COALESCE(inv.inv_outstanding, 0)
           - COALESCE(adv.advance_available, 0) AS current_balance
FROM customers c
LEFT JOIN ob ON ob.customer_id = c.customer_id
LEFT JOIN inv ON inv.customer_id = c.customer_id
LEFT JOIN adv ON adv.customer_id = c.customer_id
WHERE c.is_deleted = FALSE;


INSERT INTO management_dashboard_widget
    (widget_code, widget_name, widget_type, sql_template, display_order, is_active)
VALUES
(
    'RECEIVABLE', 'Receivable', 'KPI',
    $$
        SELECT COALESCE(SUM(GREATEST(current_balance, 0)), 0) AS value
        FROM v_dashboard_customer_balance;
    $$,
    1, TRUE
),
(
    'PAYABLE', 'Payable', 'KPI',
    $$
        SELECT COALESCE(SUM(GREATEST(current_balance, 0)), 0) AS value
        FROM v_dashboard_supplier_balance;
    $$,
    2, TRUE
),
(
    'EXPIRED_STOCK_VALUE', 'Expired Stock', 'KPI',
    $$
        SELECT COALESCE(SUM(ib.batch_qty * ib.batch_purchase_rate), 0) AS value
        FROM item_batch ib
        WHERE ib.batch_qty > 0
          AND make_date(ib.expiry_year, ib.expiry_month, 1) + INTERVAL '1 month' <= CURRENT_DATE;
    $$,
    3, TRUE
),
(
    'TOP_SELLING_ITEMS', 'Top Selling Items', 'List',
    $$
        SELECT i.item_name, SUM(sii.qty) AS total_qty, SUM(sii.amount) AS total_value
        FROM sale_invoice_item sii
        JOIN sale_invoice si ON si.sale_invoice_id = sii.sale_invoice_id
        JOIN item i ON i.item_id = sii.item_id
        WHERE si.is_deleted = FALSE AND si.status = 'Posted'
          AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
          AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
        GROUP BY i.item_id, i.item_name
        ORDER BY total_qty DESC
        LIMIT 10;
    $$,
    4, TRUE
),
(
    'TOP_PROFITABLE_ITEMS', 'Top Profitable Items', 'List',
    $$
        SELECT i.item_name,
               SUM(sii.amount + sii.cc_amount)
                 - SUM((sii.qty + sii.free_qty) * COALESCE(ib.batch_purchase_rate, 0)) AS profit_estimate
        FROM sale_invoice_item sii
        JOIN sale_invoice si ON si.sale_invoice_id = sii.sale_invoice_id
        JOIN item i ON i.item_id = sii.item_id
        LEFT JOIN item_batch ib ON ib.item_batch_id = sii.item_batch_id
        WHERE si.is_deleted = FALSE AND si.status = 'Posted'
          AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
          AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
        GROUP BY i.item_id, i.item_name
        ORDER BY profit_estimate DESC
        LIMIT 10;
    $$,
    5, TRUE
),
(
    'TOP_CUSTOMERS', 'Top Customers', 'List',
    $$
        SELECT c.customer_name, COUNT(si.sale_invoice_id) AS bill_count,
               COALESCE(SUM(si.grand_total), 0) AS total_sales
        FROM customers c
        JOIN sale_invoice si ON si.customer_id = c.customer_id
          AND si.is_deleted = FALSE AND si.status = 'Posted'
          AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
          AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
        WHERE c.is_deleted = FALSE
        GROUP BY c.customer_id, c.customer_name
        ORDER BY total_sales DESC
        LIMIT 10;
    $$,
    6, TRUE
),
(
    'TOP_SUPPLIERS', 'Top Suppliers', 'List',
    $$
        SELECT s.supplier_name, COUNT(pi.purchase_invoice_id) AS bill_count,
               COALESCE(SUM(pi.grand_total), 0) AS total_purchase
        FROM supplier s
        JOIN purchase_invoice pi ON pi.supplier_id = s.supplier_id
          AND pi.is_deleted = FALSE AND pi.status = 'Posted'
          AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
          AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
        WHERE s.is_deleted = FALSE
        GROUP BY s.supplier_id, s.supplier_name
        ORDER BY total_purchase DESC
        LIMIT 10;
    $$,
    7, TRUE
),
(
    'OUTSTANDING_CUSTOMERS', 'Outstanding Customers', 'List',
    $$
        SELECT customer_name, current_balance AS outstanding_amount
        FROM v_dashboard_customer_balance
        WHERE current_balance > 0
        ORDER BY current_balance DESC
        LIMIT 10;
    $$,
    8, TRUE
),
(
    'OUTSTANDING_SUPPLIERS', 'Outstanding Suppliers', 'List',
    $$
        SELECT supplier_name, current_balance AS outstanding_amount
        FROM v_dashboard_supplier_balance
        WHERE current_balance > 0
        ORDER BY current_balance DESC
        LIMIT 10;
    $$,
    9, TRUE
),
(
    'TOP_MANUFACTURERS', 'Top Manufacturers', 'List',
    $$
        SELECT m.manufacturer_name, SUM(pii.qty * pii.purchase_rate) AS total_value
        FROM purchase_invoice_item pii
        JOIN purchase_invoice pi ON pi.purchase_invoice_id = pii.purchase_invoice_id
        JOIN item i ON i.item_id = pii.item_id
        JOIN manufacturer m ON m.manufacturer_id = i.manufacturer_id
        WHERE pi.is_deleted = FALSE AND pi.status = 'Posted'
          AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
          AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
        GROUP BY m.manufacturer_id, m.manufacturer_name
        ORDER BY total_value DESC
        LIMIT 10;
    $$,
    10, TRUE
),
(
    'SALES_TREND', 'Sales Trend', 'Trend',
    $$
        SELECT TO_CHAR(si.invoice_date_ad, 'YYYY-MM') AS period, SUM(si.grand_total) AS value
        FROM sale_invoice si
        WHERE si.is_deleted = FALSE AND si.status = 'Posted'
          AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
          AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
        GROUP BY period
        ORDER BY period;
    $$,
    11, TRUE
),
(
    'PURCHASE_TREND', 'Purchase Trend', 'Trend',
    $$
        SELECT TO_CHAR(pi.invoice_date_ad, 'YYYY-MM') AS period, SUM(pi.grand_total) AS value
        FROM purchase_invoice pi
        WHERE pi.is_deleted = FALSE AND pi.status = 'Posted'
          AND (%(date_from)s IS NULL OR pi.invoice_date_ad >= %(date_from)s)
          AND (%(date_to)s IS NULL OR pi.invoice_date_ad <= %(date_to)s)
        GROUP BY period
        ORDER BY period;
    $$,
    12, TRUE
),
(
    'PROFIT_TREND', 'Profit Trend (Estimate)', 'Trend',
    $$
        SELECT TO_CHAR(si.invoice_date_ad, 'YYYY-MM') AS period,
               SUM(sii.amount + sii.cc_amount)
                 - SUM((sii.qty + sii.free_qty) * COALESCE(ib.batch_purchase_rate, 0)) AS value
        FROM sale_invoice_item sii
        JOIN sale_invoice si ON si.sale_invoice_id = sii.sale_invoice_id
        LEFT JOIN item_batch ib ON ib.item_batch_id = sii.item_batch_id
        WHERE si.is_deleted = FALSE AND si.status = 'Posted'
          AND (%(date_from)s IS NULL OR si.invoice_date_ad >= %(date_from)s)
          AND (%(date_to)s IS NULL OR si.invoice_date_ad <= %(date_to)s)
        GROUP BY period
        ORDER BY period;
    $$,
    13, TRUE
)
ON CONFLICT (widget_code) DO UPDATE SET
    widget_name = EXCLUDED.widget_name, widget_type = EXCLUDED.widget_type,
    sql_template = EXCLUDED.sql_template, display_order = EXCLUDED.display_order,
    is_active = EXCLUDED.is_active;