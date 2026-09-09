import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

import engines.backup_engine as be


class TestBackupEngine(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_missing_folder_fails_without_calling_pg_dump(self):
        with patch.object(be.subprocess, "run") as mock_run:
            success, message = be.run_backup("Z:\\this\\folder\\does\\not\\exist")

        self.assertFalse(success)
        self.assertFalse(mock_run.called)
        self.assertIn("folder", message.lower())

    def test_successful_backup_creates_expected_filename_pattern(self):
        fake_result = MagicMock(returncode=0, stderr="")

        with patch.object(be.subprocess, "run", return_value=fake_result) as mock_run, \
             patch.object(be, "write_audit_log") as mock_audit:

            success, message = be.run_backup(self.tmp_dir, userid=1, username="admin")

        self.assertTrue(success)
        self.assertTrue(mock_run.called)
        self.assertTrue(mock_audit.called)
        called_cmd = mock_run.call_args.args[0]
        self.assertIn("pg_dump", called_cmd)
        self.assertIn(self.tmp_dir, message)

    def test_pg_dump_failure_is_reported_and_audited(self):
        fake_result = MagicMock(returncode=1, stderr="connection refused")

        with patch.object(be.subprocess, "run", return_value=fake_result), \
             patch.object(be, "write_audit_log") as mock_audit:

            success, message = be.run_backup(self.tmp_dir, userid=1, username="admin")

        self.assertFalse(success)
        self.assertIn("connection refused", message)
        self.assertTrue(mock_audit.called)

    def test_pg_dump_not_found_gives_friendly_message(self):
        with patch.object(be.subprocess, "run", side_effect=FileNotFoundError):
            success, message = be.run_backup(self.tmp_dir)

        self.assertFalse(success)
        self.assertIn("pg_dump", message)

    def test_audit_logging_failure_never_breaks_backup_result(self):
        fake_result = MagicMock(returncode=0, stderr="")

        with patch.object(be.subprocess, "run", return_value=fake_result), \
             patch.object(be, "write_audit_log", side_effect=RuntimeError("audit db down")):

            success, message = be.run_backup(self.tmp_dir)

        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()