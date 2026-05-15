"""
AI agent loop with tool use + per-user conversation memory.
Persona: Kiro - AI software engineer.
Menggunakan OpenAI-compatible API dari freemodel.dev
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

from tools import TOOL_SCHEMAS, run_tool

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("MODEL", "gpt-4o")
BASE_URL = os.environ.get("BASE_URL", "https://api.freemodel.dev/v1")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "4096"))
MAX_TOOL_ITERATIONS = int(os.environ.get("MAX_TOOL_ITERATIONS", "10"))
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "30"))

SYSTEM_PROMPT = """You are Kiro, an AI software engineer assistant running inside a Telegram bot.

## Your personality & style
- You are a senior software engineer: precise, practical, and concise.
- You write clean, well-structured code with clear explanations.
- You reply in the same language the user writes in (Indonesian or English).
- You are friendly but professional — no fluff, no filler.
- When code is involved, always use markdown code blocks with the correct language tag.

## Your capabilities
You can help with:
- Writing, reviewing, debugging, and explaining code in any language
- Architecture and design decisions
- GitHub repository management via tools
- Web search for current info, docs, or error messages
- Math calculations
- Reading and writing code files
- Running shell commands

## Tool usage rules
- Always use tools when you need live data (GitHub issues, current time, web info, math).
- After a tool call, summarize the result clearly — don't just dump raw JSON.
- For GitHub operations, always confirm the repo (owner/repo) before acting if it's not obvious.

## Response format
- Keep responses concise. Use bullet points and headers when helpful.
- For code: always use fenced code blocks with language tag.
- Telegram max message size is 4096 chars — be concise but complete.
"""


def _build_openai_tools() -> list[dict]:
    """Convert our tool schemas to OpenAI function calling format."""
    tools = []
    for schema in TOOL_SCHEMAS:
        tools.append({
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return tools


class Agent:
    """Stateful agent: keeps conversation history per chat_id."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        key = api_key or os.environ.get("API_KEY", "")
        self.client = OpenAI(api_key=key, base_url=BASE_URL)
        self.model = model
        self.tools = _build_openai_tools()
        self._histories: dict[int, list[dict[str, Any]]] = {}

    def reset(self, chat_id: int) -> None:
        self._histories.pop(chat_id, None)

    def _history(self, chat_id: int) -> list[dict[str, Any]]:
        return self._histories.setdefault(chat_id, [])

    def _trim(self, chat_id: int) -> None:
        """Keep history manageable."""
        history = self._histories.get(chat_id, [])
        # Always keep the system message (index 0) if present
        while len(history) > MAX_HISTORY_MESSAGES:
            history.pop(1 if history and history[0].get("role") == "system" else 0)

    def chat(self, chat_id: int, user_message: str) -> str:
        """Send a user message and return the final text reply."""
        history = self._history(chat_id)

        # Ensure system prompt is first
        if not history or history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

        # Add user message
        history.append({"role": "user", "content": user_message})

        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=history,
                    tools=self.tools if self.tools else None,
                    max_tokens=MAX_TOKENS,
                )
            except Exception as exc:
                log.exception("API error")
                self._trim(chat_id)
                return f"❌ Error dari API: {exc}"

            choice = response.choices[0]
            message = choice.message

            # Store assistant message
            history.append(message.model_dump())

            # Check if there are tool calls
            if not message.tool_calls:
                # No tool calls — return text
                self._trim(chat_id)
                return (message.content or "").strip() or "(tidak ada balasan)"

            # Execute tool calls
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    func_args = {}

                log.info("Tool call: %s(%s)", func_name, func_args)
                result = run_tool(func_name, func_args)

                # Add tool result
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        self._trim(chat_id)
        return "Maaf, saya terjebak dalam loop tool. Coba /reset dan ulangi pertanyaan."
