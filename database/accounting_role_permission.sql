CREATE TABLE IF NOT EXISTS accounting_role_permission (
    accounting_role_permission_id  SERIAL PRIMARY KEY,
    role_name                          VARCHAR(30) NOT NULL,   -- 'Accountant' | 'Senior Accountant' | 'Manager' | 'Admin' | 'Auditor'
    permission_name                       VARCHAR(30) NOT NULL,   -- 'Create' | 'Edit' | 'Post' | 'Cancel' | 'Reverse' | 'Approve' | 'View' | 'Export' | 'Period Unlock'
    is_granted                              BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT uq_role_permission UNIQUE (role_name, permission_name),
    CONSTRAINT chk_role_name CHECK (role_name IN ('Accountant', 'Senior Accountant', 'Manager', 'Admin', 'Auditor')),
    CONSTRAINT chk_permission_name CHECK (permission_name IN (
        'Create', 'Edit', 'Post', 'Cancel', 'Reverse', 'Approve', 'View', 'Export', 'Period Unlock'
    ))
);

COMMENT ON TABLE accounting_role_permission IS 'A simple grid lookup, reusing the existing user/role infrastructure already in the app (this table only adds the accounting-specific permission matrix on top of whatever role a user already has). The Engine checks this before allowing Cancel/Reverse/Period-Unlock actions.';