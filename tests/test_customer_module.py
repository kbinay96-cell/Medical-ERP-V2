import unittest
from unittest.mock import patch

from engines.customer_validator import validate_customer
import engines.customer_engine as ce


BASE_VALID_CUSTOMER = {
    "customer_name": "Kathmandu Pharmacy",
    "mobile": "9812345678",
    "email": "kathmandu.pharmacy@example.com",
    "credit_limit": 50000,
    "credit_days": 30,
    "opening_balance": 0,
    "balance_type": "Dr",
}


class TestCustomerValidator(unittest.TestCase):

    def test_valid_minimal_customer(self):
        is_valid, message = validate_customer({"customer_name": "Everest Pharmacy"})
        self.assertTrue(is_valid, message)

    def test_missing_name_rejected(self):
        is_valid, _ = validate_customer({"customer_name": ""})
        self.assertFalse(is_valid)

    def test_blank_name_rejected(self):
        is_valid, _ = validate_customer({"customer_name": "   "})
        self.assertFalse(is_valid)

    def test_mobile_optional(self):
        is_valid, _ = validate_customer({"customer_name": "X", "mobile": ""})
        self.assertTrue(is_valid)

    def test_mobile_valid(self):
        is_valid, _ = validate_customer({"customer_name": "X", "mobile": "9812345678"})
        self.assertTrue(is_valid)

    def test_mobile_invalid_letters(self):
        is_valid, _ = validate_customer({"customer_name": "X", "mobile": "98ABCD5678"})
        self.assertFalse(is_valid)

    def test_email_optional(self):
        is_valid, _ = validate_customer({"customer_name": "X", "email": ""})
        self.assertTrue(is_valid)

    def test_email_invalid(self):
        is_valid, _ = validate_customer({"customer_name": "X", "email": "not-an-email"})
        self.assertFalse(is_valid)

    def test_credit_limit_negative_rejected(self):
        is_valid, _ = validate_customer({"customer_name": "X", "credit_limit": -100})
        self.assertFalse(is_valid)

    def test_credit_days_negative_rejected(self):
        is_valid, _ = validate_customer({"customer_name": "X", "credit_days": -5})
        self.assertFalse(is_valid)

    def test_opening_balance_negative_rejected(self):
        is_valid, _ = validate_customer({"customer_name": "X", "opening_balance": -1})
        self.assertFalse(is_valid)

    def test_balance_type_invalid(self):
        is_valid, _ = validate_customer({"customer_name": "X", "balance_type": "XX"})
        self.assertFalse(is_valid)

    def test_balance_type_cr_accepted(self):
        is_valid, _ = validate_customer({"customer_name": "X", "balance_type": "Cr"})
        self.assertTrue(is_valid)

    def test_photo_path_valid_extension(self):
        is_valid, _ = validate_customer({"customer_name": "X", "photo_path": "resources/images/customers/CUS-0001.png"})
        self.assertTrue(is_valid)

    def test_photo_path_invalid_extension(self):
        is_valid, _ = validate_customer({"customer_name": "X", "photo_path": "resources/images/customers/CUS-0001.gif"})
        self.assertFalse(is_valid)


