import unittest
from unittest.mock import patch

import engines.bootstrap_engine as be
from engines.exceptions import ValidationError


class TestCreateFirstCompanyAndAdmin(unittest.TestCase):

    def _patch_is_bootstrap_needed(self, needed=True):
        return patch.object(be, "is_bootstrap_needed", return_value=needed)

    def test_blocked_when_setup_already_completed(self):
        with self._patch_is_bootstrap_needed(needed=False):
            with self.assertRaises(ValidationError):
                be.create_first_company_and_admin(
                    "Test Pharmacy", "2082/83", "2082-01-01", "2083-01-01",
                    "admin", "Passw0rd!", "Admin User",
                )

    def test_missing_required_fields_rejected_without_touching_db(self):
        with self._patch_is_bootstrap_needed(needed=True), \
             patch.object(be, "company_model") as mock_company:
            with self.assertRaises(ValidationError):
                be.create_first_company_and_admin("", "", "", "", "", "", "")
        mock_company.insert_company.assert_not_called()

    def test_successful_setup_creates_company_fy_and_admin_in_order(self):
        with self._patch_is_bootstrap_needed(needed=True), \
             patch.object(be, "company_model") as mock_company, \
             patch.object(be, "financialyear_model") as mock_fy, \
             patch.object(be, "role_model") as mock_role, \
             patch.object(be, "user_model") as mock_user:

            mock_company.insert_company.return_value = "COM001"
            mock_role.get_role_by_name.return_value = {"roleid": 1}
            mock_user.create_user.return_value = (True, "created")

            be.create_first_company_and_admin(
                "Test Pharmacy", "2082/83", "2082-01-01", "2083-01-01",
                "admin", "Passw0rd!", "Admin User",
            )

        mock_company.insert_company.assert_called_once_with(
            {"companyname": "Test Pharmacy"}, created_by="system"
        )
        mock_fy.insert_financial_year.assert_called_once()
        mock_role.get_role_by_name.assert_called_once_with(be.ADMIN_ROLE_NAME)
        mock_user.create_user.assert_called_once_with(
            username="admin", plain_password="Passw0rd!", fullname="Admin User",
            roleid=1, companyid="COM001", created_by="system",
        )

    def test_missing_admin_role_raises_before_creating_user(self):
        with self._patch_is_bootstrap_needed(needed=True), \
             patch.object(be, "company_model") as mock_company, \
             patch.object(be, "financialyear_model"), \
             patch.object(be, "role_model") as mock_role, \
             patch.object(be, "user_model") as mock_user:

            mock_company.insert_company.return_value = "COM001"
            mock_role.get_role_by_name.return_value = None

            with self.assertRaises(ValidationError):
                be.create_first_company_and_admin(
                    "Test Pharmacy", "2082/83", "2082-01-01", "2083-01-01",
                    "admin", "Passw0rd!", "Admin User",
                )

        mock_user.create_user.assert_not_called()

    def test_user_creation_failure_raises_validation_error(self):
        with self._patch_is_bootstrap_needed(needed=True), \
             patch.object(be, "company_model") as mock_company, \
             patch.object(be, "financialyear_model"), \
             patch.object(be, "role_model") as mock_role, \
             patch.object(be, "user_model") as mock_user:

            mock_company.insert_company.return_value = "COM001"
            mock_role.get_role_by_name.return_value = {"roleid": 1}
            mock_user.create_user.return_value = (False, "username already exists")

            with self.assertRaises(ValidationError):
                be.create_first_company_and_admin(
                    "Test Pharmacy", "2082/83", "2082-01-01", "2083-01-01",
                    "admin", "Passw0rd!", "Admin User",
                )


if __name__ == "__main__":
    unittest.main()