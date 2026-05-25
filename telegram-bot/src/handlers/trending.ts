import type { BotContext } from "../index";

/**
 * 🔥 Trending — list trending mints right now.
 *
 * TODO: replace stub with a real call, e.g.
 *   GET https://api.reservoir.tools/collections/trending-mints/v2?period=24h
 * with header `x-api-key: RESERVOIR_API_KEY`.
 */
export async function trendingHandler(ctx: BotContext): Promise<void> {
  const stubItems = [
    { name: "Example Collection A", mints: 1234, floor: "0.05 ETH" },
    { name: "Example Collection B", mints: 987, floor: "0.02 ETH" },
    { name: "Example Collection C", mints: 654, floor: "0.10 ETH" },
  ];

  const lines = stubItems
    .map((i, idx) => `${idx + 1}. *${i.name}* — ${i.mints} mints, floor ${i.floor}`)
    .join("\n");

  await ctx.reply(
    `🔥 Trending mints (24h)\n\n${lines}\n\n` +
      "_Stub data — wire up Reservoir in src/handlers/trending.ts_",
    { parse_mode: "Markdown" },
  );
}
