import type { BotContext } from "../index";

/**
 * 🖼️ Portfolio — list NFTs held by the active wallet.
 *
 * TODO: integrate with Alchemy `getNFTs`, Reservoir `/users/{user}/tokens/v9`,
 * Moralis, or OpenSea API. Format the response with collection name,
 * thumbnail, and floor price.
 */
export async function portfolioHandler(ctx: BotContext): Promise<void> {
  const wallet = ctx.session.activeWallet;
  if (!wallet) {
    await ctx.reply(
      "🖼️ No active wallet set.\n\n" + "Set one with:\n`/wallet 0xYourAddress`",
      { parse_mode: "Markdown" },
    );
    return;
  }

  // Placeholder — replace with a real provider call.
  const stub = [
    "🖼️ Portfolio for",
    `\`${wallet}\``,
    "",
    "_Stub data — wire up Alchemy/Reservoir in src/handlers/portfolio.ts_",
    "",
    "• 0 collections",
    "• 0 NFTs",
  ].join("\n");

  await ctx.reply(stub, { parse_mode: "Markdown" });
}
