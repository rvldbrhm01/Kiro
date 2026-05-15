"""
Kiro Telegram Bot — entry point (freemodel.dev edition).
Jalankan lokal dengan:
    python bot.py
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent import DEFAULT_MODEL, Agent
from tools import TOOL_SCHEMAS

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

agent = Agent(model=os.environ.get("MODEL", DEFAULT_MODEL))


# ---------------------------------------------------------------------------
# Whitelist
# ---------------------------------------------------------------------------

def _get_allowed_ids() -> set[int]:
    raw = os.environ.get("ALLOWED_USER_IDS", "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def _is_authorized(update: Update) -> bool:
    allowed = _get_allowed_ids()
    if not allowed:
        return False
    user = update.effective_user
    return user is not None and user.id in allowed


async def _reject(update: Update) -> None:
    await update.message.reply_text("⛔ Maaf, kamu tidak memiliki akses ke bot ini.")


async def _send_long(update: Update, text: str, parse_mode: str | None = None) -> None:
    if not text:
        text = "(tidak ada balasan)"
    for i in range(0, len(text), 4000):
        chunk = text[i : i + 4000]
        try:
            await update.message.reply_text(chunk, parse_mode=parse_mode)
        except Exception:
            await update.message.reply_text(chunk)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    user = update.effective_user
    nama = user.first_name if user else "kamu"
    await update.message.reply_text(
        f"Halo {nama}! 👋 Aku *Kiro*, AI software engineer-mu.\n\n"
        "Aku bisa bantu kamu:\n"
        "• 💬 Ngobrol soal code, arsitektur, debugging\n"
        "• 📁 Baca & tulis file kode di workspace\n"
        "• ⚙️ Jalankan script & perintah shell\n"
        "• 🐙 Kelola GitHub issues (triage, label, tutup stale)\n"
        "• 🔍 Cari di web & hitung matematika\n\n"
        "Ketik /help untuk daftar lengkap perintah.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    await update.message.reply_text(
        "*Perintah yang tersedia:*\n\n"
        "🤖 *Umum*\n"
        "/start — salam pembuka\n"
        "/help — pesan ini\n"
        "/reset — hapus riwayat percakapan\n"
        "/model — tampilkan model aktif\n"
        "/tools — daftar semua tools\n\n"
        "🐙 *GitHub*\n"
        "/issues — daftar open issues (repo default)\n"
        "/issue `<nomor>` — detail issue tertentu\n"
        "/triage `<nomor>` — jalankan triage pada issue\n"
        "/stale — tutup semua issue stale\n\n"
        "💡 *Tips:* Chat langsung juga bisa, misal:\n"
        "• _\"Baca file telegram-bot/bot.py\"_\n"
        "• _\"Buatkan fungsi Python untuk parse JSON\"_",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_reset(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    agent.reset(update.effective_chat.id)
    await update.message.reply_text("🗑️ Riwayat percakapan sudah dihapus.")


async def cmd_model(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    await update.message.reply_text(f"🤖 Model aktif: `{agent.model}`", parse_mode=ParseMode.MARKDOWN)


async def cmd_tools(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    lines = ["*Tools yang tersedia:*\n"]
    for s in TOOL_SCHEMAS:
        short = s["description"].split(".")[0].strip()
        lines.append(f"• `{s['name']}` — {short}")
    await _send_long(update, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# GitHub shortcut commands
# ---------------------------------------------------------------------------

async def cmd_issues(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    reply = agent.chat(update.effective_chat.id, "Tampilkan daftar 10 open issues terbaru dari repo default.")
    await _send_long(update, reply)


async def cmd_issue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Penggunaan: /issue <nomor>\nContoh: /issue 42")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    reply = agent.chat(update.effective_chat.id, f"Tampilkan detail issue #{args[0]} dari repo default.")
    await _send_long(update, reply)


async def cmd_triage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Penggunaan: /triage <nomor>\nContoh: /triage 42")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await update.message.reply_text(f"⏳ Menjalankan triage pada issue #{args[0]}...")
    reply = agent.chat(update.effective_chat.id, f"Ambil detail issue #{args[0]}, lalu jalankan triage Kiro lengkap pada issue tersebut.")
    await _send_long(update, reply)


async def cmd_stale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await update.message.reply_text("⏳ Menjalankan stale issue closer...")
    reply = agent.chat(update.effective_chat.id, "Jalankan github_close_stale untuk menutup semua issue stale di repo default.")
    await _send_long(update, reply)


# ---------------------------------------------------------------------------
# Handler pesan biasa
# ---------------------------------------------------------------------------

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    chat_id = update.effective_chat.id
    user_text = (update.message.text or "").strip()
    if not user_text:
        return
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    try:
        reply = agent.chat(chat_id, user_text)
    except Exception as exc:
        log.exception("Agent error")
        reply = f"❌ Terjadi kesalahan: {exc}"
    await _send_long(update, reply)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("❌ TELEGRAM_BOT_TOKEN belum diisi di .env")
    if not os.environ.get("API_KEY"):
        raise SystemExit("❌ API_KEY belum diisi di .env")
    allowed = _get_allowed_ids()
    if not allowed:
        raise SystemExit("❌ ALLOWED_USER_IDS belum diisi di .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("tools", cmd_tools))
    app.add_handler(CommandHandler("issues", cmd_issues))
    app.add_handler(CommandHandler("issue", cmd_issue))
    app.add_handler(CommandHandler("triage", cmd_triage))
    app.add_handler(CommandHandler("stale", cmd_stale))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    log.info("Bot Kiro berjalan | Model: %s | Base URL: %s | User: %s",
             agent.model, os.environ.get("BASE_URL", "https://api.freemodel.dev/v1"), allowed)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
