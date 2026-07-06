#!/usr/bin/env python3
"""Tests for response feedback storage and context snapshots."""

import os
import tempfile
import unittest

import web_app


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = web_app.CHAT_DB_PATH
        web_app.CHAT_DB_PATH = os.path.join(self._tmpdir.name, "chat.db")
        web_app.init_chat_db()

    def tearDown(self):
        web_app.CHAT_DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def _seed_conversation(self, session_id="s1", browser_id="b1"):
        web_app.save_message(session_id, "user", "How do I teach poussette?", browser_id)
        web_app.save_message(session_id, "assistant", "Here is the poussette guidance.", browser_id)
        web_app.save_message(session_id, "user", "Make it class-friendly.", browser_id)
        web_app.save_message(session_id, "assistant", "Class-friendly poussette answer.", browser_id)

    def _get_feedback(self, feedback_id):
        conn = web_app._get_chat_conn()
        row = conn.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
        conn.close()
        return dict(row)

    def test_feedback_snapshots_conversation_context(self):
        self._seed_conversation()
        fid = web_app.save_feedback(
            "s1", "down", "Class-friendly poussette answer.", None, "b1", "1.2.3.4"
        )
        row = self._get_feedback(fid)
        self.assertEqual(row["rating"], "down")
        self.assertIsNotNone(row["message_id"])
        self.assertIn("How do I teach poussette?", row["context_text"])
        self.assertIn("Class-friendly poussette answer.", row["context_text"])

    def test_context_survives_chat_deletion(self):
        self._seed_conversation()
        fid = web_app.save_feedback(
            "s1", "down", "Class-friendly poussette answer.", None, "b1", "1.2.3.4"
        )
        web_app.clear_chat_history("s1", browser_id="b1")
        row = self._get_feedback(fid)
        self.assertIn("How do I teach poussette?", row["context_text"])

    def test_no_context_leak_across_browsers(self):
        self._seed_conversation(browser_id="owner-browser")
        fid = web_app.save_feedback(
            "s1", "down", "Class-friendly poussette answer.", None, "attacker-browser", "9.9.9.9"
        )
        row = self._get_feedback(fid)
        self.assertEqual(row["context_text"], "")
        self.assertIsNone(row["message_id"])

    def test_comment_update_requires_same_browser(self):
        self._seed_conversation()
        fid = web_app.save_feedback(
            "s1", "up", "Class-friendly poussette answer.", None, "b1", "1.2.3.4"
        )
        self.assertFalse(web_app.update_feedback_comment(fid, "hijacked", "other-browser"))
        self.assertTrue(web_app.update_feedback_comment(fid, "great answer", "b1"))
        self.assertEqual(self._get_feedback(fid)["comment"], "great answer")


if __name__ == "__main__":
    unittest.main()
