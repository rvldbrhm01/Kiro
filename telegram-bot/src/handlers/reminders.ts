import type { BotContext } from "../index";

/**
 * 🔔 Reminders — set reminders for upcoming mints.
 *
 * Usage:
 *   /reminders                                → list reminders
 *   /reminders add <collection> <ISO-date>    → add reminder
 *   /reminders remove <id>                    → remove reminder
 *
 * TODO: schedule the actual notification (e.g. node-cron job that scans
 * `session.reminders` every minute, or an external scheduler like BullMQ).
 */
export async function remindersHandler(ctx: BotContext): Promise<void> {
  const parts = (ctx.message?.text ?? "").trim().split(/\s+/).slice(1);
  const reminders = ctx.session.reminders;

  if (parts.length === 0) {
    if (reminders.length === 0) {
      await ctx.reply(
        "🔔 No reminders yet.\n\n" +
          "Add one with:\n`/reminders add CryptoFoo 2026-06-01T15:00Z`",
        { parse_mode: "Markdown" },
      );
      return;
    }
    const lines = reminders.map(
      (r) => `• \`${r.id}\` — ${r.collection} @ ${new Date(r.mintAt).toISOString()}`,
    );
    await ctx.reply(`🔔 Reminders:\n${lines.join("\n")}`, { parse_mode: "Markdown" });
    return;
  }

  if (parts[0] === "add" && parts[1] && parts[2]) {
    const mintAt = Date.parse(parts[2]);
    if (Number.isNaN(mintAt)) {
      await ctx.reply("⚠️ Could not parse date. Use ISO 8601, e.g. 2026-06-01T15:00Z");
      return;
    }
    const id = Math.random().toString(36).slice(2, 8);
    reminders.push({ id, collection: parts[1], mintAt });
    await ctx.reply(`✅ Reminder \`${id}\` added.`, { parse_mode: "Markdown" });
    return;
  }

  if (parts[0] === "remove" && parts[1]) {
    const before = reminders.length;
    ctx.session.reminders = reminders.filter((r) => r.id !== parts[1]);
    const removed = before - ctx.session.reminders.length;
    await ctx.reply(removed ? `✅ Removed reminder \`${parts[1]}\`` : "No such reminder.", {
      parse_mode: "Markdown",
    });
    return;
  }

  await ctx.reply("Usage: /reminders [add <name> <iso-date> | remove <id>]");
}
