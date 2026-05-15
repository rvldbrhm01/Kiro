"""
Kiro Telegram Bot — entry point.
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

from agent import DEFAULT_MODEL, ClaudeAgent
from tools import TOOL_SCHEMAS

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

agent = ClaudeAgent(model=os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL))

# ---------------------------------------------------------------------------
# Whitelist — hanya user ID yang terdaftar yang boleh pakai bot
# Set ALLOWED_USER_IDS=123456789,987654321 di .env  (kosong = semua diblokir)
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
        return False   # tidak ada ID terdaftar → blokir semua
    user = update.effective_user
    return user is not None and user.id in allowed


async def _reject(update: Update) -> None:
    user = update.effective_user
    log.warning("Akses ditolak untuk user %s (id=%s)", user.username if user else "?", user.id if user else "?")
    await update.message.reply_text("⛔ Maaf, kamu tidak memiliki akses ke bot ini.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _send_long(update: Update, text: str, parse_mode: str | None = None) -> None:
    """Kirim pesan panjang dengan memotong setiap 4000 karakter."""
    if not text:
        text = "(tidak ada balasan)"
    for i in range(0, len(text), 4000):
        chunk = text[i : i + 4000]
        try:
            await update.message.reply_text(chunk, parse_mode=parse_mode)
        except Exception:  # noqa: BLE001
            # Jika parse mode gagal (misal markdown rusak), kirim sebagai plain text
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
        "/model — tampilkan model Claude aktif\n"
        "/tools — daftar semua tools\n\n"
        "🐙 *GitHub*\n"
        "/issues — daftar open issues (repo default)\n"
        "/issue `<nomor>` — detail issue tertentu\n"
        "/triage `<nomor>` — jalankan triage Kiro pada issue\n"
        "/stale — tutup semua issue stale (pending-response 7+ hari)\n\n"
        "💡 *Tips:* Kamu juga bisa chat langsung, misalnya:\n"
        "• _\"Baca file telegram-bot/bot.py\"_\n"
        "• _\"Triage issue #42\"_\n"
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
    categories = {
        "🔧 Umum": ["get_current_time", "calculate", "web_search"],
        "📁 Kode": ["read_code_file", "write_code_file", "patch_code_file", "run_shell_command"],
        "🐙 GitHub": [
            "github_get_issue", "github_list_issues", "github_assign_labels",
            "github_close_issue", "github_create_issue_comment",
            "github_triage_issue", "github_close_stale",
        ],
    }
    schema_map = {s["name"]: s["description"] for s in TOOL_SCHEMAS}
    for cat, names in categories.items():
        lines.append(f"*{cat}*")
        for name in names:
            desc = schema_map.get(name, "")
            # ambil kalimat pertama saja agar ringkas
            short = desc.split(".")[0].split("(")[0].strip()
            lines.append(f"• `{name}` — {short}")
        lines.append("")
    await _send_long(update, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# GitHub shortcut commands
# ---------------------------------------------------------------------------

async def cmd_issues(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    reply = agent.chat(
        update.effective_chat.id,
        "Tampilkan daftar 10 open issues terbaru dari repo default.",
    )
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
    reply = agent.chat(
        update.effective_chat.id,
        f"Tampilkan detail issue #{args[0]} dari repo default.",
    )
    await _send_long(update, reply)


async def cmd_triage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Penggunaan: /triage <nomor>\nContoh: /triage 42")
        return
    issue_num = args[0]
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await update.message.reply_text(f"⏳ Menjalankan triage pada issue #{issue_num}... (bisa 30–60 detik)")
    reply = agent.chat(
        update.effective_chat.id,
        f"Ambil detail issue #{issue_num}, lalu jalankan triage Kiro lengkap (github_triage_issue) pada issue tersebut. Laporkan hasilnya.",
    )
    await _send_long(update, reply)


async def cmd_stale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await update.message.reply_text("⏳ Menjalankan stale issue closer... (bisa 30–60 detik)")
    reply = agent.chat(
        update.effective_chat.id,
        "Jalankan github_close_stale untuk menutup semua issue stale di repo default. Laporkan hasilnya.",
    )
    await _send_long(update, reply)


# ---------------------------------------------------------------------------
# Handler pesan biasa → agent
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
    except Exception as exc:  # noqa: BLE001
        log.exception("Agent error")
        reply = f"❌ Terjadi kesalahan: {exc}"

    await _send_long(update, reply)


# ---------------------------------------------------------------------------
# Wire up & run
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("❌ TELEGRAM_BOT_TOKEN belum diisi. Copy .env.example ke .env dan isi.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("❌ ANTHROPIC_API_KEY belum diisi. Copy .env.example ke .env dan isi.")

    allowed = _get_allowed_ids()
    if not allowed:
        raise SystemExit("❌ ALLOWED_USER_IDS belum diisi. Isi dengan Telegram user ID kamu di .env.")

    app = Application.builder().token(token).build()

    # Daftarkan semua command
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CommandHandler("model",  cmd_model))
    app.add_handler(CommandHandler("tools",  cmd_tools))
    app.add_handler(CommandHandler("issues", cmd_issues))
    app.add_handler(CommandHandler("issue",  cmd_issue))
    app.add_handler(CommandHandler("triage", cmd_triage))
    app.add_handler(CommandHandler("stale",  cmd_stale))

    # Pesan teks biasa
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    log.info("Bot Kiro berjalan dengan model %s | User diizinkan: %s", agent.model, allowed)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
