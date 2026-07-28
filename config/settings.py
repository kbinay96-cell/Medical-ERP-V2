"""
=========================================================
Medical ERP V2
Application Configuration
---------------------------------------------------------
Purpose:
    Central place for constants used across the app.
    These defaults are also mirrored in the `settings`
    DB table (settingkey/settingvalue) so they can be
    changed later from a Settings screen without code
    changes. These Python constants are the fallback
    values used if the DB setting is missing.
=========================================================
"""

APP_NAME = "Medical ERP"
APP_VERSION = "2.0.0"
BUILD_NUMBER = "1"

# ---------------------------------------------------------
# Security defaults (overridable via `settings` table)
# ---------------------------------------------------------
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_AUTO_UNLOCK_MINUTES = 30
SESSION_TIMEOUT_MINUTES = 30
PASSWORD_EXPIRY_DAYS = 90
PASSWORD_EXPIRY_WARNING_DAYS = 15
ALLOW_MULTIPLE_LOGIN = False
PASSWORD_MIN_LENGTH = 8

# ---------------------------------------------------------
# User account statuses
# ---------------------------------------------------------
STATUS_ACTIVE = "Active"
STATUS_DISABLED = "Disabled"
STATUS_LOCKED = "Locked"
STATUS_EXPIRED = "Expired"
STATUS_SUSPENDED = "Suspended"
STATUS_DELETED = "Deleted"

VALID_USER_STATUSES = (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_LOCKED,
    STATUS_EXPIRED,
    STATUS_SUSPENDED,
    STATUS_DELETED,
)

# ---------------------------------------------------------
# Audit actions
# ---------------------------------------------------------
AUDIT_LOGIN = "Login"
AUDIT_LOGOUT = "Logout"
AUDIT_PASSWORD_CHANGED = "PasswordChanged"
AUDIT_PASSWORD_RESET = "PasswordReset"
AUDIT_USER_LOCKED = "UserLocked"
AUDIT_USER_UNLOCKED = "UserUnlocked"
AUDIT_ROLE_CHANGED = "RoleChanged"
AUDIT_PERMISSION_CHANGED = "PermissionChanged"
