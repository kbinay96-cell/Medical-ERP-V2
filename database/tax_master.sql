CREATE TABLE IF NOT EXISTS tax_master (
    tax_master_id             SERIAL PRIMARY KEY,
    tax_name                     VARCHAR(50) NOT NULL,      -- e.g. 'VAT 13%', 'Exempt'
    tax_rate_percent                NUMERIC(5,2) NOT NULL,
    tax_direction                     VARCHAR(10) NOT NULL,   -- 'Input' (on purchases) or 'Output' (on sales)
    account_id                          INTEGER NOT NULL REFERENCES chart_of_accounts(account_id),   -- which account this tax posts to (1500 Tax Receivable for Input, 2200 Tax Payable for Output)
    is_active                             BOOLEAN NOT NULL DEFAULT TRUE,
    remarks                                 TEXT,

    CONSTRAINT chk_tax_direction CHECK (tax_direction IN ('Input', 'Output'))
);

COMMENT ON TABLE tax_master IS 'Configurable, not hardcoded (confirmed scope). Country Tax master (already built, Sale/Purchase Module) supplies the RATE used on invoice lines; this table supplies which ACCOUNT that tax amount posts to when the Accounts Engine journals a Sale/Purchase Invoice -- two different concerns, kept in two different tables so the existing Country Tax master is never touched.';