#!/usr/bin/env python3
"""Gradio UI for the Scottish Country Dance agent."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import gradio as gr
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from dance_agent import create_dance_agent, mcp_client

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("dance_gradio.log")
    ],
)
logger = logging.getLogger("dance-ui")

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are ChatSCD, an expert Scottish Country Dance teacher with full access "
    "to the Scottish Country Dance Database (SCDDB). Use the available tools to "
    "search dances, retrieve details, and explore crib instructions. When you "
    "present dances, include useful teaching details such as formation, number "
    "of bars, and any teaching tips. Format responses with clear headings and "
    "bullet lists so dancers can scan the results quickly."
)

TOOL_DISPLAY_NAMES = {
    "find_dances": "Find Dances",
    "get_dance_detail": "Dance Detail",
    "search_cribs": "Search Cribs",
}

# ---------------------------------------------------------------------------
# Agent streaming utilities
# ---------------------------------------------------------------------------
class DanceAgentUI:
    """Wrapper that manages the LangGraph agent and streams structured events."""

    def __init__(self) -> None:
        self.agent = None
        self._ready = False

    async def ensure_ready(self) -> None:
        if self._ready:
            return

        load_dotenv()
        self.agent = await create_dance_agent()
        await mcp_client.setup()
        self._ready = True
        logger.info("Dance agent and MCP client ready")

    async def stream_events(
        self,
        user_text: str,
        session_id: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream structured events describing the agent's progress."""

        await self.ensure_ready()

        system_and_user = HumanMessage(
            content=f"{SYSTEM_PROMPT}\n\nUser question: {user_text}"
        )
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": 50,
        }

        tool_runs: Dict[str, Dict[str, Any]] = {}

        yield {
            "event": "status",
            "title": "Analyzing question",
            "body": "Getting the dance floor ready and understanding your request.",
        }

        start_time = time.perf_counter()
        try:
            async for chunk in self.agent.astream({"messages": [system_and_user]}, config):
                if not isinstance(chunk, dict):
                    continue

                if "agent" in chunk:
                    await self._handle_agent_chunk(chunk["agent"], tool_runs, start_time)
                    async for event in self._convert_agent_chunk(chunk["agent"], tool_runs):
                        yield event

                if "tools" in chunk:
                    async for event in self._convert_tool_chunk(chunk["tools"], tool_runs):
                        yield event

                if "messages" in chunk:
                    async for event in self._convert_message_chunk(chunk["messages"], tool_runs):
                        yield event

            # Try to fetch the latest assistant message as a fallback
            final_state = await self.agent.aget_state(config)
            final_msg = self._extract_final_message(final_state)
            if final_msg:
                yield {"event": "final", "message": final_msg}
            else:
                yield {
                    "event": "error",
                    "message": "I couldn't find a final answer. Please try again.",
                }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Agent streaming error: %s", exc)
            yield {
                "event": "error",
                "message": f"I ran into an error: {exc}",
            }

    async def _handle_agent_chunk(
        self,
        agent_chunk: Dict[str, Any],
        tool_runs: Dict[str, Dict[str, Any]],
        start_time: float,
    ) -> None:
        """Capture timing information for debugging."""
        if agent_chunk.get("messages"):
            elapsed = time.perf_counter() - start_time
            logger.debug("Agent chunk after %.2fs: %s", elapsed, agent_chunk.keys())

    async def _convert_agent_chunk(
        self,
        agent_chunk: Dict[str, Any],
        tool_runs: Dict[str, Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        messages = agent_chunk.get("messages") or []
        for msg in messages:
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for call in tool_calls:
                    call_id = call.get("id") or str(uuid.uuid4())
                    tool_runs[call_id] = {
                        "name": call.get("name", "tool"),
                        "args": call.get("args", {}),
                    }
                    yield {
                        "event": "tool_start",
                        "tool": tool_runs[call_id]["name"],
                        "call_id": call_id,
                        "args": tool_runs[call_id]["args"],
                    }
            else:
                content = self._stringify_content(getattr(msg, "content", ""))
                if content:
                    yield {"event": "assistant_update", "message": content}

    async def _convert_tool_chunk(
        self,
        tool_chunk: Dict[str, Any],
        tool_runs: Dict[str, Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        for msg in tool_chunk.get("messages", []):
            call_id = getattr(msg, "tool_call_id", None)
            run_meta = tool_runs.get(call_id, {})
            tool_name = run_meta.get("name", "tool")
            parsed = self._parse_tool_output(tool_name, getattr(msg, "content", ""))
            yield {
                "event": "tool_result",
                "tool": tool_name,
                "call_id": call_id,
                "result": parsed,
            }

    async def _convert_message_chunk(
        self,
        messages: List[Any],
        tool_runs: Dict[str, Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        for msg in messages:
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for call in tool_calls:
                    call_id = call.get("id") or str(uuid.uuid4())
                    tool_runs[call_id] = {
                        "name": call.get("name", "tool"),
                        "args": call.get("args", {}),
                    }
                    yield {
                        "event": "tool_start",
                        "tool": tool_runs[call_id]["name"],
                        "call_id": call_id,
                        "args": tool_runs[call_id]["args"],
                    }
            else:
                content = self._stringify_content(getattr(msg, "content", ""))
                if content:
                    yield {"event": "assistant_update", "message": content}

    @staticmethod
    def _stringify_content(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list):
            parts: List[str] = []
            for block in raw:
                if isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                else:
                    parts.append(str(block))
            return "\n\n".join(parts).strip()
        return str(raw).strip()

    @staticmethod
    def _parse_tool_output(tool_name: str, raw: Any) -> Dict[str, Any]:
        def coerce_to_objects(value: Any) -> Any:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            if isinstance(value, list):
                coerced = []
                for item in value:
                    if isinstance(item, (str, dict)):
                        coerced.append(coerce_to_objects(item))
                    else:
                        coerced.append(str(item))
                return coerced
            return value

        parsed = coerce_to_objects(raw)
        dances: List[Dict[str, Any]] = []

        if tool_name == "find_dances":
            if isinstance(parsed, list):
                for entry in parsed:
                    if isinstance(entry, dict):
                        dances.append(
                            {
                                "id": entry.get("id"),
                                "name": entry.get("name"),
                                "kind": entry.get("kind"),
                                "metaform": entry.get("metaform"),
                                "bars": entry.get("bars"),
                                "progression": entry.get("progression"),
                            }
                        )
        elif tool_name == "get_dance_detail" and isinstance(parsed, dict):
            primary = parsed.get("dance") or parsed
            if primary:
                dances.append(
                    {
                        "id": primary.get("id") or primary.get("dance_id"),
                        "name": primary.get("name"),
                        "kind": primary.get("kind"),
                        "metaform": primary.get("metaform"),
                        "bars": primary.get("bars"),
                        "progression": primary.get("progression"),
                    }
                )

        summary = raw if isinstance(raw, str) else json.dumps(parsed, ensure_ascii=False, indent=2)

        return {
            "raw": raw,
            "parsed": parsed,
            "dances": dances,
            "summary": summary,
        }

    @staticmethod
    def _extract_final_message(state: Optional[Any]) -> Optional[str]:
        if not state:
            return None
        values = getattr(state, "values", {})
        messages = values.get("messages")
        if not messages:
            return None
        for msg in reversed(messages):
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                continue
            content = DanceAgentUI._stringify_content(getattr(msg, "content", ""))
            if content:
                return content
        return None


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------
ui = DanceAgentUI()
def format_activity_timeline(events: List[Dict[str, str]]) -> str:
    if not events:
        return "_No activity yet — ask the assistant to begin._"

    lines = ["### 🛰️ Agent Activity"]
    for entry in events[-12:]:
        stamp = entry.get("time", "")
        text = entry.get("text", "")
        lines.append(f"- **{stamp}** — {text}")
    return "\n".join(lines)


def render_dance_cards(dances: List[Dict[str, Any]]) -> str:
    if not dances:
        return """
        <div class="dance-placeholder">
            <p>No dances selected yet. Tool results will appear here.</p>
        </div>
        """

    cards = []
    for dance in dances:
        if not dance:
            continue
        payload = html.escape(json.dumps(dance, ensure_ascii=False))
        cards.append(
            f"""
            <div class="dance-card" tabindex="0" data-dance="{payload}">
                <div class="dance-heading">{html.escape(str(dance.get('name', 'Unknown Dance')))}</div>
                <div class="dance-meta">
                    <span>{html.escape(str(dance.get('kind', 'Unknown type')))}</span>
                    <span>{html.escape(str(dance.get('metaform', 'Unknown formation')))}</span>
                </div>
                <div class="dance-details">
                    <span>Bars: {html.escape(str(dance.get('bars', '–')))}</span>
                    <span>Progression: {html.escape(str(dance.get('progression', '–')))}</span>
                    <span>ID: {html.escape(str(dance.get('id', '–')))}</span>
                </div>
            </div>
            """
        )

    return "<div class=\"dance-grid\">" + "".join(cards) + "</div>"


def timestamp() -> str:
    return time.strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Gradio application
# ---------------------------------------------------------------------------
def build_interface() -> gr.Blocks:
    agent_ui = ui

    css = """
    :root {
        color-scheme: dark;
    }

    body {
        background: radial-gradient(circle at top, #020617 0%, #0b1220 45%, #050a16 100%);
        color: #e2e8f0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    .gradio-container {
        background: transparent;
        color: #e2e8f0;
    }

    .chat-container .message.user .message-content {
        background: linear-gradient(135deg, #1d4ed8 0%, #7c3aed 100%);
        color: #f8fafc;
        border: 1px solid rgba(96, 165, 250, 0.6);
        box-shadow: 0 12px 30px rgba(76, 29, 149, 0.35);
    }

    .chat-container .message.bot .message-content {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: inset 0 0 12px rgba(30, 64, 175, 0.15), 0 14px 28px rgba(2, 6, 23, 0.5);
        color: #e2e8f0;
    }

    .chat-container .message.bot .message-content * {
        color: inherit;
    }

    .gradio-textbox textarea {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.35);
        color: #e2e8f0;
    }

    .gradio-textbox textarea::placeholder {
        color: rgba(226, 232, 240, 0.45);
    }

    .gradio-button.primary {
        background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
        border: none;
        color: #f8fafc;
        box-shadow: 0 10px 24px rgba(37, 99, 235, 0.35);
    }

    .gradio-button.secondary {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.35);
        color: #e2e8f0;
    }

    .dance-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 16px;
    }

    .dance-card {
        background: rgba(15, 23, 42, 0.85);
        border-radius: 16px;
        padding: 18px;
        border: 1px solid rgba(96, 165, 250, 0.35);
        box-shadow: inset 0 0 18px rgba(96, 165, 250, 0.05), 0 18px 40px rgba(2, 6, 23, 0.45);
        display: flex;
        flex-direction: column;
        gap: 10px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        color: #e2e8f0;
        cursor: pointer;
    }

    .dance-card:hover {
        transform: translateY(-6px);
        box-shadow: inset 0 0 18px rgba(96, 165, 250, 0.08), 0 24px 50px rgba(37, 99, 235, 0.25);
    }

    .dance-card:focus-visible {
        outline: 2px solid rgba(96, 165, 250, 0.9);
        outline-offset: 3px;
    }

    .dance-heading {
        font-weight: 600;
        font-size: 17px;
        color: #f1f5f9;
    }

    .dance-meta span {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(59, 130, 246, 0.25);
        color: #bfdbfe;
        border-radius: 999px;
        padding: 4px 12px;
        font-size: 12px;
    }

    .dance-details {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        font-size: 12px;
        color: #cbd5f5;
    }

    .dance-placeholder {
        border: 1px dashed rgba(148, 163, 184, 0.35);
        border-radius: 14px;
        padding: 24px;
        text-align: center;
        color: rgba(226, 232, 240, 0.65);
        background: rgba(15, 23, 42, 0.6);
    }

    .activity-card {
        background: rgba(15, 23, 42, 0.85);
        border-radius: 18px;
        padding: 22px;
        border: 1px solid rgba(59, 130, 246, 0.22);
        box-shadow: inset 0 0 18px rgba(59, 130, 246, 0.06), 0 20px 44px rgba(2, 6, 23, 0.5);
        color: #e2e8f0;
    }

    .activity-card p,
    .activity-card li {
        color: rgba(226, 232, 240, 0.9);
    }

    .main-header {
        text-align: center;
        padding: 32px 12px 18px;
    }

    .main-header h1 {
        margin: 0;
        font-size: 34px;
        background: linear-gradient(135deg, #60a5fa 0%, #c084fc 40%, #f472b6 100%);
        -webkit-background-clip: text;
        color: transparent;
        font-weight: 700;
        text-shadow: 0 10px 30px rgba(96, 165, 250, 0.35);
    }

    .main-header p {
        margin-top: 10px;
        color: rgba(226, 232, 240, 0.75);
    }

    .dance-signal-hidden {
        display: none !important;
        visibility: hidden !important;
        position: absolute !important;
        left: -9999px !important;
    }
    """

    with gr.Blocks(css=css, theme=gr.themes.Soft()) as demo:
        gr.HTML(
            """
            <div class="main-header">
                <h1>ChatSCD Studio</h1>
                <p>Your Scottish Country Dance planning partner</p>
            </div>
            """
        )

        chat_state = gr.State([])
        activity_state = gr.State([])
        selection_state = gr.State([])
        session_state = gr.State({})

        with gr.Row(equal_height=True):
            with gr.Column(scale=7):
                chatbot = gr.Chatbot(
                    type="messages",
                    show_label=False,
                    height=600,
                    elem_classes=["chat-container"],
                )

                with gr.Row():
                    user_message = gr.Textbox(
                        placeholder="Ask about dances, lesson plans, or formations...",
                        lines=2,
                        scale=8,
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)
                    clear_btn = gr.Button("Reset", variant="secondary", scale=1)

            with gr.Column(scale=5):
                activity_panel = gr.Markdown(
                    format_activity_timeline([]),
                    elem_classes=["activity-card"],
                )
                dance_panel = gr.HTML(render_dance_cards([]))
                dance_signal = gr.Textbox(
                    value="",
                    visible=True,
                    elem_id="dance-click-target",
                    interactive=False,
                    container=False,
                    show_label=False,
                    elem_classes=["dance-signal-hidden"],
                )

        async def execute_agent_flow(
            agent_prompt: str,
            user_display: str,
            activity_text: str,
            chat_history: List[Dict[str, str]],
            activity_history: List[Dict[str, str]],
            dance_history: List[Dict[str, Any]],
            session_info: Dict[str, str],
            assistant_placeholder: str = "Starting the search...",
        ):
            if "session_id" not in session_info:
                session_info["session_id"] = f"browser_{uuid.uuid4()}"

            session_id = session_info["session_id"]

            chat_history.append({"role": "user", "content": user_display})
            chat_history.append({"role": "assistant", "content": assistant_placeholder})

            activity_history.append({"time": timestamp(), "text": activity_text})

            yield (
                chat_history,
                format_activity_timeline(activity_history),
                render_dance_cards(dance_history),
                chat_history,
                activity_history,
                dance_history,
                session_info,
            )

            async for event in agent_ui.stream_events(agent_prompt, session_id):
                if event["event"] == "status":
                    activity_history.append(
                        {
                            "time": timestamp(),
                            "text": event["title"],
                        }
                    )
                    chat_history[-1]["content"] = event["body"]

                elif event["event"] == "tool_start":
                    human_name = TOOL_DISPLAY_NAMES.get(event["tool"], event["tool"].title())
                    args = event.get("args", {})
                    pretty_args = ", ".join(f"{k}={v}" for k, v in args.items() if v)
                    activity_history.append(
                        {
                            "time": timestamp(),
                            "text": f"Initiated {human_name} ({pretty_args or 'no filters'})",
                        }
                    )
                    chat_history[-1]["content"] = f"🔍 Running {human_name}..."

                elif event["event"] == "tool_result":
                    human_name = TOOL_DISPLAY_NAMES.get(event["tool"], event["tool"].title())
                    activity_history.append(
                        {
                            "time": timestamp(),
                            "text": f"Completed {human_name} tool call.",
                        }
                    )
                    new_dances = event.get("result", {}).get("dances", [])
                    if new_dances:
                        merged = {d.get("id"): d for d in dance_history if d and d.get("id")}
                        for dance in new_dances:
                            if not dance:
                                continue
                            dance_id = dance.get("id")
                            if dance_id:
                                merged[dance_id] = dance
                        dance_history.clear()
                        dance_history.extend(merged.values())
                    chat_history[-1]["content"] = f"✅ {human_name} returned results."

                elif event["event"] == "assistant_update":
                    chat_history[-1]["content"] = event["message"]

                elif event["event"] == "final":
                    chat_history[-1]["content"] = event["message"]
                    activity_history.append(
                        {
                            "time": timestamp(),
                            "text": "Prepared final response for the user.",
                        }
                    )

                elif event["event"] == "error":
                    chat_history[-1]["content"] = event["message"]
                    activity_history.append(
                        {
                            "time": timestamp(),
                            "text": "Encountered an error.",
                        }
                    )
                    yield (
                        chat_history,
                        format_activity_timeline(activity_history),
                        render_dance_cards(dance_history),
                        chat_history,
                        activity_history,
                        dance_history,
                        session_info,
                    )
                    break

                yield (
                    chat_history,
                    format_activity_timeline(activity_history),
                    render_dance_cards(dance_history),
                    chat_history,
                    activity_history,
                    dance_history,
                    session_info,
                )

        async def handle_message(
            message: str,
            chat_history: Optional[List[Dict[str, str]]],
            activity_history: Optional[List[Dict[str, str]]],
            dance_history: Optional[List[Dict[str, Any]]],
            session_info: Optional[Dict[str, str]],
        ):
            chat_history = list(chat_history or [])
            activity_history = list(activity_history or [])
            dance_history = list(dance_history or [])
            session_info = dict(session_info or {})

            if not message.strip():
                yield (
                    chat_history,
                    format_activity_timeline(activity_history),
                    render_dance_cards(dance_history),
                    chat_history,
                    activity_history,
                    dance_history,
                    session_info,
                    "",
                )
                return

            async for update in execute_agent_flow(
                agent_prompt=message,
                user_display=message,
                activity_text="User request received.",
                chat_history=chat_history,
                activity_history=activity_history,
                dance_history=dance_history,
                session_info=session_info,
            ):
                yield (*update, "")

        async def handle_dance_card_click(
            selection_json: str,
            chat_history: Optional[List[Dict[str, str]]],
            activity_history: Optional[List[Dict[str, str]]],
            dance_history: Optional[List[Dict[str, Any]]],
            session_info: Optional[Dict[str, str]],
        ):
            chat_history = list(chat_history or [])
            activity_history = list(activity_history or [])
            dance_history = list(dance_history or [])
            session_info = dict(session_info or {})

            if not selection_json:
                yield (
                    chat_history,
                    format_activity_timeline(activity_history),
                    render_dance_cards(dance_history),
                    chat_history,
                    activity_history,
                    dance_history,
                    session_info,
                    "",
                )
                return

            try:
                payload = json.loads(selection_json)
                if isinstance(payload, dict) and "dance" in payload:
                    dance = payload.get("dance")
                else:
                    dance = payload
            except json.JSONDecodeError:
                logger.warning("Unable to parse dance selection payload: %s", selection_json)
                yield (
                    chat_history,
                    format_activity_timeline(activity_history),
                    render_dance_cards(dance_history),
                    chat_history,
                    activity_history,
                    dance_history,
                    session_info,
                    "",
                )
                return

            dance_name = str(dance.get("name", "the selected dance"))
            dance_id = dance.get("id")

            agent_prompt = (
                "Provide detailed crib instructions for the Scottish Country Dance "
                f"'{dance_name}'. Include the formation, phrasing, and any notable teaching tips."
            )
            if dance_id is not None:
                agent_prompt += f" The dance's SCDDB ID is {dance_id}."

            user_display = (
                f"📄 Request crib for {dance_name}"
                + (f" (ID {dance_id})" if dance_id is not None else "")
            )
            activity_text = f"Crib requested for {dance_name}."

            async for update in execute_agent_flow(
                agent_prompt=agent_prompt,
                user_display=user_display,
                activity_text=activity_text,
                chat_history=chat_history,
                activity_history=activity_history,
                dance_history=dance_history,
                session_info=session_info,
                assistant_placeholder="Fetching crib instructions...",
            ):
                yield (*update, "")

        async def reset_conversation(
            _session_info: Optional[Dict[str, str]] = None,
        ):
            return (
                [],
                format_activity_timeline([]),
                render_dance_cards([]),
                [],
                [],
                [],
                _session_info or {},
                "",
            )

        msg_event = user_message.submit(
            handle_message,
            [user_message, chat_state, activity_state, selection_state, session_state],
            [chatbot, activity_panel, dance_panel, chat_state, activity_state, selection_state, session_state, dance_signal],
            queue=True,
            show_progress=False,
        )
        send_btn.click(
            handle_message,
            [user_message, chat_state, activity_state, selection_state, session_state],
            [chatbot, activity_panel, dance_panel, chat_state, activity_state, selection_state, session_state, dance_signal],
            queue=True,
            show_progress=False,
        )
        send_btn.click(lambda: "", None, user_message, queue=False)
        msg_event.then(lambda: "", None, user_message, queue=False)

        dance_signal.change(
            handle_dance_card_click,
            [dance_signal, chat_state, activity_state, selection_state, session_state],
            [chatbot, activity_panel, dance_panel, chat_state, activity_state, selection_state, session_state, dance_signal],
            queue=True,
            show_progress=False,
        )

        clear_btn.click(
            reset_conversation,
            [session_state],
            [chatbot, activity_panel, dance_panel, chat_state, activity_state, selection_state, session_state, dance_signal],
            queue=False,
        )

        demo.load(
            None,
            None,
            None,
            js="""
            () => {
                if (window.__danceCardListenersAttached) return null;
                window.__danceCardListenersAttached = true;

                const app = window.gradioApp ? window.gradioApp() : document;

                const getSignal = () => {
                    // Try multiple ways to find the signal element
                    return app.querySelector('#dance-click-target textarea') ||
                           app.querySelector('#dance-click-target input') ||
                           app.querySelector('textarea[data-testid*="dance-click-target"]') ||
                           app.querySelector('input[data-testid*="dance-click-target"]') ||
                           app.querySelector('.dance-signal-hidden textarea') ||
                           app.querySelector('.dance-signal-hidden input') ||
                           document.querySelector('#dance-click-target textarea') ||
                           document.querySelector('#dance-click-target input');
                };

                const dispatchSelection = (card) => {
                    if (!card) {
                        console.warn('Dance card click: No card provided');
                        return;
                    }
                    const raw = card.getAttribute('data-dance');
                    if (!raw) {
                        console.warn('Dance card click: No data-dance attribute found');
                        return;
                    }
                    let danceData = null;
                    try {
                        danceData = JSON.parse(raw);
                        console.log('Dance card click: Parsed dance data', danceData);
                    } catch (err) {
                        console.warn('Unable to parse dance data', err);
                        return;
                    }
                    const signal = getSignal();
                    if (!signal) {
                        console.error('Dance card click: Signal element not found!');
                        console.log('Available textareas:', document.querySelectorAll('textarea').length);
                        console.log('Available inputs:', document.querySelectorAll('input').length);
                        return;
                    }
                    console.log('Dance card click: Signal element found', signal);
                    const payload = JSON.stringify({ dance: danceData, ts: Date.now() });
                    signal.value = payload;
                    signal.dispatchEvent(new Event('input', { bubbles: true }));
                    signal.dispatchEvent(new Event('change', { bubbles: true }));
                    console.log('Dance card click: Events dispatched with payload', payload);
                };

                const findCard = (target) => target && target.closest('.dance-card[data-dance]');

                app.addEventListener('click', (event) => {
                    const card = findCard(event.target);
                    if (card) {
                        event.preventDefault();
                        dispatchSelection(card);
                    }
                });

                app.addEventListener('keydown', (event) => {
                    if (event.key !== 'Enter' && event.key !== ' ') return;
                    const card = findCard(event.target);
                    if (card) {
                        event.preventDefault();
                        dispatchSelection(card);
                    }
                });

                return null;
            }
            """,
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    db_path = os.environ.get("SCDDB_SQLITE", "data/scddb/scddb.sqlite")
    if not Path(db_path).exists():
        print(f"❌ Database not found at {db_path}. Run refresh_scddb.py first.")
        sys.exit(1)

    demo = build_interface()
    demo.queue(max_size=50, default_concurrency_limit=10)
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        share=False,
    )


if __name__ == "__main__":
    main()
