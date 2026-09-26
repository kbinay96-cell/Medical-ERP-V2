-- database/migrations/0034_reconcile_outstanding_reports.sql
-- Medical ERP V2 -- make the two "Outstanding" reports agree with the
-- Management Dashboard Receivable / Payable tiles (and with the Supplier
-- List current balance), by reading the same helper views created in 0033
-- (v_dashboard_customer_balance, v_dashboard_supplier_balance).
--
-- Supersedes the CUSTOMER_OUTSTANDING and SUPPLIER_OUTSTANDING blocks in
-- 0031_seed_reports_data.sql. If 0031 is ever re-run, re-run this file
-- afterwards. Column names, filters and drill-down settings are unchanged,
-- so columns_definition / applicable_filters stay as they are.
--
-- Idempotent: safe to re-run (plain UPDATEs). Each should report UPDATE 1.

UPDATE report_definition
   SET sql_template = $$
        SELECT c.customer_id, c.customer_name, c.credit_limit, c.credit_days,
               b.current_balance AS outstanding_amount
          FROM v_dashboard_customer_balance b
          JOIN customers c ON c.customer_id = b.customer_id
         WHERE b.current_balance > 0
           AND (%(customer_id)s IS NULL OR c.customer_id = %(customer_id)s)
         ORDER BY b.current_balance DESC;
   $$,
       remarks = 'Same logic as the Management Dashboard Receivable tile: Dr opening balance + open invoices (balance_amount minus receipts and adjusting sale returns) minus unused receipt advance. Parties with a zero or credit balance are not listed.'
 WHERE report_code = 'CUSTOMER_OUTSTANDING';

UPDATE report_definition
   SET sql_template = $$
        SELECT s.supplier_id, s.supplier_name, s.credit_limit, s.credit_days,
               b.current_balance AS outstanding_amount
          FROM v_dashboard_supplier_balance b
          JOIN supplier s ON s.supplier_id = b.supplier_id
         WHERE b.current_balance > 0
           AND (%(supplier_id)s IS NULL OR s.supplier_id = %(supplier_id)s)
         ORDER BY b.current_balance DESC;
   $$,
       remarks = 'Same logic as the Management Dashboard Payable tile and the Supplier List current balance: Cr opening balance still due + open purchase invoices (minus payments and adjusting purchase returns) minus unused payment advance. Suppliers with a zero or debit balance are not listed.'
 WHERE report_code = 'SUPPLIER_OUTSTANDING';