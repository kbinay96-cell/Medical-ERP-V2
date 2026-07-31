import unittest

from utils.settings_ui_helpers import (
    group_icon_name,
    group_tagline,
    humanize_setting_key,
    is_file_path_setting,
    is_image_path_setting,
    parse_enum_options,
)


class TestHumanizeSettingKey(unittest.TestCase):

    def test_simple_key(self):
        self.assertEqual(humanize_setting_key("general.app_name"), "App Name")

    def test_multi_word_key(self):
        self.assertEqual(
            humanize_setting_key("security.max_login_attempts"), "Max Login Attempts"
        )

    def test_key_without_dot(self):
        self.assertEqual(humanize_setting_key("theme"), "Theme")

    def test_empty_key(self):
        self.assertEqual(humanize_setting_key(""), "")


class TestParseEnumOptions(unittest.TestCase):

    def test_business_type_options(self):
        result = parse_enum_options(
            "Retail | Wholesale | Hospital | Distributor | Surgical | Veterinary"
        )
        self.assertEqual(
            result, ["Retail", "Wholesale", "Hospital", "Distributor", "Surgical", "Veterinary"]
        )

    def test_theme_options(self):
        self.assertEqual(parse_enum_options("Light | Dark"), ["Light", "Dark"])

    def test_options_with_trailing_prose(self):
        result = parse_enum_options(
            "A4 | A5 | Letter | Thermal58 | Thermal80"
        )
        self.assertEqual(result, ["A4", "A5", "Letter", "Thermal58", "Thermal80"])

    def test_plain_prose_returns_none(self):
        self.assertIsNone(
            parse_enum_options("BS (primary) or AD (secondary) - BS-first is LOCKED project-wide")
        )

    def test_no_pipe_returns_none(self):
        self.assertIsNone(parse_enum_options("Days before expiry to start warning the user"))

    def test_empty_description_returns_none(self):
        self.assertIsNone(parse_enum_options(""))
        self.assertIsNone(parse_enum_options(None))


class TestPathSettingHints(unittest.TestCase):

    def test_logo_path_is_file(self):
        self.assertTrue(is_file_path_setting("company.logo_path", "Path to company logo image"))

    def test_backup_folder_is_not_file(self):
        self.assertFalse(is_file_path_setting("backup.folder_path", "Folder where backups are saved"))

    def test_logo_path_is_image(self):
        self.assertTrue(is_image_path_setting("company.logo_path", "Path to company logo image"))

    def test_backup_folder_is_not_image(self):
        self.assertFalse(is_image_path_setting("backup.folder_path", "Folder where backups are saved"))


class TestGroupLookups(unittest.TestCase):

    def test_known_group_icon(self):
        self.assertEqual(group_icon_name("User & Security"), "lock")

    def test_unknown_group_icon_falls_back(self):
        self.assertEqual(group_icon_name("Some Future Module"), "list")

    def test_known_group_tagline(self):
        self.assertTrue(group_tagline("Backup"))

    def test_unknown_group_tagline_falls_back(self):
        self.assertEqual(group_tagline("Some Future Module"), "Application preferences")


if __name__ == "__main__":
    unittest.main()
