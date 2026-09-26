-- database/migrations/0032_seed_report_permissions.sql
-- Medical ERP V2 -- Reports Module -- Role Permission Seed
--
-- Administrator bypasses this table entirely (engines/report_engine.py's
-- session_manager.is_current_user_admin() check) -- seeded here too only
-- for consistency/display purposes, not because it's load-bearing.
--
-- Access matrix below is a SENSIBLE DEFAULT based on each role's name/
-- purpose -- a business-policy decision, not a verified requirement.
-- Adjust any row via UPDATE report_permission SET is_granted = ...
-- WHERE role_name = '...' AND permission_name = '...'; at any time.
--
-- Idempotent -- safe to re-run.

INSERT INTO report_permission (role_name, permission_name, is_granted) VALUES
-- ------------------------------------------------------------------
-- Administrator -- full access (redundant with the is_admin bypass,
-- kept for display/consistency in any future Role Permission screen)
-- ------------------------------------------------------------------
('Administrator', 'View Sales Reports',       TRUE),
('Administrator', 'View Purchase Reports',    TRUE),
('Administrator', 'View Stock Reports',       TRUE),
('Administrator', 'View Accounts Reports',    TRUE),
('Administrator', 'View Profit Reports',      TRUE),
('Administrator', 'View Tax Reports',         TRUE),
('Administrator', 'Export Reports',           TRUE),
('Administrator', 'Print Reports',            TRUE),
('Administrator', 'View Audit Reports',       TRUE),
('Administrator', 'View Financial Statements',TRUE),

-- ------------------------------------------------------------------
-- Owner -- same as Administrator, full visibility into the business
-- ------------------------------------------------------------------
('Owner', 'View Sales Reports',        TRUE),
('Owner', 'View Purchase Reports',     TRUE),
('Owner', 'View Stock Reports',        TRUE),
('Owner', 'View Accounts Reports',     TRUE),
('Owner', 'View Profit Reports',       TRUE),
('Owner', 'View Tax Reports',          TRUE),
('Owner', 'Export Reports',            TRUE),
('Owner', 'Print Reports',             TRUE),
('Owner', 'View Audit Reports',        TRUE),
('Owner', 'View Financial Statements', TRUE),

-- ------------------------------------------------------------------
-- Manager -- broad operational access, excludes Audit trail specifically
-- ------------------------------------------------------------------
('Manager', 'View Sales Reports',        TRUE),
('Manager', 'View Purchase Reports',     TRUE),
('Manager', 'View Stock Reports',        TRUE),
('Manager', 'View Accounts Reports',     TRUE),
('Manager', 'View Profit Reports',       TRUE),
('Manager', 'View Tax Reports',          TRUE),
('Manager', 'Export Reports',            TRUE),
('Manager', 'Print Reports',             TRUE),
('Manager', 'View Audit Reports',        FALSE),
('Manager', 'View Financial Statements', TRUE),

-- ------------------------------------------------------------------
-- Accountant -- accounting/finance-focused
-- ------------------------------------------------------------------
('Accountant', 'View Sales Reports',        TRUE),
('Accountant', 'View Purchase Reports',     TRUE),
('Accountant', 'View Stock Reports',        FALSE),
('Accountant', 'View Accounts Reports',     TRUE),
('Accountant', 'View Profit Reports',       TRUE),
('Accountant', 'View Tax Reports',          TRUE),
('Accountant', 'Export Reports',            TRUE),
('Accountant', 'Print Reports',             TRUE),
('Accountant', 'View Audit Reports',        FALSE),
('Accountant', 'View Financial Statements', TRUE),

-- ------------------------------------------------------------------
-- Cashier -- day-to-day sales/cash only, no financial visibility
-- ------------------------------------------------------------------
('Cashier', 'View Sales Reports',        TRUE),
('Cashier', 'View Purchase Reports',     FALSE),
('Cashier', 'View Stock Reports',        FALSE),
('Cashier', 'View Accounts Reports',     FALSE),
('Cashier', 'View Profit Reports',       FALSE),
('Cashier', 'View Tax Reports',          FALSE),
('Cashier', 'Export Reports',            FALSE),
('Cashier', 'Print Reports',             TRUE),
('Cashier', 'View Audit Reports',        FALSE),
('Cashier', 'View Financial Statements', FALSE),

