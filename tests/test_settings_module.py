import json
import os
import tempfile
import unittest
from unittest.mock import patch

from engines import settings_cache
from engines.settings_validator import validate_setting_value, parse_setting_value
import engines.settings_engine as se
from engines import theme_engine

FAKE_ROWS = [
    {
        "setting_key": "general.app_name", "setting_value": "Medical ERP",
        "setting_group": "General", "data_type": "string",
        "default_value": "Medical ERP", "display_order": 10,
    },
    {
        "setting_key": "security.max_login_attempts", "setting_value": "5",
        "setting_group": "User & Security", "data_type": "integer",
        "default_value": "5", "display_order": 80,
    },
    {
        "setting_key": "security.enable_auto_lock", "setting_value": "true",
        "setting_group": "User & Security", "data_type": "boolean",
        "default_value": "true", "display_order": 10,
    },
]


class TestSettingsValidator(unittest.TestCase):

    def test_integer_valid(self):
        self.assertEqual(validate_setting_value("integer", "15"), (True, ""))

    def test_integer_invalid(self):
        is_valid, _ = validate_setting_value("integer", "abcd")
        self.assertFalse(is_valid)

    def test_boolean_valid(self):
        self.assertEqual(validate_setting_value("boolean", "true"), (True, ""))

    def test_boolean_invalid(self):
        is_valid, _ = validate_setting_value("boolean", "maybe")
        self.assertFalse(is_valid)

    def test_color_valid(self):
        self.assertEqual(validate_setting_value("color", "#7C3AED"), (True, ""))

    def test_color_invalid(self):
        is_valid, _ = validate_setting_value("color", "purple")
        self.assertFalse(is_valid)

    def test_unknown_data_type(self):
        is_valid, _ = validate_setting_value("bogus", "x")
        self.assertFalse(is_valid)

    def test_parse_integer(self):
        self.assertEqual(parse_setting_value("integer", "15"), 15)
        self.assertIsInstance(parse_setting_value("integer", "15"), int)

    def test_parse_boolean(self):
        self.assertIs(parse_setting_value("boolean", "true"), True)
        self.assertIs(parse_setting_value("boolean", "false"), False)

    def test_parse_string_passthrough(self):
        self.assertEqual(parse_setting_value("string", "Medical ERP"), "Medical ERP")


class TestSettingsCache(unittest.TestCase):

    def setUp(self):
        settings_cache.clear_cache()
        se.clear_user_runtime_overrides()

    def test_not_loaded_initially(self):
        self.assertFalse(settings_cache.is_loaded())

    def test_load_and_read(self):
        settings_cache.load_cache(FAKE_ROWS)
        self.assertTrue(settings_cache.is_loaded())
        self.assertEqual(settings_cache.get_cached_value("security.max_login_attempts"), 5)
        self.assertIsInstance(settings_cache.get_cached_value("security.max_login_attempts"), int)

    def test_missing_key_returns_default(self):
        settings_cache.load_cache(FAKE_ROWS)
        self.assertEqual(settings_cache.get_cached_value("missing.key", default="fallback"), "fallback")

    def test_update_cached_value(self):
        settings_cache.load_cache(FAKE_ROWS)
        settings_cache.update_cached_value("security.max_login_attempts", "9")
        self.assertEqual(settings_cache.get_cached_value("security.max_login_attempts"), 9)

    def test_clear_cache(self):
        settings_cache.load_cache(FAKE_ROWS)
        settings_cache.clear_cache()
        self.assertFalse(settings_cache.is_loaded())


