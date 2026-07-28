import unittest
from datetime import datetime, timedelta

from engines.password_manager import (
    hash_password, verify_password, check_password_policy, is_password_expired,
)


class TestPasswordManager(unittest.TestCase):

    def test_hash_and_verify_correct_password(self):
        h, s = hash_password("MyP@ssw0rd")
        self.assertTrue(verify_password("MyP@ssw0rd", h, s))

    def test_verify_rejects_wrong_password(self):
        h, s = hash_password("MyP@ssw0rd")
        self.assertFalse(verify_password("WrongPassword", h, s))

    def test_policy_rejects_short_password(self):
        is_valid, _ = check_password_policy("abc")
        self.assertFalse(is_valid)

    def test_policy_accepts_strong_password(self):
        is_valid, _ = check_password_policy("MyP@ssw0rd")
        self.assertTrue(is_valid)

    def test_password_expired_when_old(self):
        self.assertTrue(is_password_expired(datetime.now() - timedelta(days=100)))

    def test_password_not_expired_when_recent(self):
        self.assertFalse(is_password_expired(datetime.now() - timedelta(days=5)))


if __name__ == "__main__":
    unittest.main()
