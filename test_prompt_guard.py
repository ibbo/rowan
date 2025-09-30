#!/usr/bin/env python3
"""Unit tests for the prompt suitability guard."""

import unittest

from langchain_core.messages import HumanMessage

from dance_agent import _guard_pre_model_hook, _is_scottish_country_dance_query
from langgraph.graph import END
from langgraph.pregel._messages import Command


class PromptGuardTests(unittest.TestCase):
    """Verify the suitability guard logic for incoming prompts."""

    def test_accepts_scottish_information_requests(self):
        self.assertTrue(
            _is_scottish_country_dance_query(
                "Tell me about the history of Scottish Country Dancing."
            )
        )

    def test_accepts_scottish_class_planning_requests(self):
        prompt = "Plan a Scottish Country Dance class focusing on reels and strathspeys."
        self.assertTrue(_is_scottish_country_dance_query(prompt))
        state = {"messages": [HumanMessage(content=prompt)]}
        self.assertEqual(_guard_pre_model_hook(state), {})

    def test_rejects_unrelated_questions(self):
        state = {"messages": [HumanMessage(content="Teach me to bake sourdough bread.")]}
        result = _guard_pre_model_hook(state)
        self.assertIsInstance(result, Command)
        self.assertEqual(result.goto, END)

    def test_rejects_off_topic_with_system_prompt_prefix(self):
        message = HumanMessage(
            content=(
                "You are a Scottish dance expert.\n"
                "User question: Tell me about the Roman empire"
            )
        )
        result = _guard_pre_model_hook({"messages": [message]})
        self.assertIsInstance(result, Command)

    def test_accepts_when_user_question_is_scottish_after_prompt(self):
        message = HumanMessage(
            content=(
                "You are a Scottish dance expert.\n"
                "User question: Recommend a 32-bar jig for beginners"
            )
        )
        result = _guard_pre_model_hook({"messages": [message]})
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