class TestCustomerEngineCreate(unittest.TestCase):

    def test_auto_generates_code_when_not_provided(self):
        data = dict(BASE_VALID_CUSTOMER)
        with patch("engines.settings_engine.get_setting", return_value="CUS-"), \
             patch("models.customer_model.get_next_customer_code", return_value="CUS-0007") as mock_next_code, \
             patch("models.customer_model.customer_name_exists", return_value=False), \
             patch("models.customer_model.create_customer", return_value=42), \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message, customer_id = ce.create_customer(data, "admin")

        self.assertTrue(success, message)
        self.assertEqual(customer_id, 42)
        mock_next_code.assert_called_once_with("CUS-")
        self.assertIn("CUS-0007", message)

    def test_manual_code_override_used_when_available(self):
        data = dict(BASE_VALID_CUSTOMER)
        data["customer_code"] = "CUS-9999"
        with patch("models.customer_model.customer_code_exists", return_value=False), \
             patch("models.customer_model.customer_name_exists", return_value=False), \
             patch("models.customer_model.create_customer", return_value=1) as mock_create, \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message, customer_id = ce.create_customer(data, "admin")

        self.assertTrue(success, message)
        saved_data = mock_create.call_args[0][0]
        self.assertEqual(saved_data["customer_code"], "CUS-9999")

    def test_manual_code_conflict_rejected(self):
        data = dict(BASE_VALID_CUSTOMER)
        data["customer_code"] = "CUS-0001"
        with patch("models.customer_model.customer_code_exists", return_value=True), \
             patch("models.customer_model.create_customer") as mock_create:
            success, message, customer_id = ce.create_customer(data, "admin")

        self.assertFalse(success)
        self.assertIsNone(customer_id)
        self.assertFalse(mock_create.called)

    def test_missing_name_rejected_without_touching_db(self):
        data = {"customer_name": ""}
        with patch("models.customer_model.get_next_customer_code", return_value="CUS-0001"), \
             patch("models.customer_model.create_customer") as mock_create:
            success, message, customer_id = ce.create_customer(data, "admin")

        self.assertFalse(success)
        self.assertFalse(mock_create.called)

    def test_duplicate_name_rejected(self):
        data = dict(BASE_VALID_CUSTOMER)
        with patch("models.customer_model.get_next_customer_code", return_value="CUS-0001"), \
             patch("models.customer_model.customer_name_exists", return_value=True), \
             patch("models.customer_model.create_customer") as mock_create:
            success, message, customer_id = ce.create_customer(data, "admin")

        self.assertFalse(success)
        self.assertFalse(mock_create.called)
        self.assertIn("already exists", message)

    def test_photo_staged_is_saved_and_attached(self):
        data = dict(BASE_VALID_CUSTOMER)
        data["_photo_source_path"] = "/tmp/some_photo.jpg"

        with patch("models.customer_model.get_next_customer_code", return_value="CUS-0001"), \
             patch("models.customer_model.customer_name_exists", return_value=False), \
             patch("utils.image_manager.save_image", return_value=(True, "resources/images/customers/CUS-0001.jpg")) as mock_save_image, \
             patch("models.customer_model.create_customer", return_value=1) as mock_create, \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message, customer_id = ce.create_customer(data, "admin")

        self.assertTrue(success, message)
        mock_save_image.assert_called_once_with("/tmp/some_photo.jpg", "customers", "CUS-0001")
        saved_data = mock_create.call_args[0][0]
        self.assertEqual(saved_data["photo_path"], "resources/images/customers/CUS-0001.jpg")
        self.assertNotIn("_photo_source_path", saved_data)

    def test_survives_db_error_on_create(self):
        data = dict(BASE_VALID_CUSTOMER)
        with patch("models.customer_model.get_next_customer_code", return_value="CUS-0001"), \
             patch("models.customer_model.customer_name_exists", return_value=False), \
             patch("models.customer_model.create_customer", side_effect=RuntimeError("DB down")), \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message, customer_id = ce.create_customer(data, "admin")

        self.assertFalse(success)
        self.assertIsNone(customer_id)
        self.assertIn("try again", message.lower())


class TestCustomerEngineUpdate(unittest.TestCase):

    def _existing_row(self, **overrides):
        row = {
            "customer_id": 1, "customer_code": "CUS-0001",
            "customer_name": "Old Name", "photo_path": "resources/images/customers/CUS-0001.jpg",
        }
        row.update(overrides)
        return row

    def test_customer_not_found(self):
        with patch("models.customer_model.get_customer_by_id", return_value=None):
            success, message = ce.update_customer(999, dict(BASE_VALID_CUSTOMER), "admin")
        self.assertFalse(success)
        self.assertIn("not found", message.lower())

    def test_code_conflict_on_update_rejected(self):
        data = dict(BASE_VALID_CUSTOMER)
        data["customer_code"] = "CUS-9999"
        with patch("models.customer_model.get_customer_by_id", return_value=self._existing_row()), \
             patch("models.customer_model.customer_code_exists", return_value=True), \
             patch("models.customer_model.update_customer") as mock_update:
            success, message = ce.update_customer(1, data, "admin")

        self.assertFalse(success)
        self.assertFalse(mock_update.called)

    def test_remove_photo_deletes_file_and_clears_path(self):
        data = dict(BASE_VALID_CUSTOMER)
        data["_remove_photo"] = True

        with patch("models.customer_model.get_customer_by_id", return_value=self._existing_row()), \
             patch("models.customer_model.customer_name_exists", return_value=False), \
             patch("utils.image_manager.delete_image", return_value=True) as mock_delete, \
             patch("models.customer_model.update_customer") as mock_update, \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message = ce.update_customer(1, data, "admin")

        self.assertTrue(success, message)
        mock_delete.assert_called_once_with("resources/images/customers/CUS-0001.jpg")
        saved_data = mock_update.call_args[0][1]
        self.assertIsNone(saved_data["photo_path"])

    def test_new_photo_replaces_old(self):
        data = dict(BASE_VALID_CUSTOMER)
        data["_photo_source_path"] = "/tmp/new_photo.png"

        with patch("models.customer_model.get_customer_by_id", return_value=self._existing_row()), \
             patch("models.customer_model.customer_name_exists", return_value=False), \
             patch("utils.image_manager.save_image", return_value=(True, "resources/images/customers/CUS-0001.png")) as mock_save, \
             patch("models.customer_model.update_customer") as mock_update, \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message = ce.update_customer(1, data, "admin")

        self.assertTrue(success, message)
        mock_save.assert_called_once_with("/tmp/new_photo.png", "customers", "CUS-0001")
        saved_data = mock_update.call_args[0][1]
        self.assertEqual(saved_data["photo_path"], "resources/images/customers/CUS-0001.png")

    def test_no_photo_change_keeps_existing_path(self):
        data = dict(BASE_VALID_CUSTOMER)

        with patch("models.customer_model.get_customer_by_id", return_value=self._existing_row()), \
             patch("models.customer_model.customer_name_exists", return_value=False), \
             patch("models.customer_model.update_customer") as mock_update, \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message = ce.update_customer(1, data, "admin")

        self.assertTrue(success, message)
        saved_data = mock_update.call_args[0][1]
        self.assertEqual(saved_data["photo_path"], "resources/images/customers/CUS-0001.jpg")


