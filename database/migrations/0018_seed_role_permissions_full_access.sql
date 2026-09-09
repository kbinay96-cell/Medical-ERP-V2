-- Migration 0018: Seed role_permissions with full access for every
-- existing role, on the 6 screens we're wiring backend enforcement
-- for right now. This is a deliberate "everyone gets everything"
-- starting point (per user decision) so the app keeps working the
-- moment engine-level checks go live -- fine-tune per-role later
-- via a proper Permission Management screen.

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
    ('Item'),
    ('Supplier'),
    ('Company'),
    ('Purchase'),
    ('Purchase Order'),
    ('User Master')
) AS s(screenname)
ON CONFLICT (roleid, screenname) DO NOTHING;