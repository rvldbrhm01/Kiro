"""
Claude agent loop with tool use + per-user conversation memory.
Persona: Kiro - AI software engineer.

Fitur fallback: jika model utama (Opus 4.7) kena rate limit / overloaded,
otomatis turun ke model cadangan (Sonnet 4.5).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from anthropic import Anthropic, RateLimitError, APIStatusError

from tools import TOOL_SCHEMAS, run_tool

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")
FALLBACK_MODEL = os.environ.get("CLAUDE_FALLBACK_MODEL", "claude-sonnet-4-5-20250929")
MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "4096"))
MAX_TOOL_ITERATIONS = int(os.environ.get("MAX_TOOL_ITERATIONS", "10"))
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "30"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))

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
    """Stateful agent: keeps conversation history per chat_id.
    
    Fallback logic:
    - Coba model utama (claude-opus-4-7)
    - Jika kena RateLimitError / 529 Overloaded → retry sekali setelah 5 detik
    - Jika masih gagal → fallback ke model cadangan (claude-sonnet-4-5-20250929)
    """

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.fallback_model = FALLBACK_MODEL
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
            if not history:
                break
            history.pop(0)
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
                history.pop(0)
                if history and history[0]["role"] == "user":
                    history.pop(0)

    # -- API call with fallback --------------------------------------------

    def _call_api(self, model: str, messages: list[dict[str, Any]]) -> Any:
        """Call Claude API. Raises on non-retryable errors."""
        return self.client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

    def _call_with_fallback(self, messages: list[dict[str, Any]]) -> tuple[Any, str]:
        """
        Try primary model → retry once on rate limit → fallback to secondary.
        Returns (response, model_used).
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = self._call_api(self.model, messages)
                return response, self.model
            except RateLimitError as exc:
                log.warning(
                    "Rate limit pada %s (attempt %d/%d): %s",
                    self.model, attempt + 1, MAX_RETRIES, exc,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5)  # tunggu 5 detik sebelum retry
            except APIStatusError as exc:
                # 529 = Overloaded
                if exc.status_code == 529:
                    log.warning(
                        "Model %s overloaded (attempt %d/%d)",
                        self.model, attempt + 1, MAX_RETRIES,
                    )
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(5)
                else:
                    raise  # error lain, langsung raise

        # Semua retry gagal → fallback ke model cadangan
        log.info(
            "Fallback dari %s ke %s karena high traffic",
            self.model, self.fallback_model,
        )
        response = self._call_api(self.fallback_model, messages)
        return response, self.fallback_model

    # -- Main entry point --------------------------------------------------

    def chat(self, chat_id: int, user_message: str) -> str:
        """Send a user message and return Claude's final text reply.
        Auto-fallback jika model utama high traffic."""
        history = self._history(chat_id)
        history.append({"role": "user", "content": user_message})

        model_used = self.model
        for _iteration in range(MAX_TOOL_ITERATIONS):
            response, model_used = self._call_with_fallback(messages=history)

            # Store the full assistant turn (text + any tool_use blocks).
            history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                final_text = "".join(
                    block.text for block in response.content if block.type == "text"
                ).strip()
                # Tambahkan info jika pakai fallback
                if model_used != self.model:
                    final_text += f"\n\n_⚠️ Model utama ({self.model}) sedang high traffic. Balasan ini dari {model_used}._"
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
        return "Maaf, saya terjebak dalam loop tool. Coba /reset dan ulangi pertanyaan."
