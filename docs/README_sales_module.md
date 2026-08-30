# Sales & Stock — schema apply order

Stock tables already exist in this repo. Sales invoice tables did **not**;
`schema_sale_return.sql` already FKs `sale_invoice` / `sale_invoice_item`,
so apply **0009 before any sale-return script**.

## Ordered apply (psql)

Run against `medical_erp_v2` after auth + masters:

```
1.  database/schema_calendar.sql
2.  database/schema_auth.sql
3.  database/schema_company.sql          (if used)
4.  database/schema_supplier.sql
5.  database/schema_manufacturer.sql
6.  database/schema_simple_masters.sql
7.  database/schema_item.sql             -- item + item_batch (current stock)
8.  database/schema_stock_ledger.sql     -- canonical movement history (ItemEngine)
9.  database/schema_customer.sql
10. database/0004_create_country_tax.sql
11. database/0005_create_supplier_manufacturer_discount.sql
12. database/0007_purchase_schema.sql
13. database/migrations/0008_purchase_invoice_enhancements.sql
14. database/0009_sale_schema.sql        -- THIS MODULE (sale_invoice + lines)
15. database/schema_sale_return.sql      -- only after 0009
16. database/schema_sale_return_item.sql
17. database/0010_payment_receipt_schema.sql   -- Accounts (next)
```

Do **not** treat `0006_create_stock_transaction.sql` as the live ledger.
`ItemEngine.post_stock_movement()` writes **`stock_ledger`** and updates
`item_batch.batch_qty` in the same transaction. `stock_transaction` is a
legacy parallel table used only by opening-stock `add_batch()`.

Example:

```
psql -U postgres -d medical_erp_v2 -f database/0009_sale_schema.sql
```