class TestSettingsEngine(unittest.TestCase):

    def setUp(self):
        settings_cache.clear_cache()

    def test_load_all_settings_populates_cache(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            se.load_all_settings()
        self.assertTrue(settings_cache.is_loaded())

    def test_load_all_settings_never_raises_on_db_error(self):
        with patch("models.settings_model.get_all_settings", side_effect=RuntimeError("DB down")):
            se.load_all_settings()  # must not raise
        self.assertFalse(settings_cache.is_loaded())

    def test_get_setting_autoloads_if_not_loaded(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            value = se.get_setting("general.app_name")
        self.assertEqual(value, "Medical ERP")

    def test_get_setting_returns_default_for_missing_key(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            value = se.get_setting("missing.key", default="fallback")
        self.assertEqual(value, "fallback")

    def test_get_settings_grouped(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            grouped = se.get_settings_grouped()
        self.assertIn("General", grouped)
        self.assertIn("User & Security", grouped)
        self.assertEqual(len(grouped["User & Security"]), 2)

    def test_save_setting_valid_updates_cache(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            se.load_all_settings()
        with patch("models.settings_model.update_setting_value", return_value=(True, "Setting updated successfully.")):
            success, message = se.save_setting("security.max_login_attempts", "7", "admin")
        self.assertTrue(success)
        self.assertEqual(se.get_setting("security.max_login_attempts"), 7)

    def test_save_setting_rejects_invalid_value_without_touching_db(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            se.load_all_settings()
        with patch("models.settings_model.update_setting_value") as mock_update:
            success, message = se.save_setting("security.max_login_attempts", "not-a-number", "admin")
        self.assertFalse(success)
        self.assertFalse(mock_update.called)

    def test_save_setting_unknown_key(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            se.load_all_settings()
        with patch("models.settings_model.get_setting_by_key", return_value=None):
            success, message = se.save_setting("nonexistent.key", "x", "admin")
        self.assertFalse(success)

    def test_save_setting_survives_db_error(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            se.load_all_settings()
        with patch("models.settings_model.update_setting_value", side_effect=RuntimeError("DB down")):
            success, message = se.save_setting("security.max_login_attempts", "7", "admin")
        self.assertFalse(success)
        self.assertIn("try again", message.lower())

    def test_apply_setting_temporarily_does_not_call_db(self):
        with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
            se.load_all_settings()
        with patch("models.settings_model.update_setting_value") as mock_update:
            success, _ = se.apply_setting_temporarily("general.app_name", "Test ERP")
        self.assertTrue(success)
        self.assertFalse(mock_update.called)
        self.assertEqual(se.get_setting("general.app_name"), "Test ERP")

    def test_requires_restart(self):
        self.assertTrue(se.requires_restart("Date & Calendar"))
        self.assertTrue(se.requires_restart("Company"))
        self.assertFalse(se.requires_restart("General"))
        self.assertFalse(se.requires_restart("Print"))

    def test_user_control_height_override_is_personal_and_parsed(self):
        settings_cache.load_cache([
            *FAKE_ROWS,
            {
                "setting_key": "ui.control_height", "setting_value": "28",
                "setting_group": "General", "data_type": "integer",
                "default_value": "28", "display_order": 910,
            },
        ])
        with patch(
            "models.settings_model.get_setting_by_key",
            return_value={"setting_key": "ui.control_height", "setting_value": "36", "data_type": "integer"},
        ):
            self.assertEqual(se.get_user_setting(12, "ui.control_height", 28), 36)

    def test_user_control_height_falls_back_to_global_default(self):
        settings_cache.load_cache([
            *FAKE_ROWS,
            {
                "setting_key": "ui.control_height", "setting_value": "28",
                "setting_group": "General", "data_type": "integer",
                "default_value": "28", "display_order": 910,
            },
        ])
        with patch("models.settings_model.get_setting_by_key", return_value=None):
            self.assertEqual(se.get_user_setting(12, "ui.control_height", 28), 28)

    def test_apply_and_save_user_setting_does_not_change_global_value(self):
        settings_cache.load_cache([
            *FAKE_ROWS,
            {
                "setting_key": "ui.control_height", "setting_value": "28",
                "setting_group": "General", "data_type": "integer",
                "default_value": "28", "display_order": 910,
            },
        ])
        self.assertTrue(se.apply_user_setting_temporarily(12, "ui.control_height", "40")[0])
        self.assertEqual(se.get_user_setting(12, "ui.control_height", 28), 40)
        self.assertEqual(se.get_setting("ui.control_height"), 28)
        with patch("models.settings_model.save_user_setting", return_value=(True, "saved")) as save:
            self.assertTrue(se.save_user_setting(12, "ui.control_height", "40", "user")[0])
        save.assert_called_once_with("ui.control_height", "40", 12, "user", "")
        self.assertEqual(se.get_setting("ui.control_height"), 28)

    def test_dynamic_theme_uses_personal_height_and_standard_table_styles(self):
        settings_cache.load_cache([
            *FAKE_ROWS,
            {
                "setting_key": "ui.control_height", "setting_value": "28",
                "setting_group": "General", "data_type": "integer",
                "default_value": "28", "display_order": 910,
            },
            {
                "setting_key": "ui.font_size", "setting_value": "10.5",
                "setting_group": "General", "data_type": "decimal",
                "default_value": "10.5", "display_order": 911,
            },
            {
                "setting_key": "ui.font_family", "setting_value": "Segoe UI",
                "setting_group": "General", "data_type": "string",
                "default_value": "Segoe UI", "display_order": 912,
            },
        ])
        theme_engine.set_active_user_id(12)
        try:
            with patch(
                "models.settings_model.get_setting_by_key",
                return_value={"setting_key": "ui.control_height", "setting_value": "38", "data_type": "integer"},
            ):
                stylesheet = theme_engine._build_dynamic_overrides()
            self.assertIn("min-height: 36px", stylesheet)
            self.assertIn("max-height: 36px", stylesheet)
            self.assertIn("max-width: 144px", stylesheet)
            self.assertIn("QTableView::item", stylesheet)
        finally:
            theme_engine.set_active_user_id(None)

    def test_export_then_import_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = os.path.join(tmpdir, "settings_export.json")

            with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
                success, message = se.export_settings(export_path)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(export_path))

            with open(export_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data["settings"]), len(FAKE_ROWS))

            with patch("models.settings_model.get_all_settings", return_value=FAKE_ROWS):
                se.load_all_settings()
            with patch("models.settings_model.update_setting_value", return_value=(True, "Setting updated successfully.")):
                success, message = se.import_settings(export_path, "admin")
            self.assertTrue(success)
            self.assertIn("Imported 3", message)

    def test_export_survives_db_error(self):
        with patch("models.settings_model.get_all_settings", side_effect=RuntimeError("DB down")):
            success, message = se.export_settings("/tmp/should_not_be_created.json")
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
