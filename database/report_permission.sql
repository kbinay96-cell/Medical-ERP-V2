CREATE TABLE IF NOT EXISTS report_permission (
    report_permission_id   SERIAL PRIMARY KEY,
    role_name                  VARCHAR(30) NOT NULL,
    permission_name               VARCHAR(50) NOT NULL,   -- 'View Sales Reports' | 'View Purchase Reports' | 'View Stock Reports' | 'View Accounts Reports' | 'View Profit Reports' | 'View Tax Reports' | 'Export Reports' | 'Print Reports' | 'View Audit Reports' | 'View Financial Statements'
    is_granted                     BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT uq_report_role_permission UNIQUE (role_name, permission_name),
    CONSTRAINT chk_report_permission_name CHECK (permission_name IN (
        'View Sales Reports', 'View Purchase Reports', 'View Stock Reports', 'View Accounts Reports',
        'View Profit Reports', 'View Tax Reports', 'Export Reports', 'Print Reports',
        'View Audit Reports', 'View Financial Statements'
    ))
);

COMMENT ON TABLE report_permission IS 'Same shape and reasoning as accounts.accounting_role_permission (Accounts Module Part 1) -- reuses the existing user/role infrastructure, adds only the reports-specific permission grid. "View Financial Statements" and "View Profit Reports" are the two gates behind report_definition.is_financial_statement, per the confirmed rule that profit/financial reports are not shown to a general user by default.';