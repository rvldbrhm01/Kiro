"""
Claude agent loop with tool use + per-user conversation memory.
Persona: Kiro - AI software engineer.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from anthropic import Anthropic

from tools import TOOL_SCHEMAS, run_tool

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "4096"))
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
- GitHub repository management via tools:
  - Triage new issues (classify + label + detect duplicates + post acknowledgment)
  - Detect duplicate issues
  - Assign labels to issues
  - Close stale issues
  - Get issue details
  - List open issues
- Web search for current info, docs, or error messages
- Math calculations
- Reading local files

## Tool usage rules
- Always use tools when you need live data (GitHub issues, current time, web info, math).
- After a tool call, summarize the result clearly — don't just dump raw JSON.
- For GitHub operations, always confirm the repo (owner/repo) before acting if it's not obvious.
- If a GitHub operation fails, explain the error and suggest a fix.

## Response format
- Keep responses concise. Use bullet points and headers when helpful.
- For code: always use fenced code blocks with language tag.
- For GitHub results: use a clean summary, not raw JSON.
- Telegram max message size is 4096 chars — be concise but complete.
"""


class ClaudeAgent:
    """Stateful agent: keeps conversation history per chat_id."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        # chat_id -> list of {"role": ..., "content": ...} messages
        self._histories: dict[int, list[dict[str, Any]]] = {}

    # -- Memory helpers ----------------------------------------------------

    def reset(self, chat_id: int) -> None:
        self._histories.pop(chat_id, None)

    def _history(self, chat_id: int) -> list[dict[str, Any]]:
        return self._histories.setdefault(chat_id, [])

    def _trim(self, chat_id: int) -> None:
        """Keep history under MAX_HISTORY_MESSAGES, never splitting tool pairs."""
        history = self._histories.get(chat_id, [])
        while len(history) > MAX_HISTORY_MESSAGES:
            # Always remove from the front; skip if it would split a tool pair
            if not history:
                break
            # Drop first message
            history.pop(0)
            # If the new first message is an assistant turn whose content has
            # tool_use blocks, we must also drop the following user turn that
            # holds tool_result — otherwise the API will reject the history.
            while (
                history
                and history[0]["role"] == "assistant"
                and isinstance(history[0]["content"], list)
                and any(
                    getattr(b, "type", None) == "tool_use"
                    if hasattr(b, "type")
                    else b.get("type") == "tool_use"
                    for b in history[0]["content"]
                )
            ):
                history.pop(0)  # assistant tool_use turn
                if history and history[0]["role"] == "user":
                    history.pop(0)  # corresponding tool_result turn

    # -- Main entry point --------------------------------------------------

    def chat(self, chat_id: int, user_message: str) -> str:
        """Send a user message and return Claude's final text reply."""
        history = self._history(chat_id)
        history.append({"role": "user", "content": user_message})

        for _iteration in range(MAX_TOOL_ITERATIONS):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=history,
            )

            # Store the full assistant turn (text + any tool_use blocks).
            history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                final_text = "".join(
                    block.text for block in response.content if block.type == "text"
                ).strip()
                self._trim(chat_id)
                return final_text or "(no reply)"

            # Execute every tool_use block and feed results back.
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                log.info("Tool call: %s(%s)", block.name, block.input)
                result = run_tool(block.name, block.input or {})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
            history.append({"role": "user", "content": tool_results})

        self._trim(chat_id)
        return "Sorry, I got stuck in a tool loop. Please try /reset and rephrase your request."
