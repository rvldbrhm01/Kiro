import { Bot, Context, session, SessionFlavor } from "grammy";
import { config } from "./config";
import { mainMenuKeyboard, welcomeInlineKeyboard, labelToAction } from "./keyboards";
import { walletHandler } from "./handlers/wallet";
import { trackNftHandler } from "./handlers/trackNft";
import { remindersHandler } from "./handlers/reminders";
import { autoMintHandler } from "./handlers/autoMint";
import { gasHandler } from "./handlers/gas";
import { portfolioHandler } from "./handlers/portfolio";
import { historyHandler } from "./handlers/history";
import { trendingHandler } from "./handlers/trending";

/**
 * Per-user session shape. Replace InMemoryStorage with a persistent
 * adapter (Redis, Postgres) before going to production.
 */
export interface SessionData {
  activeWallet?: string;
  trackedCollections: string[];
  reminders: { id: string; collection: string; mintAt: number }[];
  autoMint: { enabled: boolean; collections: string[] };
}

export type BotContext = Context & SessionFlavor<SessionData>;

function initialSession(): SessionData {
  return {
    trackedCollections: [],
    reminders: [],
    autoMint: { enabled: false, collections: [] },
  };
}

const bot = new Bot<BotContext>(config.botToken);
bot.use(session({ initial: initialSession }));

// ---- /start ----
bot.command("start", async (ctx) => {
  const name = ctx.from?.first_name ?? "there";
  const wallet = ctx.session.activeWallet ?? "(none — set with /wallet)";
  await ctx.reply(
    `👋 Welcome, ${name}!\n\n` +
      `💼 Active Wallet:\n${wallet}\n\n` +
      `What would you like to do?`,
    { reply_markup: welcomeInlineKeyboard },
  );
  await ctx.reply("Use the menu below to navigate:", {
    reply_markup: mainMenuKeyboard,
  });
});

bot.command("help", async (ctx) => {
  await ctx.reply(
    [
      "Available commands:",
      "/wallet — manage active wallet",
      "/track — track an NFT collection",
      "/reminders — manage mint reminders",
      "/automint — configure auto-mint",
      "/gas — current gas prices",
      "/portfolio — view your NFTs",
      "/history — past mints",
      "/trending — trending mints",
    ].join("\n"),
    { reply_markup: mainMenuKeyboard },
  );
});

// ---- per-skill commands ----
bot.command("wallet", walletHandler);
bot.command("track", trackNftHandler);
bot.command("reminders", remindersHandler);
bot.command("automint", autoMintHandler);
bot.command("gas", gasHandler);
bot.command("portfolio", portfolioHandler);
bot.command("history", historyHandler);
bot.command("trending", trendingHandler);

// ---- inline callback router (welcome buttons) ----
bot.on("callback_query:data", async (ctx) => {
  const data = ctx.callbackQuery.data;
  await ctx.answerCallbackQuery();
  if (!data.startsWith("menu:")) return;
  const action = data.slice("menu:".length);
  await routeAction(ctx, action);
});

// ---- reply-keyboard router ----
bot.on("message:text", async (ctx, next) => {
  const action = labelToAction[ctx.message.text];
  if (!action) return next();
  await routeAction(ctx, action);
});

async function routeAction(ctx: BotContext, action: string): Promise<void> {
  switch (action) {
    case "wallet":     return walletHandler(ctx);
    case "track":      return trackNftHandler(ctx);
    case "reminders":  return remindersHandler(ctx);
    case "automint":   return autoMintHandler(ctx);
    case "gas":        return gasHandler(ctx);
    case "portfolio":  return portfolioHandler(ctx);
    case "history":    return historyHandler(ctx);
    case "trending":   return trendingHandler(ctx);
    case "menu":
      await ctx.reply("📋 Main menu", { reply_markup: mainMenuKeyboard });
      return;
    default:
      await ctx.reply("Unknown action.");
  }
}

bot.catch((err) => {
  console.error("[bot error]", err.error);
});

async function main(): Promise<void> {
  console.log("Starting NFT mint tracker bot…");
  await bot.start({
    onStart: (info) => console.log(`Bot @${info.username} is running.`),
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
