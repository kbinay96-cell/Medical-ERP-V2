-- Migration 0020: Create password_reset_requests table.
-- Supports the zero-cost WhatsApp deep-link + admin-approval
-- forgot-password flow: user requests a reset from the login
-- screen, a 6-digit code is generated and shown to them via a
-- prefilled wa.me link they send to the admin's WhatsApp from
-- their own phone (human verification), and an admin approves
-- the request from a new "Password Reset Requests" screen,
-- which issues a temporary password (mustchangepassword=TRUE).
--
-- NOTE: temppassword is stored briefly in plaintext so the admin
-- can view+relay it. Same accepted-risk precedent as
-- smtp.app_password (0008) -- flagging now, encrypt-at-rest is a
-- separate future follow-up if needed.

CREATE TABLE IF NOT EXISTS password_reset_requests (
    requestid       BIGSERIAL PRIMARY KEY,
    userid          INTEGER NOT NULL REFERENCES users(userid),
    username        VARCHAR(50) NOT NULL,
    requestcode     VARCHAR(6)  NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'Pending',
    createdat       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expiresat       TIMESTAMP NOT NULL,
    approvedby      VARCHAR(50),
    approvedat      TIMESTAMP,
    temppassword    VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_pwd_reset_req_user   ON password_reset_requests(userid);
CREATE INDEX IF NOT EXISTS idx_pwd_reset_req_status ON password_reset_requests(status);

INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order) VALUES
    ('admin.whatsapp_number', '', 'User & Security', 'string', '', 'Admin WhatsApp number (with country code, digits only) that forgot-password requests are sent to', 50)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;