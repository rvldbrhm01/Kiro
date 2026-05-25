import type { BotContext } from "../index";

/**
 * 💼 Wallet — show / set the active wallet address.
 *
 * Usage:
 *   /wallet                 → show current active wallet
 *   /wallet 0xabc...        → set active wallet
 */
export async function walletHandler(ctx: BotContext): Promise<void> {
  const text = ctx.message?.text ?? "";
  const parts = text.trim().split(/\s+/);
  const arg = parts[1];

  if (arg) {
    if (!isLikelyAddress(arg)) {
      await ctx.reply("⚠️ That doesn't look like a valid 0x address.");
      return;
    }
    ctx.session.activeWallet = arg;
    await ctx.reply(`💼 Active wallet set:\n\`${arg}\``, { parse_mode: "Markdown" });
    return;
  }

  const current = ctx.session.activeWallet;
  if (!current) {
    await ctx.reply(
      "💼 No active wallet set.\n\n" +
        "Set one with:\n`/wallet 0xYourAddress`",
      { parse_mode: "Markdown" },
    );
    return;
  }
  await ctx.reply(`💼 Active wallet:\n\`${current}\``, { parse_mode: "Markdown" });
}

function isLikelyAddress(value: string): boolean {
  return /^0x[a-fA-F0-9]{40}$/.test(value);
}
