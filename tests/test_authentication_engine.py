import unittest
from unittest.mock import patch

import engines.authentication_engine as ae

FAKE_USER = {
    "userid": 1, "username": "admin", "passwordhash": "HASH", "passwordsalt": "SALT",
    "fullname": "Admin User", "roleid": 1, "status": "Active",
    "lockeduntil": None, "failedattempts": 0,
}


class TestAuthenticationEngine(unittest.TestCase):

    def test_successful_login_returns_full_context(self):
        with patch.object(ae, "get_user_by_username", return_value=FAKE_USER), \
             patch.object(ae, "auto_unlock_if_due", side_effect=lambda u: u), \
             patch.object(ae, "verify_password", return_value=True), \
             patch.object(ae, "reset_failed_attempts"), \
             patch.object(ae, "validate_license", return_value=(True, "ok")), \
             patch.object(ae, "validate_subscription", return_value=(True, "ok")), \
             patch.object(ae, "get_accessible_menus", return_value=["Dashboard"]), \
             patch.object(ae, "get_role_name", return_value="Administrator"), \
             patch.object(ae, "create_session", return_value={"sessionid": "SESSXYZ"}), \
             patch.object(ae, "write_login_history"), \
             patch.object(ae, "write_audit_log"):

            result = ae.login("admin", "correct-pass", "COM1", "FY1")

        self.assertTrue(result.success)
        self.assertEqual(result.session_id, "SESSXYZ")
        self.assertEqual(result.rolename, "Administrator")
        self.assertTrue(result.is_admin)
        self.assertIsNotNone(result.login_time)
        self.assertIsNotNone(result.machine_name)

    def test_wrong_password_registers_failed_attempt(self):
        with patch.object(ae, "get_user_by_username", return_value=FAKE_USER), \
             patch.object(ae, "auto_unlock_if_due", side_effect=lambda u: u), \
             patch.object(ae, "verify_password", return_value=False), \
             patch.object(ae, "register_failed_attempt") as mock_register, \
             patch.object(ae, "write_failed_login"):

            result = ae.login("admin", "wrong-pass", "COM1", "FY1")

        self.assertFalse(result.success)
        self.assertTrue(mock_register.called)

    def test_locked_account_never_checks_password(self):
        locked_user = dict(FAKE_USER, status="Locked")

        with patch.object(ae, "get_user_by_username", return_value=locked_user), \
             patch.object(ae, "auto_unlock_if_due", side_effect=lambda u: u), \
             patch.object(ae, "verify_password") as mock_verify, \
             patch.object(ae, "write_failed_login"):

            result = ae.login("admin", "whatever", "COM1", "FY1")

        self.assertFalse(result.success)
        self.assertFalse(mock_verify.called)

    def test_empty_input_rejected_before_any_db_call(self):
        result = ae.login("", "", "", "")
        self.assertFalse(result.success)

    def test_unexpected_exception_is_caught_and_safe(self):
        with patch.object(ae, "get_user_by_username", side_effect=RuntimeError("DB exploded")):
            result = ae.login("admin", "x", "COM1", "FY1")

        self.assertFalse(result.success)
        self.assertNotIn("DB exploded", result.message)  # never leak internals


if __name__ == "__main__":
    unittest.main()
