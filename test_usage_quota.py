#!/usr/bin/env python3
"""Tests for daily message quotas, usage logging, and IP blocking."""

import os
import tempfile
import unittest

import web_app


class UsageQuotaTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = web_app.CHAT_DB_PATH
        web_app.CHAT_DB_PATH = os.path.join(self._tmpdir.name, "chat.db")
        web_app.init_chat_db()

    def tearDown(self):
        web_app.CHAT_DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_own_key_is_unlimited(self):
        for _ in range(web_app.DAILY_LIMIT_USER + 5):
            web_app.log_usage("chat", "s1", "user-1", "b1", "1.2.3.4", own_key=True)
        allowed, message = web_app.check_quota("user-1", "b1", "1.2.3.4", has_own_key=True)
        self.assertTrue(allowed)
        self.assertEqual(message, "")

    def test_anonymous_quota_by_browser(self):
        for _ in range(web_app.DAILY_LIMIT_ANON):
            web_app.log_usage("chat", "s1", None, "browser-a", "1.2.3.4", own_key=False)
        allowed, message = web_app.check_quota(None, "browser-a", "9.9.9.9", has_own_key=False)
        self.assertFalse(allowed)
        self.assertIn("Sign in", message)

    def test_anonymous_quota_by_ip_survives_cleared_cookies(self):
        for _ in range(web_app.DAILY_LIMIT_ANON):
            web_app.log_usage("chat", "s1", None, "browser-a", "1.2.3.4", own_key=False)
        # New browser_id, same IP: still limited
        allowed, _ = web_app.check_quota(None, "browser-b", "1.2.3.4", has_own_key=False)
        self.assertFalse(allowed)

    def test_signed_in_quota_higher_than_anonymous(self):
        for _ in range(web_app.DAILY_LIMIT_ANON):
            web_app.log_usage("chat", "s1", "user-1", "b1", "1.2.3.4", own_key=False)
        allowed, _ = web_app.check_quota("user-1", "b1", "1.2.3.4", has_own_key=False)
        self.assertTrue(allowed)

        for _ in range(web_app.DAILY_LIMIT_USER - web_app.DAILY_LIMIT_ANON):
            web_app.log_usage("chat", "s1", "user-1", "b1", "1.2.3.4", own_key=False)
        allowed, message = web_app.check_quota("user-1", "b1", "1.2.3.4", has_own_key=False)
        self.assertFalse(allowed)
        self.assertIn("Settings", message)

    def test_own_key_usage_does_not_count_against_quota(self):
        for _ in range(web_app.DAILY_LIMIT_ANON):
            web_app.log_usage("chat", "s1", None, "browser-a", "1.2.3.4", own_key=True)
        allowed, _ = web_app.check_quota(None, "browser-a", "1.2.3.4", has_own_key=False)
        self.assertTrue(allowed)

    def test_block_and_unblock_ip(self):
        self.assertFalse(web_app.is_ip_blocked("5.6.7.8"))
        web_app.block_ip("5.6.7.8", "testing")
        self.assertTrue(web_app.is_ip_blocked("5.6.7.8"))
        web_app.unblock_ip("5.6.7.8")
        self.assertFalse(web_app.is_ip_blocked("5.6.7.8"))

    def test_mark_usage_rejected(self):
        usage_id = web_app.log_usage("chat", "s1", None, "b1", "1.2.3.4", own_key=False)
        web_app.mark_usage_rejected(usage_id)
        conn = web_app._get_chat_conn()
        row = conn.execute(
            "SELECT rejected FROM usage_log WHERE id = ?", (usage_id,)
        ).fetchone()
        conn.close()
        self.assertEqual(row["rejected"], 1)


if __name__ == "__main__":
    unittest.main()
