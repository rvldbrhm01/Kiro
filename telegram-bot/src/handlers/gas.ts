import type { BotContext } from "../index";
import { config } from "../config";

/**
 * ⛽ Gas — show current gas prices.
 *
 * Default implementation calls the public Etherscan gas oracle. If you have
 * an API key in ETHERSCAN_API_KEY it will be appended automatically.
 *
 * TODO: add multi-chain (Polygon gasstation, Base, Arbitrum) and cache the
 * response for a few seconds.
 */
export async function gasHandler(ctx: BotContext): Promise<void> {
  try {
    const url = new URL("https://api.etherscan.io/api");
    url.searchParams.set("module", "gastracker");
    url.searchParams.set("action", "gasoracle");
    if (config.etherscanKey) url.searchParams.set("apikey", config.etherscanKey);

    const res = await fetch(url);
    const json = (await res.json()) as {
      status: string;
      message?: string;
      result: {
        SafeGasPrice: string;
        ProposeGasPrice: string;
        FastGasPrice: string;
        suggestBaseFee?: string;
      } | string;
    };

    if (json.status !== "1" || typeof json.result === "string") {
      await ctx.reply(
        `⚠️ Could not fetch gas right now (${json.message ?? "unknown error"}).`,
      );
      return;
    }

    const r = json.result;
    await ctx.reply(
      `⛽ Ethereum gas (gwei)\n` +
        `🐢 Safe:    ${r.SafeGasPrice}\n` +
        `🚶 Standard: ${r.ProposeGasPrice}\n` +
        `🚀 Fast:    ${r.FastGasPrice}\n` +
        (r.suggestBaseFee ? `Base fee: ${Number(r.suggestBaseFee).toFixed(2)}` : ""),
    );
  } catch (err) {
    console.error("[gas]", err);
    await ctx.reply("⚠️ Failed to fetch gas prices.");
  }
}
