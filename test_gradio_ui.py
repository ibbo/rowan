import asyncio
import json
import unittest
from types import SimpleNamespace

from gradio_app import DanceAgentUI, format_activity_timeline, render_dance_cards


class StubState:
    def __init__(self, messages):
        self.values = {"messages": messages}


class StubAgent:
    def __init__(self, chunks, state_messages):
        self._chunks = list(chunks)
        self._state_messages = list(state_messages)

    async def astream(self, *_args, **_kwargs):
        for chunk in self._chunks:
            yield chunk

    async def aget_state(self, _config):
        return StubState(self._state_messages)


class DanceAgentUITests(unittest.TestCase):
    def test_stream_events_produce_tool_flow(self):
        call_id = "tool-123"
        tool_payload = json.dumps([
            {
                "id": 42,
                "name": "The Flower of Glasgow",
                "kind": "Reel",
                "metaform": "4x32",
                "bars": 32,
                "progression": "3/4",
            },
            {
                "id": 314,
                "name": "The Piper",
                "kind": "Jig",
                "metaform": "3x40",
                "bars": 40,
                "progression": "None",
            },
        ])

        chunks = [
            {"agent": {"messages": [SimpleNamespace(tool_calls=[{"id": call_id, "name": "find_dances", "args": {"limit": 2}}])] }},
            {"tools": {"messages": [SimpleNamespace(tool_call_id=call_id, content=tool_payload)]}},
            {"agent": {"messages": [SimpleNamespace(content="Drafting the final answer for you.")]}}
        ]

        state_messages = [SimpleNamespace(content="Here are the dances you requested.")]

        agent = DanceAgentUI()
        agent._ready = True
        agent.agent = StubAgent(chunks, state_messages)

        async def fake_ready():
            return None

        agent.ensure_ready = fake_ready

        async def collect_events():
            result = []
            async for event in agent.stream_events("Find me 2 dances", "session-1"):
                result.append(event)
            return result

        events = asyncio.run(collect_events())

        self.assertEqual(events[0]["event"], "status")

        tool_start = next(e for e in events if e["event"] == "tool_start")
        self.assertEqual(tool_start["tool"], "find_dances")
        self.assertEqual(tool_start["args"]["limit"], 2)

        tool_result = next(e for e in events if e["event"] == "tool_result")
        dances = tool_result["result"]["dances"]
        self.assertEqual(len(dances), 2)
        self.assertEqual({dance["name"] for dance in dances}, {"The Flower of Glasgow", "The Piper"})

        final_event = events[-1]
        self.assertEqual(final_event["event"], "final")
        self.assertIn("dances you requested", final_event["message"].lower())


class PresentationHelperTests(unittest.TestCase):
    def test_format_activity_timeline_highlights_latest_steps(self):
        log = format_activity_timeline([
            {"time": "10:00", "text": "Analyzing question"},
            {"time": "10:01", "text": "Completed find_dances"},
        ])

        self.assertIn("Agent Activity", log)
        self.assertIn("10:01", log)
        self.assertIn("Completed find_dances", log)

    def test_render_dance_cards_renders_details(self):
        html = render_dance_cards([
            {"id": 7, "name": "The Braes", "kind": "Reel", "metaform": "4x32", "bars": 32, "progression": "3/4"}
        ])

        self.assertIn("dance-card", html)
        self.assertIn("The Braes", html)
        self.assertIn("Bars: 32", html)


if __name__ == "__main__":
    unittest.main()
