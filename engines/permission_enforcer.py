"""
=========================================================
Medical ERP V2
Permission Enforcer
---------------------------------------------------------
Central helper for backend (engine-level) permission
enforcement. Wraps authorization_engine.has_permission()
with the CURRENT logged-in user's role (from session_manager)
plus an admin bypass, so engines can guard save/update/delete
calls without each one re-implementing role lookups.

No UI code here, no SQL beyond what authorization_engine
already does.
=========================================================
"""

from engines import session_manager
from engines.authorization_engine import has_permission
from engines.exceptions import EngineError


class PermissionDeniedError(EngineError):
    """Raised when the current user lacks a required permission."""
    def __init__(self, screenname: str, action: str):
        self.screenname = screenname
        self.action = action
        super().__init__(f"You do not have permission to do this on '{screenname}'.")


def check_permission(screenname: str, action: str) -> None:
    """
    Raises PermissionDeniedError if the current logged-in user's
    role does not have `action` on `screenname`. Admins bypass
    all checks (mirrors the existing admin bypass already used
    for menu-building in dashboard_engine.build_dashboard()).
    """
    if session_manager.is_current_user_admin():
        return

    roleid = session_manager.get_current_roleid()
    if roleid is None:
        raise PermissionDeniedError(screenname, action)

    if not has_permission(roleid, screenname, action):
        raise PermissionDeniedError(screenname, action)


def user_has_permission(screenname: str, action: str) -> bool:
    """
    Non-raising version - True/False. Useful for UI code that
    wants to enable/disable a button rather than catch an
    exception.
    """
    if session_manager.is_current_user_admin():
        return True
    roleid = session_manager.get_current_roleid()
    if roleid is None:
        return False
    return has_permission(roleid, screenname, action)