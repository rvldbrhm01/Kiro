import type { BotContext } from "../index";

/**
 * 📋 Mint History — show past mints made via the bot.
 *
 * TODO: persist mint records (Postgres / SQLite) keyed by Telegram user ID
 * and read them back here. For now we return an empty placeholder.
 */
export async function historyHandler(ctx: BotContext): Promise<void> {
  await ctx.reply(
    "📋 Mint history\n\n" +
      "_No mints recorded yet._\n\n" +
      "Once you mint through this bot, completed transactions will appear here.",
    { parse_mode: "Markdown" },
  );
}
