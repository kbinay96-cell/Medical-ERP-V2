BEGIN;

ALTER TABLE purchase_invoice
    ADD COLUMN IF NOT EXISTS cancellation_reason TEXT;

INSERT INTO role_permissions (
    roleid, screenname,
    can_view, can_add, can_edit, can_delete, can_restore,
    can_print, can_export, can_import, can_approve,
    can_cancel, can_lock, can_unlock
)
SELECT
    roleid, 'Purchase Invoice List',
    can_view, can_add, can_edit, can_delete, can_restore,
    can_print, can_export, can_import, can_approve,
    can_cancel, can_lock, can_unlock
FROM role_permissions
WHERE screenname = 'Purchase'
ON CONFLICT (roleid, screenname) DO NOTHING;

COMMIT;
