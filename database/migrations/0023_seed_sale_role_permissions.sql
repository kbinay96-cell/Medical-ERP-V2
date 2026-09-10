-- Migration 0023: Seed role_permissions with full access for every
-- existing role on the "Sale" screen, matching the same pattern as
-- migration 0018. Backend enforcement in sale_engine.py's
-- create_sale_invoice/cancel_sale_invoice requires this row to
-- exist for non-admin users, or they will be locked out.

INSERT INTO role_permissions (
    roleid, screenname,
    can_view, can_add, can_edit, can_delete, can_restore,
    can_print, can_export, can_import, can_approve,
    can_cancel, can_lock, can_unlock
)
SELECT
    r.roleid, s.screenname,
    TRUE, TRUE, TRUE, TRUE, TRUE,
    TRUE, TRUE, TRUE, TRUE,
    TRUE, TRUE, TRUE
FROM roles r
CROSS JOIN (VALUES
    ('Sale')
) AS s(screenname)
ON CONFLICT (roleid, screenname) DO NOTHING;