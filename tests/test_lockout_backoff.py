import unittest
from unittest.mock import patch, MagicMock

import models.user_model as um


def _make_mock_connection(fetchone_result=None):
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = fetchone_result
    mock_cur.__enter__.return_value = mock_cur
    mock_cur.__exit__.return_value = False

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = False

    return mock_conn, mock_cur


class TestRegisterFailedAttempt(unittest.TestCase):

    def test_unknown_username_does_nothing(self):
        mock_conn, mock_cur = _make_mock_connection(fetchone_result=None)

        with patch.object(um, "get_connection", return_value=mock_conn):
            um.register_failed_attempt("ghost")

        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_not_called()

    def test_attempt_below_threshold_just_increments(self):
        mock_conn, mock_cur = _make_mock_connection(
            fetchone_result={"failedattempts": 1, "lockoutcount": 0}
        )

        with patch("engines.settings_engine.get_setting", side_effect=[True, 5, 15]), \
             patch.object(um, "get_connection", return_value=mock_conn):
            um.register_failed_attempt("admin")

        update_call = mock_cur.execute.call_args_list[1]
        self.assertIn("UPDATE users SET failedattempts", update_call.args[0])
        self.assertNotIn("lockeduntil", update_call.args[0])
        mock_conn.commit.assert_called_once()

    def test_attempt_reaching_max_locks_account_with_backoff(self):
        mock_conn, mock_cur = _make_mock_connection(
            fetchone_result={"failedattempts": 4, "lockoutcount": 2}
        )

        with patch("engines.settings_engine.get_setting", side_effect=[True, 5, 15]), \
             patch.object(um, "get_connection", return_value=mock_conn):
            um.register_failed_attempt("admin")

        update_call = mock_cur.execute.call_args_list[1]
        self.assertIn("lockeduntil", update_call.args[0])
        params = update_call.args[1]
        self.assertEqual(params[0], 5)   # new failedattempts
        self.assertEqual(params[3], 3)   # new lockoutcount (backoff escalated)
        mock_conn.commit.assert_called_once()

    def test_settings_lookup_failure_falls_back_to_static_constants(self):
        mock_conn, mock_cur = _make_mock_connection(
            fetchone_result={"failedattempts": 0, "lockoutcount": 0}
        )

        with patch("engines.settings_engine.get_setting", side_effect=RuntimeError("settings db down")), \
             patch.object(um, "get_connection", return_value=mock_conn):
            um.register_failed_attempt("admin")  # must not raise

        mock_conn.commit.assert_called_once()


class TestResetFailedAttempts(unittest.TestCase):

    def test_resets_both_counters(self):
        mock_conn, mock_cur = _make_mock_connection()

        with patch.object(um, "get_connection", return_value=mock_conn):
            um.reset_failed_attempts("admin")

        executed_sql = mock_cur.execute.call_args.args[0]
        self.assertIn("failedattempts = 0", executed_sql)
        self.assertIn("lockoutcount = 0", executed_sql)
        mock_conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()