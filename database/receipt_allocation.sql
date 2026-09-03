CREATE TABLE IF NOT EXISTS receipt_allocation (
    receipt_allocation_id    SERIAL PRIMARY KEY,
    receipt_id                  INTEGER NOT NULL REFERENCES receipt(receipt_id),
    sale_invoice_id                INTEGER NOT NULL REFERENCES sale_invoice(sale_invoice_id),
    allocated_amount                  NUMERIC(14,2) NOT NULL,
    is_auto_allocated                   BOOLEAN NOT NULL DEFAULT TRUE,   -- TRUE = FIFO engine matched it, FALSE = user manually re-targeted (edit path)
    remarks                               TEXT,

    CONSTRAINT chk_receipt_allocation_positive CHECK (allocated_amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_receipt_allocation_receipt ON receipt_allocation (receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_allocation_invoice ON receipt_allocation (sale_invoice_id);

COMMENT ON COLUMN receipt_allocation.sale_invoice_id IS 'SUM(allocated_amount) across every receipt_allocation row for a given sale_invoice_id, restricted to receipts with status != Cancelled, is the total amount ever paid toward that invoice. sale_invoice.grand_total minus that sum (further reduced by any Sale Return with refund_mode=''Adjust Against Invoice'') is that invoice''s live outstanding balance -- computed live by ReceiptModel.get_outstanding_invoices_for_customer(), never stored redundantly.';