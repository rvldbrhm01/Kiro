import type { BotContext } from "../index";
import { runFcfsMint } from "../snipe/minter";

/**
 * 🤖 Auto-Mint — configure & trigger automatic SeaDrop FCFS mints.
 *
 * Config sub-commands:
 *   /automint                            → show current config
 *   /automint enable | disable
 *   /automint add <0xAddr>
 *   /automint remove <0xAddr>
 *
 * Action sub-commands:
 *   /automint snipe <chain> <0xAddr> <qty> [priorityGwei] [maxGwei]
 *     e.g. /automint snipe base 0xabc... 1 5 80
 *
 * SECURITY: snipe signs with MINTER_PRIVATE_KEY from the bot's env.
 * Only deploy this bot with a DEDICATED hot wallet. Never put a main
 * wallet's private key in env.
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
        "Sub-commands:\n" +
        "• `enable` / `disable`\n" +
        "• `add <addr>` / `remove <addr>`\n" +
        "• `snipe <chain> <addr> <qty> [priorityGwei] [maxGwei]`",
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

    case "snipe":
      await handleSnipe(ctx, parts.slice(1));
      return;

    default:
      await ctx.reply("Unknown sub-command. Send `/automint` for help.", {
        parse_mode: "Markdown",
      });
  }
}

async function handleSnipe(ctx: BotContext, args: string[]): Promise<void> {
  const [chain, collection, qtyRaw, priorityRaw, maxRaw] = args;

  if (!chain || !collection || !qtyRaw) {
    await ctx.reply(
      "Usage:\n`/automint snipe <chain> <addr> <qty> [priorityGwei] [maxGwei]`\n\n" +
        "Chains: `eth`, `base`",
      { parse_mode: "Markdown" },
    );
    return;
  }

  if (!["eth", "base"].includes(chain)) {
    await ctx.reply("⚠️ chain must be `eth` or `base`.", { parse_mode: "Markdown" });
    return;
  }
  if (!/^0x[a-fA-F0-9]{40}$/.test(collection)) {
    await ctx.reply("⚠️ Invalid collection address.");
    return;
  }
  const quantity = Number(qtyRaw);
  if (!Number.isInteger(quantity) || quantity < 1) {
    await ctx.reply("⚠️ qty must be a positive integer.");
    return;
  }

  const privateKey = process.env.MINTER_PRIVATE_KEY;
  if (!privateKey) {
    await ctx.reply(
      "⚠️ MINTER_PRIVATE_KEY is not configured on the bot host.\n" +
        "The operator must set it (use a dedicated hot wallet) before snipes can run.",
    );
    return;
  }

  await ctx.reply(
    `🚀 Starting FCFS snipe…\nChain: ${chain}\nCollection: \`${collection}\`\nQty: ${quantity}`,
    { parse_mode: "Markdown" },
  );

  // Forward minter logs back to the user as periodic Telegram messages.
  // We batch lines to avoid hitting Telegram rate limits.
  const buffer: string[] = [];
  let flushTimer: NodeJS.Timeout | null = null;
  const flush = async (): Promise<void> => {
    if (buffer.length === 0) return;
    const msg = buffer.splice(0, buffer.length).join("\n");
    try {
      await ctx.reply(msg);
    } catch {
      /* swallow telegram send errors so the snipe still runs */
    }
  };
  const log = (line: string): void => {
    console.log(`[snipe] ${line}`);
    buffer.push(line);
    if (!flushTimer) {
      flushTimer = setTimeout(async () => {
        flushTimer = null;
        await flush();
      }, 1500);
    }
  };

  try {
    const result = await runFcfsMint(
      {
        chain,
        collection,
        quantity,
        privateKey,
        priorityFeeGwei: priorityRaw ? Number(priorityRaw) : undefined,
        maxFeeGwei: maxRaw ? Number(maxRaw) : undefined,
      },
      log,
    );
    await flush();

    const icon = result.status === "success" ? "✅" : result.status === "skipped" ? "⏭" : "❌";
    const lines = [`${icon} Snipe ${result.status.toUpperCase()}`];
    if (result.reason) lines.push(`Reason: ${result.reason}`);
    if (result.explorerUrl) lines.push(result.explorerUrl);
    await ctx.reply(lines.join("\n"));
  } catch (err) {
    await flush();
    const e = err as { message?: string };
    await ctx.reply(`❌ Snipe error: ${e?.message ?? String(err)}`);
  }
}