-- ------------------------------------------------------------------
-- Pharmacist -- stock/expiry-focused (item dispensing context)
-- ------------------------------------------------------------------
('Pharmacist', 'View Sales Reports',        TRUE),
('Pharmacist', 'View Purchase Reports',     FALSE),
('Pharmacist', 'View Stock Reports',        TRUE),
('Pharmacist', 'View Accounts Reports',     FALSE),
('Pharmacist', 'View Profit Reports',       FALSE),
('Pharmacist', 'View Tax Reports',          FALSE),
('Pharmacist', 'Export Reports',            FALSE),
('Pharmacist', 'Print Reports',             TRUE),
('Pharmacist', 'View Audit Reports',        FALSE),
('Pharmacist', 'View Financial Statements', FALSE),

-- ------------------------------------------------------------------
-- Purchase Officer -- purchase/stock-focused
-- ------------------------------------------------------------------
('Purchase Officer', 'View Sales Reports',        FALSE),
('Purchase Officer', 'View Purchase Reports',     TRUE),
('Purchase Officer', 'View Stock Reports',        TRUE),
('Purchase Officer', 'View Accounts Reports',     FALSE),
('Purchase Officer', 'View Profit Reports',       FALSE),
('Purchase Officer', 'View Tax Reports',          FALSE),
('Purchase Officer', 'Export Reports',            TRUE),
('Purchase Officer', 'Print Reports',             TRUE),
('Purchase Officer', 'View Audit Reports',        FALSE),
('Purchase Officer', 'View Financial Statements', FALSE),

-- ------------------------------------------------------------------
-- Sales Officer -- sales-focused
-- ------------------------------------------------------------------
('Sales Officer', 'View Sales Reports',        TRUE),
('Sales Officer', 'View Purchase Reports',     FALSE),
('Sales Officer', 'View Stock Reports',        FALSE),
('Sales Officer', 'View Accounts Reports',     FALSE),
('Sales Officer', 'View Profit Reports',       FALSE),
('Sales Officer', 'View Tax Reports',          FALSE),
('Sales Officer', 'Export Reports',            TRUE),
('Sales Officer', 'Print Reports',             TRUE),
('Sales Officer', 'View Audit Reports',        FALSE),
('Sales Officer', 'View Financial Statements', FALSE),

-- ------------------------------------------------------------------
-- Store Keeper -- stock-only
-- ------------------------------------------------------------------
('Store Keeper', 'View Sales Reports',        FALSE),
('Store Keeper', 'View Purchase Reports',     FALSE),
('Store Keeper', 'View Stock Reports',        TRUE),
('Store Keeper', 'View Accounts Reports',     FALSE),
('Store Keeper', 'View Profit Reports',       FALSE),
('Store Keeper', 'View Tax Reports',          FALSE),
('Store Keeper', 'Export Reports',            FALSE),
('Store Keeper', 'Print Reports',             TRUE),
('Store Keeper', 'View Audit Reports',        FALSE),
('Store Keeper', 'View Financial Statements', FALSE),

-- ------------------------------------------------------------------
-- Auditor -- audit/compliance + read access to everything for review,
-- but not necessarily export (auditors typically review, not extract)
-- ------------------------------------------------------------------
('Auditor', 'View Sales Reports',        TRUE),
('Auditor', 'View Purchase Reports',     TRUE),
('Auditor', 'View Stock Reports',        TRUE),
('Auditor', 'View Accounts Reports',     TRUE),
('Auditor', 'View Profit Reports',       TRUE),
('Auditor', 'View Tax Reports',          TRUE),
('Auditor', 'Export Reports',            FALSE),
('Auditor', 'Print Reports',             TRUE),
('Auditor', 'View Audit Reports',        TRUE),
('Auditor', 'View Financial Statements', TRUE)

ON CONFLICT (role_name, permission_name) DO UPDATE SET
    is_granted = EXCLUDED.is_granted;