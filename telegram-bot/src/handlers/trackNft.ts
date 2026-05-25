import type { BotContext } from "../index";

/**
 * 🔍 Track NFT — subscribe to mint events for a collection.
 *
 * Usage:
 *   /track                       → list tracked collections
 *   /track 0xCollectionAddress   → start tracking
 *   /track remove 0xAddress      → stop tracking
 *
 * TODO: wire this up to a mint-event listener (Reservoir websocket, Alchemy
 * Notify, or a polling worker). When a mint is detected, send the user a DM.
 */
export async function trackNftHandler(ctx: BotContext): Promise<void> {
  const text = ctx.message?.text ?? "";
  const parts = text.trim().split(/\s+/).slice(1);
  const list = ctx.session.trackedCollections;

  if (parts.length === 0) {
    if (list.length === 0) {
      await ctx.reply(
        "🔍 You're not tracking any collections yet.\n\n" +
          "Add one with:\n`/track 0xCollectionAddress`",
        { parse_mode: "Markdown" },
      );
      return;
    }
    const lines = list.map((addr, i) => `${i + 1}. \`${addr}\``).join("\n");
    await ctx.reply(`🔍 Tracked collections:\n${lines}`, { parse_mode: "Markdown" });
    return;
  }

  if (parts[0] === "remove" && parts[1]) {
    const target = parts[1].toLowerCase();
    const before = list.length;
    ctx.session.trackedCollections = list.filter((a) => a.toLowerCase() !== target);
    const removed = before - ctx.session.trackedCollections.length;
    await ctx.reply(removed ? `✅ Stopped tracking \`${parts[1]}\`` : "Not in your list.", {
      parse_mode: "Markdown",
    });
    return;
  }

  const addr = parts[0];
  if (!/^0x[a-fA-F0-9]{40}$/.test(addr)) {
    await ctx.reply("⚠️ That doesn't look like a valid contract address.");
    return;
  }
  if (list.includes(addr)) {
    await ctx.reply("Already tracking that collection.");
    return;
  }
  list.push(addr);
  await ctx.reply(`✅ Now tracking \`${addr}\``, { parse_mode: "Markdown" });
}
