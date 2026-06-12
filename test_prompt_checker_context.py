"""Tests for the context-aware prompt checker.

Guards against the bug where the topic gate judged each message in
isolation, so follow-ups like "Please give me the full instructions in
class-friendly form" were rejected as off-topic mid-conversation.
"""

import unittest

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from scd_agent import build_checker_transcript


class BuildCheckerTranscriptTests(unittest.TestCase):
    def test_empty_history(self):
        self.assertEqual(build_checker_transcript([]), "")

    def test_formats_user_and_assistant_turns(self):
        messages = [
            HumanMessage(content="How do you teach skip change of step?"),
            AIMessage(content="Here is the RSCDS manual guidance for skip change of step."),
        ]
        transcript = build_checker_transcript(messages)
        self.assertEqual(
            transcript,
            "User: How do you teach skip change of step?\n"
            "Assistant: Here is the RSCDS manual guidance for skip change of step.",
        )

    def test_skips_system_and_tool_messages(self):
        messages = [
            SystemMessage(content="You are a dance assistant."),
            HumanMessage(content="What is a poussette?"),
            ToolMessage(content="manual content", tool_call_id="call_1"),
            AIMessage(content="A poussette is a progression formation."),
        ]
        transcript = build_checker_transcript(messages)
        self.assertNotIn("dance assistant", transcript)
        self.assertNotIn("manual content", transcript)
        self.assertIn("User: What is a poussette?", transcript)

    def test_skips_tool_call_only_assistant_messages(self):
        messages = [
            HumanMessage(content="What is a poussette?"),
            AIMessage(content="", tool_calls=[
                {"name": "search_manual", "args": {"query_str": "poussette"}, "id": "call_1"}
            ]),
        ]
        transcript = build_checker_transcript(messages)
        self.assertEqual(transcript, "User: What is a poussette?")

    def test_truncates_long_assistant_answers(self):
        messages = [AIMessage(content="step " * 200)]
        transcript = build_checker_transcript(messages)
        self.assertLessEqual(len(transcript), 320)
        self.assertTrue(transcript.endswith("…"))

    def test_keeps_only_recent_turns(self):
        messages = []
        for i in range(10):
            messages.append(HumanMessage(content=f"question {i}"))
            messages.append(AIMessage(content=f"answer {i}"))
        transcript = build_checker_transcript(messages, max_turns=4)
        lines = transcript.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], "User: question 8")
        self.assertEqual(lines[-1], "Assistant: answer 9")

    def test_collapses_whitespace(self):
        messages = [HumanMessage(content="skip   change\n\nof step")]
        self.assertEqual(build_checker_transcript(messages), "User: skip change of step")


if __name__ == "__main__":
    unittest.main()