class TestCustomerEngineOtherOperations(unittest.TestCase):

    def test_search_customers_passes_filters_through(self):
        with patch("models.customer_model.list_customers", return_value=[{"customer_id": 1}]) as mock_list:
            results = ce.search_customers(search_text="phar", is_active=True, area_id=2)

        self.assertEqual(len(results), 1)
        mock_list.assert_called_once_with(
            search_text="phar", is_active=True, area_id=2, route_id=None, price_level_id=None
        )

    def test_search_customers_survives_db_error(self):
        with patch("models.customer_model.list_customers", side_effect=RuntimeError("DB down")):
            results = ce.search_customers(search_text="phar")
        self.assertEqual(results, [])

    def test_get_active_customers_survives_db_error(self):
        with patch("models.customer_model.get_active_customers", side_effect=RuntimeError("DB down")):
            results = ce.get_active_customers()
        self.assertEqual(results, [])

    def test_soft_delete_success(self):
        row = {"customer_id": 1, "customer_code": "CUS-0001"}
        with patch("models.customer_model.get_customer_by_id", return_value=row), \
             patch("models.customer_model.soft_delete_customer") as mock_delete, \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message = ce.soft_delete_customer(1, "admin")

        self.assertTrue(success, message)
        self.assertTrue(mock_delete.called)

    def test_soft_delete_not_found(self):
        with patch("models.customer_model.get_customer_by_id", return_value=None):
            success, message = ce.soft_delete_customer(999, "admin")
        self.assertFalse(success)

    def test_set_active_status_success(self):
        with patch("models.customer_model.set_active_status") as mock_set, \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message = ce.set_active_status(1, False, "admin")

        self.assertTrue(success, message)
        self.assertTrue(mock_set.called)
        self.assertIn("deactivated", message)

    def test_set_active_status_survives_db_error(self):
        with patch("models.customer_model.set_active_status", side_effect=RuntimeError("DB down")), \
             patch("engines.customer_engine._today_bs", return_value="2083-04-15"):
            success, message = ce.set_active_status(1, True, "admin")
        self.assertFalse(success)

    def test_get_lookup_data_survives_db_error(self):
        with patch("models.customer_model.get_areas", side_effect=RuntimeError("DB down")):
            data = ce.get_lookup_data()
        self.assertEqual(data, {"areas": [], "routes": [], "price_levels": []})

    def test_get_lookup_data_success(self):
        with patch("models.customer_model.get_areas", return_value=[{"area_id": 1}]), \
             patch("models.customer_model.get_routes", return_value=[{"route_id": 1}]), \
             patch("models.customer_model.get_price_levels", return_value=[{"price_level_id": 1}]):
            data = ce.get_lookup_data()

        self.assertEqual(len(data["areas"]), 1)
        self.assertEqual(len(data["routes"]), 1)
        self.assertEqual(len(data["price_levels"]), 1)


if __name__ == "__main__":
    unittest.main()
