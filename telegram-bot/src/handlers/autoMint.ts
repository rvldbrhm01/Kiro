import type { BotContext } from "../index";

/**
 * 🤖 Auto-Mint — configure automatic minting at launch.
 *
 * Usage:
 *   /automint                  → show current config
 *   /automint enable|disable
 *   /automint add <0xAddr>
 *   /automint remove <0xAddr>
 *
 * SECURITY NOTE: actual transaction signing is intentionally NOT bundled
 * here. To execute mints you must add a signer (e.g. ethers.Wallet) with a
 * funded private key — only do this on a dedicated hot wallet you control.
 */
export async function autoMintHandler(ctx: BotContext): Promise<void> {
  const parts = (ctx.message?.text ?? "").trim().split(/\s+/).slice(1);
  const cfg = ctx.session.autoMint;

  if (parts.length === 0) {
    const status = cfg.enabled ? "✅ enabled" : "⏸ disabled";
    const list = cfg.collections.length
      ? cfg.collections.map((c) => `• \`${c}\``).join("\n")
      : "(none)";
    await ctx.reply(
      `🤖 Auto-Mint: ${status}\n\nWatchlist:\n${list}\n\n` +
        "Commands: enable, disable, add <addr>, remove <addr>",
      { parse_mode: "Markdown" },
    );
    return;
  }

  switch (parts[0]) {
    case "enable":
      cfg.enabled = true;
      await ctx.reply("✅ Auto-Mint enabled.");
      return;
    case "disable":
      cfg.enabled = false;
      await ctx.reply("⏸ Auto-Mint disabled.");
      return;
    case "add":
      if (!parts[1] || !/^0x[a-fA-F0-9]{40}$/.test(parts[1])) {
        await ctx.reply("⚠️ Provide a valid 0x address.");
        return;
      }
      if (!cfg.collections.includes(parts[1])) cfg.collections.push(parts[1]);
      await ctx.reply(`✅ Added \`${parts[1]}\``, { parse_mode: "Markdown" });
      return;
    case "remove":
      if (!parts[1]) {
        await ctx.reply("Usage: /automint remove <addr>");
        return;
      }
      cfg.collections = cfg.collections.filter(
        (a) => a.toLowerCase() !== parts[1].toLowerCase(),
      );
      await ctx.reply(`✅ Removed \`${parts[1]}\``, { parse_mode: "Markdown" });
      return;
    default:
      await ctx.reply("Unknown sub-command.");
  }
}
